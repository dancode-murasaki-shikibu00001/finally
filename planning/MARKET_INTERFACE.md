# Market Data Interface Design

This document defines the unified Python interface for market data in FinAlly. All backend code that needs prices goes through this interface — never calls Massive or the simulator directly.

---

## Design Goals

1. **Single switch** — one environment variable (`MASSIVE_API_KEY`) selects the implementation; no code changes needed.
2. **Identical contract** — both implementations return identical data shapes so downstream code (SSE streaming, portfolio valuation, trade execution) never checks which provider is active.
3. **In-process background task** — a single polling loop updates a shared price cache; all SSE clients read from the cache rather than each making their own API calls.
4. **Graceful degradation** — if Massive returns an error, the last cached price is kept; no crash, no empty SSE events.

---

## Abstract Interface

```python
# backend/market/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class PriceQuote:
    """Canonical price record returned by both implementations."""
    ticker: str
    price: float            # Most recent trade price
    prev_close: float       # Previous session close (basis for daily % change)
    change_pct: float       # (price - prev_close) / prev_close * 100
    volume: float           # Today's cumulative volume (0.0 in simulator)
    timestamp_ms: int       # Unix milliseconds of last update


class MarketDataProvider(ABC):
    """Abstract base for market data sources."""

    @abstractmethod
    async def start(self, tickers: Sequence[str]) -> None:
        """Start background polling/simulation for the given tickers."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop background task cleanly."""

    @abstractmethod
    def get_price(self, ticker: str) -> PriceQuote | None:
        """Return the latest cached quote for ticker, or None if unknown."""

    @abstractmethod
    def get_all_prices(self) -> dict[str, PriceQuote]:
        """Return the full price cache as {ticker: PriceQuote}."""

    @abstractmethod
    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active polling set."""

    @abstractmethod
    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active polling set."""
```

### `PriceQuote` field notes

| Field         | Simulator source                          | Massive source                                      |
|--------------|-------------------------------------------|-----------------------------------------------------|
| `price`      | Current GBM price                         | `last_trade.price` (or `session.close`)             |
| `prev_close` | Seed price at simulator start             | `session.previous_close`                            |
| `change_pct` | Computed from seed price                  | `session.change_percent` (or computed)              |
| `volume`     | `0.0` (not simulated)                     | `session.volume`                                    |
| `timestamp_ms` | `time.time_ns() // 1_000_000`           | `last_trade.sip_timestamp` (or `updated`)           |

---

## Price Cache

Both implementations write to and expose a shared in-memory cache:

```python
# backend/market/cache.py

import threading
from .base import PriceQuote


class PriceCache:
    """Thread-safe in-memory store for the latest price per ticker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, PriceQuote] = {}

    def update(self, quote: PriceQuote) -> None:
        with self._lock:
            self._data[quote.ticker] = quote

    def get(self, ticker: str) -> PriceQuote | None:
        with self._lock:
            return self._data.get(ticker)

    def get_all(self) -> dict[str, PriceQuote]:
        with self._lock:
            return dict(self._data)

    def tickers(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())
```

---

## Factory Function

```python
# backend/market/factory.py

import os
from .base import MarketDataProvider
from .simulator import MarketSimulator
from .massive_client import MassiveClient


def create_market_provider() -> MarketDataProvider:
    """
    Return the appropriate MarketDataProvider based on environment config.
    Uses MassiveClient if MASSIVE_API_KEY is set and non-empty,
    otherwise falls back to MarketSimulator.
    """
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveClient(api_key=api_key)
    return MarketSimulator()
```

Usage in FastAPI startup:

```python
# backend/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from .market.factory import create_market_provider
from .db import get_watchlist_tickers

_provider: MarketDataProvider | None = None


def get_provider() -> MarketDataProvider:
    assert _provider is not None, "Provider not initialized"
    return _provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _provider
    tickers = get_watchlist_tickers()          # reads DB seed data
    _provider = create_market_provider()
    await _provider.start(tickers)
    yield
    await _provider.stop()


app = FastAPI(lifespan=lifespan)
```

---

## Massive Client Implementation

