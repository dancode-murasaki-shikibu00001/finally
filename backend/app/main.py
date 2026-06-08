"""FinAlly FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.market import PriceCache, create_market_data_source, stream_router
from app.market.seed_prices import SEED_PRICES

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and market data on startup, clean up on shutdown."""
    logger.info("Starting FinAlly backend...")

    # 1. Initialize database (idempotent — CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE)
    init_db()

    # 2. Build shared objects — stored on app.state, not module-level globals (D-07)
    cache = PriceCache()
    source = create_market_data_source(cache)
    tickers = list(SEED_PRICES.keys())
    await source.start(tickers)
    logger.info("Market data source started with %d tickers", len(tickers))

    # 3. Store on app.state — NO module-level globals (D-07)
    app.state.price_cache = cache
    app.state.market_source = source

    yield  # Application is running

    # Shutdown
    logger.info("Stopping market data source...")
    await source.stop()
    logger.info("FinAlly backend stopped.")


app = FastAPI(
    title="FinAlly",
    description="AI Trading Workstation",
    lifespan=lifespan,
)

app.include_router(stream_router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint for Docker and deployment readiness."""
    return {"status": "ok"}
