"""Watchlist REST endpoints: CRUD for the user's tracked tickers."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db import DEFAULT_USER_ID, DbDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    ticker: str


async def add_ticker_logic(
    conn: sqlite3.Connection,
    market_source,
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Add a ticker to the watchlist; idempotent (WTCH-02).

    Returns a dict with ticker and added_at. Calls market_source.add_ticker
    only when the ticker is newly added.
    """
    ticker = ticker.upper().strip()
    existing = conn.execute(
        "SELECT added_at FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    ).fetchone()
    if existing:
        return {"ticker": ticker, "added_at": existing["added_at"], "created": False}

    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, now),
        )
    await market_source.add_ticker(ticker)
    return {"ticker": ticker, "added_at": now, "created": True}


async def remove_ticker_logic(
    conn: sqlite3.Connection,
    market_source,
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
) -> bool:
    """Remove a ticker from the watchlist. Returns True if removed, False if not found."""
    ticker = ticker.upper()
    existing = conn.execute(
        "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    ).fetchone()
    if not existing:
        return False
    with conn:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
    await market_source.remove_ticker(ticker)
    return True


@router.get("")
async def get_watchlist(request: Request, db: DbDep) -> dict:
    cache = request.app.state.price_cache
    user_id = DEFAULT_USER_ID

    rows = db.execute(
        "SELECT ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
        (user_id,),
    ).fetchall()

    tickers = []
    for r in rows:
        ticker = r["ticker"]
        update = cache.get(ticker)
        tickers.append(
            {
                "ticker": ticker,
                "price": update.price if update else None,
                "change": round(update.change, 4) if update else None,
                "change_percent": round(update.change_percent, 4) if update else None,
                "direction": update.direction if update else None,
                "added_at": r["added_at"],
            }
        )

    return {"tickers": tickers}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(body: AddTickerRequest, request: Request, db: DbDep) -> dict:
    ticker = body.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker must not be empty")

    result = await add_ticker_logic(db, request.app.state.market_source, ticker)
    if not result["created"]:
        # WTCH-02: idempotent — already present is not an error
        return JSONResponse(
            status_code=200,
            content={"ticker": result["ticker"], "added_at": result["added_at"]},
        )
    return {"ticker": result["ticker"], "added_at": result["added_at"]}


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(ticker: str, request: Request, db: DbDep) -> None:
    removed = await remove_ticker_logic(db, request.app.state.market_source, ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} not found in watchlist")
