"""
FinAlly database package.

Public surface:
    init_db        — create tables and seed default data (idempotent)
    get_connection — open a sqlite3 connection (row_factory=sqlite3.Row)

    Query functions — all accept an open connection as their first argument.
    See db/queries.py for full docstrings.
"""

from db.init_db import init_db, get_connection, get_db_path
from db.queries import (
    # User profile
    get_user_profile,
    update_cash_balance,
    # Watchlist
    get_watchlist,
    add_watchlist_ticker,
    remove_watchlist_ticker,
    # Positions
    get_positions,
    get_position,
    upsert_position,
    delete_position,
    # Trades
    record_trade,
    get_trades,
    # Portfolio snapshots
    record_portfolio_snapshot,
    get_portfolio_snapshots,
    prune_old_snapshots,
    # Chat messages
    get_chat_messages,
    add_chat_message,
)

__all__ = [
    # Init / connection
    "init_db",
    "get_connection",
    "get_db_path",
    # User profile
    "get_user_profile",
    "update_cash_balance",
    # Watchlist
    "get_watchlist",
    "add_watchlist_ticker",
    "remove_watchlist_ticker",
    # Positions
    "get_positions",
    "get_position",
    "upsert_position",
    "delete_position",
    # Trades
    "record_trade",
    "get_trades",
    # Portfolio snapshots
    "record_portfolio_snapshot",
    "get_portfolio_snapshots",
    "prune_old_snapshots",
    # Chat messages
    "get_chat_messages",
    "add_chat_message",
]