```python
# backend/market/massive_client.py

import asyncio
import time
import logging
from typing import Sequence

import requests

from .base import MarketDataProvider, PriceQuote
from .cache import PriceCache

logger = logging.getLogger(__name__)

BASE_URL = "https://api.massive.com"
POLL_INTERVAL = 15.0   # seconds — safe for free/starter tiers


class MassiveClient(MarketDataProvider):

    def __init__(self, api_key: str, poll_interval: float = POLL_INTERVAL) -> None:
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._cache = PriceCache()
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def start(self, tickers: Sequence[str]) -> None:
        self._tickers = set(tickers)
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------ #
    # Cache access                                                         #
    # ------------------------------------------------------------------ #

    def get_price(self, ticker: str) -> PriceQuote | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, PriceQuote]:
        return self._cache.get_all()

    def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker.upper())

    def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker.upper())

    # ------------------------------------------------------------------ #
    # Internal polling                                                     #
    # ------------------------------------------------------------------ #

    async def _poll_loop(self) -> None:
        while True:
            if self._tickers:
                try:
                    quotes = await asyncio.to_thread(self._fetch_snapshots, list(self._tickers))
                    for q in quotes:
                        self._cache.update(q)
                except Exception:
                    logger.exception("Massive poll failed; keeping last cached prices")
            await asyncio.sleep(self._poll_interval)

    def _fetch_snapshots(self, tickers: list[str]) -> list[PriceQuote]:
        resp = requests.get(
            f"{BASE_URL}/v3/snapshot",
            params={
                "apiKey": self._api_key,
                "ticker.any_of": ",".join(tickers),
                "limit": 250,
            },
            timeout=10,
        )
        resp.raise_for_status()
        now_ms = int(time.time() * 1000)

        quotes = []
        for r in resp.json().get("results", []):
            session = r.get("session", {})
            last_trade = r.get("last_trade", {})
            price = last_trade.get("price") or session.get("close") or 0.0
            prev_close = session.get("previous_close") or price
            change_pct = session.get("change_percent") or 0.0
            quotes.append(PriceQuote(
                ticker=r["ticker"],
                price=price,
                prev_close=prev_close,
                change_pct=change_pct,
                volume=session.get("volume") or 0.0,
                timestamp_ms=r.get("updated") or now_ms,
            ))
        return quotes
```

---

## Simulator Implementation (summary)

See `MARKET_SIMULATOR.md` for the full design. The simulator implements the same `MarketDataProvider` interface:

```python
# backend/market/simulator.py  (sketch)

class MarketSimulator(MarketDataProvider):
    def __init__(self) -> None:
        self._cache = PriceCache()
        self._tickers: dict[str, _TickerState] = {}
        self._task: asyncio.Task | None = None

    async def start(self, tickers: Sequence[str]) -> None:
        for t in tickers:
            self._tickers[t] = _TickerState.from_seed(t)
        self._task = asyncio.create_task(self._simulate_loop())

    async def stop(self) -> None: ...
    def get_price(self, ticker: str) -> PriceQuote | None: ...
    def get_all_prices(self) -> dict[str, PriceQuote]: ...
    def add_ticker(self, ticker: str) -> None: ...
    def remove_ticker(self, ticker: str) -> None: ...
```

---

## SSE Streaming

The SSE endpoint reads exclusively from the price cache:

```python
# backend/routes/stream.py

import asyncio
import json
from fastapi import Request
from fastapi.responses import StreamingResponse
from ..market.factory import get_provider


async def price_stream(request: Request):
    async def event_generator():
        while not await request.is_disconnected():
            prices = get_provider().get_all_prices()
            payload = {
                ticker: {
                    "ticker": q.ticker,
                    "price": q.price,
                    "prev_close": q.prev_close,
                    "change_pct": q.change_pct,
                    "timestamp_ms": q.timestamp_ms,
                }
                for ticker, q in prices.items()
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.5)   # push at ~2Hz regardless of poll cadence

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

Key point: the SSE loop runs at 500ms; the Massive poller runs at 15s. Clients get smooth updates from cache even though the upstream data refreshes less frequently.

---

## Trade Execution Price

`POST /api/portfolio/trade` fetches the current price for fill:

```python
def get_fill_price(ticker: str) -> float:
    quote = get_provider().get_price(ticker)
    if quote is None:
        raise ValueError(f"No price available for {ticker}")
    return quote.price
```

No staleness rejection is applied — if the cache has a price (even if 15 seconds old), the trade fills at that price. This is acceptable for a simulated single-user demo.

---

## Watchlist Sync

When the user adds/removes a ticker (via API or AI chat), the provider is notified immediately:

```python
# in the watchlist route handlers
provider = get_provider()
provider.add_ticker(ticker)    # on POST /api/watchlist
provider.remove_ticker(ticker) # on DELETE /api/watchlist/{ticker}
```

For the Massive client, the new ticker is included in the next poll cycle automatically because `_fetch_snapshots` reads from `self._tickers` at call time. For the simulator, `add_ticker` initializes a new `_TickerState` immediately so prices start appearing within the next 500ms SSE push.

---

## Directory Layout

```
backend/
└── market/
    ├── __init__.py
    ├── base.py          # PriceQuote dataclass, MarketDataProvider ABC
    ├── cache.py         # PriceCache (thread-safe dict wrapper)
    ├── factory.py       # create_market_provider() factory
    ├── massive_client.py  # MassiveClient implementation
    └── simulator.py     # MarketSimulator implementation
```
