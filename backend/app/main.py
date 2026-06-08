"""FinAlly FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from app.db import get_db_path, init_db
from app.market import PriceCache, create_market_data_source, stream_router
from app.market.seed_prices import SEED_PRICES
from app.routers import chat_router, portfolio_router, watchlist_router
from app.snapshots import snapshot_task

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and market data on startup, clean up on shutdown."""
    logger.info("Starting FinAlly backend...")

    init_db()

    cache = PriceCache()
    source = create_market_data_source(cache)
    tickers = list(SEED_PRICES.keys())
    await source.start(tickers)
    logger.info("Market data source started with %d tickers", len(tickers))

    app.state.price_cache = cache
    app.state.market_source = source

    snap_task = asyncio.create_task(snapshot_task(cache))

    yield

    snap_task.cancel()
    try:
        await snap_task
    except asyncio.CancelledError:
        pass

    logger.info("Stopping market data source...")
    await source.stop()
    logger.info("FinAlly backend stopped.")


app = FastAPI(
    title="FinAlly",
    description="AI Trading Workstation",
    lifespan=lifespan,
)

app.include_router(stream_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/debug/reset")
async def debug_reset(request: Request):
    """Reset DB to initial seed state. Only available when LLM_MOCK=true (test mode)."""
    if os.environ.get("LLM_MOCK", "").lower() != "true":
        raise HTTPException(status_code=403, detail="Only available in test mode")
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            DROP TABLE IF EXISTS users_profile;
            DROP TABLE IF EXISTS watchlist;
            DROP TABLE IF EXISTS positions;
            DROP TABLE IF EXISTS trades;
            DROP TABLE IF EXISTS portfolio_snapshots;
            DROP TABLE IF EXISTS chat_messages;
        """)
    finally:
        conn.close()
    init_db()
    # Re-add seed tickers to market source so prices flow after any remove_ticker calls
    for ticker in SEED_PRICES:
        await request.app.state.market_source.add_ticker(ticker)
    return {"ok": True}


# Serve the Next.js static export — must be mounted LAST so API routes take priority.
# The `static/` directory is populated by the Docker multi-stage build.
_static_dir = Path(__file__).parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
