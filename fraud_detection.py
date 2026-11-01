from datetime import datetime
from database import get_connection

HIGH_AMOUNT_THRESHOLD = 20000
ODD_HOURS = set([0, 1, 2, 3, 4, 5])
RAPID_WINDOW_MINUTES = 10
RAPID_COUNT_THRESHOLD = 3

RISK_LEVELS = {
    "Low": (0, 3),
    "Medium": (4, 7),
    "High": (8, 100),
}


def classify_score(score):
    for level, (low, high) in RISK_LEVELS.items():
        if low <= score <= high:
            return level
    return "Low"


def get_user_avg_amount(conn, user_id, exclude_txn_id=None):
    cur = conn.cursor()
    cur.execute("""
        SELECT AVG(amount) as avg_amt FROM transactions
        WHERE sender_id = ? AND txn_id != COALESCE(?, -1)
    """, (user_id, exclude_txn_id))
    row = cur.fetchone()
    return row["avg_amt"] if row and row["avg_amt"] else 0


def is_known_device(conn, user_id, device_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM user_devices WHERE user_id = ? AND device_id = ?
    """, (user_id, device_id))
    return cur.fetchone() is not None


def count_recent_transactions(conn, user_id, timestamp_str, exclude_txn_id=None):
    cur = conn.cursor()
    ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    cur.execute("""
        SELECT timestamp FROM transactions
        WHERE sender_id = ? AND txn_id != COALESCE(?, -1)
    """, (user_id, exclude_txn_id))
    count = 0
    for row in cur.fetchall():
        other_ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
        diff_minutes = abs((ts - other_ts).total_seconds()) / 60
        if diff_minutes <= RAPID_WINDOW_MINUTES:
            count += 1
    return count


def score_transaction(conn, txn):
    score = 0
    reasons = []

    if txn["amount"] >= HIGH_AMOUNT_THRESHOLD:
        score += 3
        reasons.append(f"High transaction amount (₹{txn['amount']:.2f})")

    avg_amt = get_user_avg_amount(conn, txn["sender_id"], exclude_txn_id=txn["txn_id"])
    if avg_amt and txn["amount"] >= avg_amt * 5:
        score += 3
        reasons.append(f"Amount is {txn['amount']/avg_amt:.1f}x the user's average spend")

    if not is_known_device(conn, txn["sender_id"], txn["device_id"]):
        score += 3
        reasons.append("Transaction made from an unrecognized device")

    ts = datetime.strptime(txn["timestamp"], "%Y-%m-%d %H:%M:%S")
    if ts.hour in ODD_HOURS:
        score += 2
        reasons.append(f"Unusual transaction time ({ts.strftime('%I:%M %p')})")

    recent_count = count_recent_transactions(conn, txn["sender_id"], txn["timestamp"],
                                              exclude_txn_id=txn["txn_id"])
    if recent_count >= RAPID_COUNT_THRESHOLD:
        score += 3
        reasons.append(f"{recent_count} other transactions within {RAPID_WINDOW_MINUTES} minutes")

    return score, reasons


def evaluate_all_transactions(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions")
    txns = cur.fetchall()

    for txn in txns:
        score, reasons = score_transaction(conn, txn)
        level = classify_score(score)

        cur.execute("""
            UPDATE transactions SET risk_score = ?, risk_level = ? WHERE txn_id = ?
        """, (score, level, txn["txn_id"]))

        if level == "High":
            cur.execute("SELECT 1 FROM flagged_transactions WHERE txn_id = ?", (txn["txn_id"],))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO flagged_transactions (txn_id, reason, risk_score, flagged_date)
                    VALUES (?, ?, ?, ?)
                """, (txn["txn_id"], "; ".join(reasons), score,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()


def evaluate_single_transaction(conn, txn_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
    txn = cur.fetchone()
    if not txn:
        return None

    score, reasons = score_transaction(conn, txn)
    level = classify_score(score)

    cur.execute("""
        UPDATE transactions SET risk_score = ?, risk_level = ? WHERE txn_id = ?
    """, (score, level, txn_id))

    if level == "High":
        cur.execute("SELECT 1 FROM flagged_transactions WHERE txn_id = ?", (txn_id,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO flagged_transactions (txn_id, reason, risk_score, flagged_date)
                VALUES (?, ?, ?, ?)
            """, (txn_id, "; ".join(reasons), score,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    return score, level, reasons


if __name__ == "__main__":
    conn = get_connection()
    print("Scoring all transactions...")
    evaluate_all_transactions(conn)
    print("Done.")
    conn.close()