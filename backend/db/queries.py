"""
Database query functions for the FinAlly backend.

All functions are synchronous (sqlite3, no async).  FastAPI route handlers
should call these via asyncio.get_event_loop().run_in_executor() or a
thread-pool executor so the async event loop is not blocked.

Every function accepts an open sqlite3.Connection as its first argument so
connection lifetime is controlled by the caller.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlite3


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _rows_to_dicts(rows) -> list[dict]:
    """Convert a list of sqlite3.Row objects to plain dicts."""
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

def get_user_profile(conn: sqlite3.Connection, user_id: str = "default") -> dict:
    """
    Return the user profile row as a dict.
    Raises KeyError if the user does not exist.
    """
    row = conn.execute(
        "SELECT * FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"User '{user_id}' not found")
    return _row_to_dict(row)


def update_cash_balance(
    conn: sqlite3.Connection, user_id: str, new_balance: float
) -> None:
    """Overwrite the cash_balance for the given user."""
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (new_balance, user_id),
    )


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def get_watchlist(conn: sqlite3.Connection, user_id: str = "default") -> list[dict]:
    """Return all watchlist entries for the user, ordered by added_at ASC."""
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
        (user_id,),
    ).fetchall()
    return _rows_to_dicts(rows)


def add_watchlist_ticker(
    conn: sqlite3.Connection, user_id: str, ticker: str
) -> bool:
    """
    Add a ticker to the user's watchlist.

    Returns True on success, False if the ticker is already in the watchlist.
    """
    ticker = ticker.upper().strip()
    try:
        conn.execute(
            """
            INSERT INTO watchlist (id, user_id, ticker, added_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), user_id, ticker, _utcnow()),
        )
        return True
    except sqlite3.IntegrityError:
        # UNIQUE (user_id, ticker) constraint violated
        return False


def remove_watchlist_ticker(
    conn: sqlite3.Connection, user_id: str, ticker: str
) -> bool:
    """
    Remove a ticker from the user's watchlist.

    Returns True if a row was deleted, False if the ticker was not found.
    """
    ticker = ticker.upper().strip()
    cursor = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

def get_positions(conn: sqlite3.Connection, user_id: str = "default") -> list[dict]:
    """Return all open positions for the user, ordered by ticker ASC."""
    rows = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker ASC",
        (user_id,),
    ).fetchall()
    return _rows_to_dicts(rows)


def get_position(
    conn: sqlite3.Connection, user_id: str, ticker: str
) -> Optional[dict]:
    """Return a single position row, or None if not held."""
    ticker = ticker.upper().strip()
    row = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return _row_to_dict(row) if row else None


def upsert_position(
    conn: sqlite3.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    avg_cost: float,
) -> None:
    """
    Insert or replace a position row.

    Uses INSERT OR REPLACE so both new positions and updates to existing
    ones work with a single call.
    """
    ticker = ticker.upper().strip()
    # Check for an existing row so we can reuse its UUID on update
    existing = conn.execute(
        "SELECT id FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    row_id = existing["id"] if existing else str(uuid.uuid4())
    conn.execute(
        """
        INSERT OR REPLACE INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row_id, user_id, ticker, quantity, avg_cost, _utcnow()),
    )


def delete_position(
    conn: sqlite3.Connection, user_id: str, ticker: str
) -> None:
    """Remove a position row (called when quantity reaches zero)."""
    ticker = ticker.upper().strip()
    conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

def record_trade(
    conn: sqlite3.Connection,
    user_id: str,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
) -> str:
    """
    Append a trade to the trade log.

    Returns the new trade's UUID.
    """
    ticker = ticker.upper().strip()
    trade_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (trade_id, user_id, ticker, side, quantity, price, _utcnow()),
    )
    return trade_id


def get_trades(
    conn: sqlite3.Connection, user_id: str = "default", limit: int = 100
) -> list[dict]:
    """Return the most recent trades for a user, newest first."""
    rows = conn.execute(
        """
        SELECT * FROM trades
        WHERE user_id = ?
        ORDER BY executed_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Portfolio snapshots
# ---------------------------------------------------------------------------

def record_portfolio_snapshot(
    conn: sqlite3.Connection, user_id: str, total_value: float
) -> str:
    """
    Record a portfolio value snapshot.

    Also prunes snapshots older than 24 hours to keep the table bounded.
    Returns the new snapshot's UUID.
    """
    snapshot_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
        VALUES (?, ?, ?, ?)
        """,
        (snapshot_id, user_id, total_value, _utcnow()),
    )
    # Prune old data to prevent unbounded growth
    prune_old_snapshots(conn, user_id)
    return snapshot_id


def get_portfolio_snapshots(
    conn: sqlite3.Connection,
    user_id: str = "default",
    limit: int = 288,  # 288 = 24 hours at 30-second intervals
) -> list[dict]:
    """
    Return the most recent `limit` portfolio snapshots, ordered oldest-first
    so callers can plot a time series directly.
    """
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM portfolio_snapshots
            WHERE user_id = ?
            ORDER BY recorded_at DESC
            LIMIT ?
        ) sub
        ORDER BY recorded_at ASC
        """,
        (user_id, limit),
    ).fetchall()
    return _rows_to_dicts(rows)


def prune_old_snapshots(
    conn: sqlite3.Connection, user_id: str, keep_hours: int = 24
) -> None:
    """Delete snapshots older than `keep_hours` hours for the given user."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=keep_hours)
    ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    conn.execute(
        """
        DELETE FROM portfolio_snapshots
        WHERE user_id = ? AND recorded_at < ?
        """,
        (user_id, cutoff),
    )


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------

def get_chat_messages(
    conn: sqlite3.Connection,
    user_id: str = "default",
    limit: int = 20,
) -> list[dict]:
    """
    Return the last `limit` chat messages for the user, ordered oldest-first
    (i.e. chronological order suitable for rendering a conversation).
    """
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ) sub
        ORDER BY created_at ASC
        """,
        (user_id, limit),
    ).fetchall()
    # Deserialise the actions JSON field if present
    result = []
    for row in rows:
        d = _row_to_dict(row)
        if d.get("actions"):
            try:
                d["actions"] = json.loads(d["actions"])
            except (json.JSONDecodeError, TypeError):
                pass  # leave as raw string if unparseable
        result.append(d)
    return result


def add_chat_message(
    conn: sqlite3.Connection,
    user_id: str,
    role: str,
    content: str,
    actions=None,
) -> str:
    """
    Persist a chat message and return its UUID.

    `actions` may be a dict/list (will be JSON-serialised) or None.
    """
    message_id = str(uuid.uuid4())
    actions_json = json.dumps(actions) if actions is not None else None
    conn.execute(
        """
        INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (message_id, user_id, role, content, actions_json, _utcnow()),
    )
    return message_id
