import sqlite3
import os
DB_NAME = os.path.join(os.path.dirname(__file__),"upi_fraud.db")
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
         user_id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL,
         upi_id TEXT UNIQUE NOT NULL,
         bank_account TEXT NOT NULL,
         registered_date TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS user_devices(
         device_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id INTEGER NOT NULL,
         device_id TEXT NOT NULL,
         first_used_date TEXT NOT NULL,
         FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    CREATE TABLE IF NOT EXISTS transactions(
         txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
         sender_id INTEGER NOT NULL,
         receiver_id INTEGER NOT NULL,
         amount REAL NOT NULL,
         timestamp TEXT NOT NULL,
         device_id TEXT NOT NULL,
         location TEXT NOT NULL,
         risk_score INTEGER DEFAULT 0,
         risk_level TEXT DEFAULT 'Low',
         FOREIGN KEY (sender_id) REFERENCES users(user_id),
         FOREIGN KEY (receiver_id) REFERENCES users(user_id)
    );
    CREATE TABLE IF NOT EXISTS flagged_transactions(
         flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
         txn_id INTEGER NOT NULL,
         reason TEXT NOT NULL,
         risk_score INTEGER NOT NULL,
         flagged_date TEXT NOT NULL,
         FOREIGN KEY (txn_id) REFERENCES transactions(txn_id)
    );
    CREATE TABLE IF NOT EXISTS checked_urls(
         check_id INTEGER PRIMARY KEY AUTOINCREMENT,
         url TEXT NOT NULL,
         risk_score INTEGER NOT NULL,
         risk_level TEXT NOT NULL,
         reasons TEXT NOT NULL,
         checked_date TEXT NOT NULL
     );
    """)
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_NAME}")
if __name__ == "__main__":
    init_db()