"""
Database initialisation helpers.

get_db_path()  — resolve the SQLite file path from DB_PATH env var
get_connection() — open a connection with row_factory=sqlite3.Row
init_db()       — create tables + seed default data (idempotent)
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from db.schema import ALL_TABLES

# ---------------------------------------------------------------------------
# Default watchlist tickers (seeded on first start)
# ---------------------------------------------------------------------------
DEFAULT_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]


def _utcnow() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def get_db_path() -> str:
    """
    Return the SQLite database file path.

    Reads the DB_PATH environment variable; defaults to "db/finally.db"
    relative to the current working directory.
    """
    return os.environ.get("DB_PATH", "db/finally.db")


def get_connection() -> sqlite3.Connection:
    """
    Open and return a sqlite3 connection with row_factory=sqlite3.Row.

    Creates the parent directory if it does not yet exist so the caller
    never has to worry about the directory structure.
    """
    db_path = get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """
    Idempotently create all tables and seed default data.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS and
    INSERT OR IGNORE / existence checks so re-running never duplicates data.
    """
    conn = get_connection()
    try:
        with conn:
            # 1. Create all tables
            for ddl in ALL_TABLES:
                conn.execute(ddl)

            # 2. Seed default user profile if not present
            conn.execute(
                """
                INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at)
                VALUES (?, ?, ?)
                """,
                ("default", 10000.0, _utcnow()),
            )

            # 3. Seed default watchlist tickers if watchlist is empty
            row = conn.execute(
                "SELECT COUNT(*) FROM watchlist WHERE user_id = 'default'"
            ).fetchone()
            if row[0] == 0:
                for ticker in DEFAULT_TICKERS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)
                        VALUES (?, 'default', ?, ?)
                        """,
                        (str(uuid.uuid4()), ticker, _utcnow()),
                    )
    finally:
        conn.close()
