import sqlite3
import os

# Create absolute DB path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, '..', 'database')
os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, 'recruitment.db')


def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ---------------- JOBS TABLE ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # ---------------- APPLICATIONS TABLE ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL,
            email TEXT NOT NULL,
            resume_path TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            score REAL NOT NULL,
            decision TEXT NOT NULL,
            evaluation_details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    conn.commit()
    conn.close()

    print("✅ recruitment.db created successfully!")


if __name__ == "__main__":
    init_database()
