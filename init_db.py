"""
Creates personal_assistant.db from schema.sql and seeds it with a few
sample rows, so the MCP servers have real data to query from day one.

Run it with:
    python init_db.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "personal_assistant.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # Idempotent: skip seeding if the database already has data.
    cur.execute("SELECT COUNT(*) FROM tasks")
    if cur.fetchone()[0] > 0:
        print("Database already has data — skipping seed.")
        return

    cur.executemany(
        "INSERT INTO tasks (title, due_date, priority) VALUES (?, ?, ?)",
        [
            ("Finish MCP tutorial", "2026-09-23", "high"),
            ("Pay internet bill", "2026-09-25", "medium"),
            ("Buy birthday gift", "2026-09-30", "low"),
        ],
    )

    cur.executemany(
        "INSERT INTO events (title, start_time, end_time, location) VALUES (?, ?, ?, ?)",
        [
            ("Dentist appointment", "2026-09-24 10:00", "2026-09-24 11:00", "Dental clinic"),
            ("Team sync", "2026-09-22 09:00", "2026-09-22 09:30", "Zoom"),
        ],
    )

    cur.executemany(
        "INSERT INTO transactions (amount, category, description, date) VALUES (?, ?, ?, ?)",
        [
            (-45.20, "food", "Groceries", "2026-09-19"),
            (-12.00, "transport", "Bus pass", "2026-09-18"),
            (1500.00, "income", "Freelance payment", "2026-09-15"),
        ],
    )

    conn.commit()
    print(f"Seeded {DB_PATH.name} with sample tasks, events, and transactions.")


if __name__ == "__main__":
    connection = init_db()
    seed(connection)
    connection.close()
