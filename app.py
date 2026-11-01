import io
from datetime import datetime

#import matplotlib
#matplotlib.use("Agg")
#import matplotlib.pyplot as plt

from flask import Flask, render_template, request, redirect, url_for, send_file

from database import get_connection, init_db
from fraud_detection import evaluate_single_transaction, evaluate_all_transactions
from data_generator import generate_users,generate_transactions
from phishing_detection import score_url

app = Flask(__name__)
def setup_database():
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT (*) AS c FROM users")
    if cur.fetchone()["c"] == 0:
        users = generate_users(conn,n=30)
        generate_transactions(conn,users,n=300,fraud_ratio=0.12)
        evaluate_all_transactions(conn)
    conn.close()
setup_database()


@app.route("/")
def dashboard():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as c FROM transactions")
    total_txns = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM transactions WHERE risk_level = 'High'")
    high_risk = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM transactions WHERE risk_level = 'Medium'")
    medium_risk = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM users")
    total_users = cur.fetchone()["c"]

    cur.execute("SELECT SUM(amount) as s FROM transactions")
    total_amount = cur.fetchone()["s"] or 0

    cur.execute("""
        SELECT t.txn_id, u1.name as sender, u2.name as receiver, t.amount,
               t.timestamp, t.risk_level, t.risk_score
        FROM transactions t
        JOIN users u1 ON t.sender_id = u1.user_id
        JOIN users u2 ON t.receiver_id = u2.user_id
        ORDER BY t.timestamp DESC LIMIT 8
    """)
    recent = cur.fetchall()

    conn.close()
    return render_template("dashboard.html",
                            total_txns=total_txns,
                            high_risk=high_risk,
                            medium_risk=medium_risk,
                            total_users=total_users,
                            total_amount=total_amount,
                            recent=recent)


@app.route("/transactions")
def transactions():
    risk_filter = request.args.get("risk", "All")
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT t.txn_id, u1.name as sender, u2.name as receiver, t.amount,
               t.timestamp, t.device_id, t.location, t.risk_level, t.risk_score
        FROM transactions t
        JOIN users u1 ON t.sender_id = u1.user_id
        JOIN users u2 ON t.receiver_id = u2.user_id
    """
    params = ()
    if risk_filter in ("Low", "Medium", "High"):
        query += " WHERE t.risk_level = ?"
        params = (risk_filter,)
    query += " ORDER BY t.timestamp DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return render_template("transactions.html", rows=rows, risk_filter=risk_filter)


@app.route("/flagged")
def flagged():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.flag_id, t.txn_id, u1.name as sender, u2.name as receiver,
               t.amount, t.timestamp, f.reason, f.risk_score, f.flagged_date
        FROM flagged_transactions f
        JOIN transactions t ON f.txn_id = t.txn_id
        JOIN users u1 ON t.sender_id = u1.user_id
        JOIN users u2 ON t.receiver_id = u2.user_id
        ORDER BY f.flagged_date DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return render_template("flagged.html", rows=rows)


@app.route("/new_transaction", methods=["GET", "POST"])
def new_transaction():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, name, upi_id FROM users ORDER BY name")
    users = cur.fetchall()

    result = None
    if request.method == "POST":
        sender_id = int(request.form["sender_id"])
        receiver_id = int(request.form["receiver_id"])
        amount = float(request.form["amount"])
        device_id = request.form["device_id"].strip()
        location = request.form["location"].strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, device_id, location)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sender_id, receiver_id, amount, timestamp, device_id, location))
        conn.commit()
        txn_id = cur.lastrowid

        score, level, reasons = evaluate_single_transaction(conn, txn_id)
        result = {"txn_id": txn_id, "score": score, "level": level, "reasons": reasons}

    conn.close()
    return render_template("new_transaction.html", users=users, result=result)


@app.route("/reports")
def reports():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT risk_level, COUNT(*) as c FROM transactions GROUP BY risk_level")
    data = {row["risk_level"]: row["c"] for row in cur.fetchall()}
    risk_labels = ["Low", "Medium","High"]
    risk_values = [data.get(l,0) for l in risk_labels]
    cur.execute("""
        SELECT substr(timestamp, 1, 10)as day, COUNT(*) as c
        FROM transactions
        WHERE risk_level = 'High'
        GROUP BY day
        ORDER BY day
    """)
    trend_rows = cur.fetchall()
    trend_days = [r["day"] for r in trend_rows]
    trend_counts = [r["c"] for r in trend_rows]
    conn.close()
    return render_template("reports.html",
                           risk_labels=risk_labels,
                           risk_values=risk_values,
                           trend_days=trend_days,
                           trend_counts=trend_counts)



@app.route("/rescan")
def rescan():
    conn = get_connection()
    evaluate_all_transactions(conn)
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/phishing_check", methods=["GET", "POST"])
def phishing_check():
    result = None
    history = []
    if request.method == "POST":
        url = request.form["url"].strip()
        score, level, reasons = score_url(url)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO checked_urls (url, risk_score, risk_level, reasons, checked_date)
            VALUES (?,?,?,?,?)
        """, (url, score, level, ";".join(reasons), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        result = {"url": url, "score":score, "level": level, "reasons":reasons}
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM checked_urls ORDER BY checked_date DESC LIMIT 10")
    history = cur.fetchall()
    conn.close()
    return render_template("phishing.html", result=result, history=history)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
