"""
Watchlist endpoints:
  GET    /api/watchlist        — list all tickers with latest prices
  POST   /api/watchlist        — add a ticker
  DELETE /api/watchlist/{ticker} — remove a ticker
"""

from fastapi import APIRouter, HTTPException

from db.init_db import get_connection
from db import queries as db
from market.factory import get_provider
from models import WatchlistAddRequest, WatchlistItem

router = APIRouter()
USER_ID = "default"


@router.get("/watchlist", response_model=list[WatchlistItem])
def get_watchlist():
    """Return all watched tickers with their latest prices."""
    with get_connection() as conn:
        entries = db.get_watchlist(conn, USER_ID)

    provider = get_provider()
    result = []
    for entry in entries:
        ticker = entry["ticker"]
        quote = provider.get_price(ticker)
        result.append(
            WatchlistItem(
                ticker=ticker,
                price=quote.price if quote else None,
                change_pct=quote.change_pct if quote else None,
            )
        )
    return result


@router.post("/watchlist", response_model=WatchlistItem, status_code=201)
def add_to_watchlist(body: WatchlistAddRequest):
    """Add a ticker to the watchlist and start streaming its prices."""
    ticker = body.ticker  # already uppercased by validator

    with get_connection() as conn:
        added = db.add_watchlist_ticker(conn, USER_ID, ticker)
        if not added:
            raise HTTPException(status_code=400, detail=f"{ticker} is already in the watchlist")

    # Tell the market provider to start tracking this ticker
    provider = get_provider()
    provider.add_ticker(ticker)

    quote = provider.get_price(ticker)
    return WatchlistItem(
        ticker=ticker,
        price=quote.price if quote else None,
        change_pct=quote.change_pct if quote else None,
    )


@router.delete("/watchlist/{ticker}", status_code=204)
def remove_from_watchlist(ticker: str):
    """Remove a ticker from the watchlist and stop streaming its prices."""
    ticker = ticker.strip().upper()

    with get_connection() as conn:
        removed = db.remove_watchlist_ticker(conn, USER_ID, ticker)
        if not removed:
            raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")

    # Tell the market provider to stop tracking this ticker
    provider = get_provider()
    provider.remove_ticker(ticker)
