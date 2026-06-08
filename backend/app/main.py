"""FinAlly FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
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
