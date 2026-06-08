"""Watchlist REST endpoints: CRUD for the user's tracked tickers."""

from __future__ import annotations

import logging
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
    user_id = DEFAULT_USER_ID
    ticker = body.ticker.upper().strip()

    if not ticker:
        raise HTTPException(status_code=400, detail="ticker must not be empty")

    existing = db.execute(
        "SELECT added_at FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    ).fetchone()
    if existing:
        # WTCH-02: idempotent — already present is not an error
        return JSONResponse(
            status_code=200,
            content={"ticker": ticker, "added_at": existing["added_at"]},
        )

    now = datetime.now(timezone.utc).isoformat()
    with db:
        db.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, now),
        )

    await request.app.state.market_source.add_ticker(ticker)

    return {"ticker": ticker, "added_at": now}


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(ticker: str, request: Request, db: DbDep) -> None:
    user_id = DEFAULT_USER_ID
    ticker = ticker.upper()

    existing = db.execute(
        "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")

    with db:
        db.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )

    await request.app.state.market_source.remove_ticker(ticker)
