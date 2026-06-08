"""
FinAlly FastAPI application entry point.

Lifespan:
  - Initialises SQLite DB (creates tables + seeds if needed)
  - Starts market data provider (simulator or Massive API)
  - Launches background portfolio snapshot task

Routes:
  /api/health           — health check
  /api/stream/prices    — SSE price stream
  /api/watchlist        — watchlist CRUD
  /api/portfolio        — portfolio read + trade + history
  /api/chat             — LLM chat

Static files (Next.js export) are served from ./static/ under the root path.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db.init_db import init_db, get_connection
from db import queries as db
from market.factory import create_market_provider, init_provider, get_provider
from routers import health, stream, watchlist, portfolio, chat

logger = logging.getLogger(__name__)

USER_ID = "default"
SNAPSHOT_INTERVAL = 30  # seconds


async def snapshot_loop():
    """
    Background task: record a portfolio snapshot every SNAPSHOT_INTERVAL seconds.
    Runs until cancelled during application shutdown.
    """
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        try:
            provider = get_provider()
            with get_connection() as conn:
                profile = db.get_user_profile(conn, USER_ID)
                cash_balance = profile["cash_balance"]
                positions = db.get_positions(conn, USER_ID)

            invested_value = 0.0
            for pos in positions:
                quote = provider.get_price(pos["ticker"])
                price = quote.price if quote else pos["avg_cost"]
                invested_value += price * pos["quantity"]

            total_value = cash_balance + invested_value

            with get_connection() as conn:
                db.record_portfolio_snapshot(conn, USER_ID, total_value)

        except Exception as exc:
            logger.warning("snapshot_loop error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup → yield → shutdown."""
    # ---- Startup ----
    init_db()
    logger.info("Database initialised")

    provider = create_market_provider()

    # Seed the provider with tickers already on the watchlist
    with get_connection() as conn:
        watchlist_rows = db.get_watchlist(conn)
    tickers = [row["ticker"] for row in watchlist_rows]
    await provider.start(tickers)
    init_provider(provider)
    logger.info("Market provider started with %d tickers", len(tickers))

    # Start background snapshot task
    task = asyncio.create_task(snapshot_loop())

    yield

    # ---- Shutdown ----
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await provider.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title="FinAlly API",
    description="AI-powered trading workstation backend",
    version="0.1.0",
    lifespan=lifespan,
)

# ----- API Routers -----
app.include_router(health.router, prefix="/api")
app.include_router(stream.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# ----- Static files (Next.js export) -----
# In Docker the build step copies frontend/out → /app/static/
# In local dev: frontend/out (created by `npm run build`)
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
else:
    logger.warning(
        "Static directory '%s' not found — frontend not served. "
        "Run `npm run build` inside frontend/ first.",
        _static_dir,
    )
