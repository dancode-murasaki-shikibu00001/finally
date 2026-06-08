"""Database initialization and connection management for FinAlly."""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0.0,
    avg_cost REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
);
"""

DEFAULT_USER_ID = "default"


def get_db_path() -> str:
    """Return the SQLite database path from DB_PATH env var or default."""
    return os.environ.get("DB_PATH", "db/finally.db")


def init_db() -> None:
    """Initialize the database: create tables and seed default data.

    Safe to call on every startup — CREATE TABLE IF NOT EXISTS and
    INSERT OR IGNORE make this idempotent.
    """
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    logger.info("Initializing database at %s", db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)  # DDL — do NOT wrap in `with conn:`
        _seed_default_data(conn)
    finally:
        conn.close()


def _seed_default_data(conn: sqlite3.Connection) -> None:
    """Insert default user and watchlist if not already present."""
    from app.market.seed_prices import SEED_PRICES  # local import to avoid circular

    now = datetime.now(timezone.utc).isoformat()

    with conn:  # auto-commit context manager for DML
        conn.execute(
            "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, 10000.0, now),
        )
        for ticker in SEED_PRICES:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
            )


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield one sqlite3 connection per request, then close it."""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


DbDep = Annotated[sqlite3.Connection, Depends(get_db)]
