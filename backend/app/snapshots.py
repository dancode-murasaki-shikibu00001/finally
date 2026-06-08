"""Background task: record portfolio value snapshots every 30 seconds."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from app.db import DEFAULT_USER_ID, get_db_path

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL = 30


async def snapshot_task(cache) -> None:
    """Periodically record total portfolio value into portfolio_snapshots."""
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        try:
            _take_snapshot(cache)
        except Exception:
            logger.exception("Portfolio snapshot failed")


def _take_snapshot(cache) -> None:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
        ).fetchone()
        if row is None:
            return

        cash_balance = row["cash_balance"]
        pos_rows = conn.execute(
            "SELECT ticker, quantity FROM positions WHERE user_id = ? AND quantity > 0",
            (DEFAULT_USER_ID,),
        ).fetchall()
        positions_value = sum(
            (cache.get_price(r["ticker"]) or 0.0) * r["quantity"] for r in pos_rows
        )
        total_value = cash_balance + positions_value
        now = datetime.now(timezone.utc).isoformat()

        with conn:
            conn.execute(
                "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)"
                " VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, total_value, now),
            )
        logger.debug("Snapshot: total_value=%.2f", total_value)
    finally:
        conn.close()
