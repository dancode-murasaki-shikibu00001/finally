"""
SSE streaming endpoint: GET /api/stream/prices

Pushes all ticker prices every 500ms to connected clients.
Each event contains ticker, price, prev_price, change_pct, direction, timestamp_ms.
"""

import asyncio
import json

from fastapi import APIRouter

from market.factory import get_provider

# Import EventSourceResponse lazily to allow the module to be imported even
# when sse-starlette is not yet installed (e.g. during testing stubs).
try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:  # pragma: no cover
    EventSourceResponse = None  # type: ignore[assignment,misc]

router = APIRouter()

PUSH_INTERVAL = 0.5  # seconds


async def _price_generator():
    """Async generator that yields SSE events every PUSH_INTERVAL seconds."""
    while True:
        try:
            provider = get_provider()
            all_prices = provider.get_all_prices()
            for ticker, quote in all_prices.items():
                if quote.price > quote.prev_close:
                    direction = "up"
                elif quote.price < quote.prev_close:
                    direction = "down"
                else:
                    direction = "unchanged"

                payload = {
                    "ticker": quote.ticker,
                    "price": quote.price,
                    "prev_price": quote.prev_close,
                    "change_pct": quote.change_pct,
                    "direction": direction,
                    "timestamp_ms": quote.timestamp_ms,
                }
                yield {"data": json.dumps(payload)}
        except RuntimeError:
            # Provider not yet initialized — yield a keepalive comment
            yield {"comment": "initializing"}

        await asyncio.sleep(PUSH_INTERVAL)


@router.get("/stream/prices")
async def stream_prices():
    """SSE endpoint — push all ticker prices every 500ms."""
    if EventSourceResponse is None:  # pragma: no cover
        raise RuntimeError(
            "sse-starlette is not installed. Run: uv add sse-starlette"
        )
    return EventSourceResponse(_price_generator())
