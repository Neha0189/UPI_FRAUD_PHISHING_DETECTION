import random
from datetime import datetime, timedelta
from database import get_connection

FIRST_NAMES = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Karan",
               "Neha", "Rohan", "Pooja", "Arjun", "Divya", "Sanjay", "Kavita"]
LAST_NAMES = ["Sharma", "Verma", "Patel", "Singh", "Gupta", "Reddy", "Iyer",
              "Mehta", "Joshi", "Nair"]
CITIES = ["Mumbai", "Delhi", "Bangalore", "Pune", "Hyderabad", "Chennai",
          "Kolkata", "Ahmedabad"]


def random_date(days_back=90):
    return datetime.now() - timedelta(days=random.randint(0, days_back),
                                       hours=random.randint(0, 23),
                                       minutes=random.randint(0, 59))


def generate_users(conn, n=30):
    cur = conn.cursor()
    user_ids = []
    for i in range(n):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        upi_id = f"{name.split()[0].lower()}{i}{random.randint(100,999)}@upi"
        bank_account = f"AC{random.randint(100000000, 999999999)}"
        reg_date = random_date(365).strftime("%Y-%m-%d")
        cur.execute(
            "INSERT INTO users (name, upi_id, bank_account, registered_date) VALUES (?, ?, ?, ?)",
            (name, upi_id, bank_account, reg_date)
        )
        user_ids.append(cur.lastrowid)

        for _ in range(random.randint(1, 2)):
            device_id = f"DEV{random.randint(1000,9999)}"
            cur.execute(
                "INSERT INTO user_devices (user_id, device_id, first_used_date) VALUES (?, ?, ?)",
                (user_ids[-1], device_id, reg_date)
            )
    conn.commit()
    return user_ids


def get_known_devices(conn, user_id):
    cur = conn.cursor()
    cur.execute("SELECT device_id FROM user_devices WHERE user_id = ?", (user_id,))
    return [row["device_id"] for row in cur.fetchall()]


def generate_transactions(conn, user_ids, n=300, fraud_ratio=0.12):
    cur = conn.cursor()
    num_fraud = int(n * fraud_ratio)
    num_normal = n - num_fraud

    for _ in range(num_normal):
        sender = random.choice(user_ids)
        receiver = random.choice([u for u in user_ids if u != sender])
        amount = round(random.uniform(50, 3000), 2)
        ts = random_date(60)
        devices = get_known_devices(conn, sender)
        device_id = random.choice(devices) if devices else f"DEV{random.randint(1000,9999)}"
        ts = ts.replace(hour=random.randint(7, 22))
        location = random.choice(CITIES)

        cur.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, device_id, location)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sender, receiver, amount, ts.strftime("%Y-%m-%d %H:%M:%S"), device_id, location))

    for _ in range(num_fraud):
        sender = random.choice(user_ids)
        receiver = random.choice([u for u in user_ids if u != sender])
        ts = random_date(60)
        location = random.choice(CITIES)

        pattern = random.choice(["high_amount", "odd_hour", "new_device", "rapid_fire"])

        if pattern == "high_amount":
            amount = round(random.uniform(40000, 100000), 2)
            if random.random() < 0.5:
                device_id = f"DEV{random.randint(9000,9999)}X"
            else:
                devices = get_known_devices(conn, sender)
                device_id = random.choice(devices) if devices else f"DEV{random.randint(1000,9999)}"
            ts = ts.replace(hour=random.randint(10, 20))

        elif pattern == "odd_hour":
            amount = round(random.uniform(15000, 35000), 2)
            devices = get_known_devices(conn, sender)
            device_id = random.choice(devices) if devices else f"DEV{random.randint(1000,9999)}"
            ts = ts.replace(hour=random.choice([1, 2, 3, 4]))

        elif pattern == "new_device":
            amount = round(random.uniform(10000, 30000), 2)
            device_id = f"DEV{random.randint(9000,9999)}X"
            ts = ts.replace(hour=random.randint(9, 21))

        else:  # rapid_fire
            amount = round(random.uniform(500, 4000), 2)
            devices = get_known_devices(conn, sender)
            device_id = random.choice(devices) if devices else f"DEV{random.randint(1000,9999)}"
            base_ts = ts
            for burst in range(4):
                burst_ts = base_ts + timedelta(minutes=burst * 2)
                cur.execute("""
                    INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, device_id, location)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sender, receiver, amount, burst_ts.strftime("%Y-%m-%d %H:%M:%S"), device_id, location))
            conn.commit()
            continue

        cur.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, device_id, location)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sender, receiver, amount, ts.strftime("%Y-%m-%d %H:%M:%S"), device_id, location))

    conn.commit()


if __name__ == "__main__":
    conn = get_connection()
    print("Generating users...")
    users = generate_users(conn, n=30)
    print(f"Created {len(users)} users.")
    print("Generating transactions...")
    generate_transactions(conn, users, n=300, fraud_ratio=0.12)
    print("Done. Sample data is ready in upi_fraud.db")
    conn.close()