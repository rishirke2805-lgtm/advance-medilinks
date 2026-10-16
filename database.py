import os
import sqlite3
from config import Config

def get_db():
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create table if it doesn't exist and run non-destructive schema migrations."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                city TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Ensure city column exists for existing databases
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(registrations)").fetchall()]
        if "city" not in columns:
            conn.execute("ALTER TABLE registrations ADD COLUMN city TEXT DEFAULT '';")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_email ON registrations(email);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_created ON registrations(created_at);")
