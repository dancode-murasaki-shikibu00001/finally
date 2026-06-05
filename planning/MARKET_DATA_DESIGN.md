# Market Data Backend — Implementation Design

This document is the authoritative implementation guide for all market data functionality in FinAlly. It synthesises the abstract interface (`MARKET_INTERFACE.md`), simulator details (`MARKET_SIMULATOR.md`), and Massive API reference (`MASSIVE_API.md`) into concrete, ready-to-implement code.

---

## 1. Module Layout

```
backend/
└── market/
    ├── __init__.py          # exports: create_market_provider, get_provider
    ├── base.py              # PriceQuote dataclass, MarketDataProvider ABC
    ├── cache.py             # PriceCache — thread-safe dict wrapper
    ├── factory.py           # create_market_provider() — reads env, returns provider
    ├── simulator.py         # MarketSimulator — GBM + correlated noise + events
    └── massive_client.py    # MassiveClient — REST polling against Massive API
```

All external code (SSE route, portfolio trade endpoint, watchlist routes) imports only from `backend/market/__init__.py`. No route file ever imports `simulator` or `massive_client` directly.

---

## 2. Data Contract

### `PriceQuote` (canonical price record)

```python
# backend/market/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass
class PriceQuote:
    ticker: str
    price: float        # last trade price (or simulated current price)
    prev_close: float   # prior session close (or simulator seed price)
    change_pct: float   # (price - prev_close) / prev_close * 100
    volume: float       # session cumulative volume; 0.0 in simulator
    timestamp_ms: int   # Unix ms of last update


class MarketDataProvider(ABC):

    @abstractmethod
    async def start(self, tickers: Sequence[str]) -> None:
        """Start background polling/simulation for the given tickers."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop cleanly; cancel background task."""

    @abstractmethod
    def get_price(self, ticker: str) -> PriceQuote | None:
        """Latest cached quote for ticker, or None if unknown."""

    @abstractmethod
    def get_all_prices(self) -> dict[str, PriceQuote]:
        """Full price cache snapshot as {ticker: PriceQuote}."""

    @abstractmethod
    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active polling/simulation set."""

    @abstractmethod
    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set."""
```

### Field sources by provider

| Field          | Simulator                              | Massive API                                |
|---------------|----------------------------------------|--------------------------------------------|
| `price`       | Current GBM price (rounded to 2dp)    | `last_trade.price` or `session.close`      |
| `prev_close`  | Seed price (constant for session)      | `session.previous_close`                   |
| `change_pct`  | `(price - seed) / seed * 100`         | `session.change_percent` (or computed)     |
| `volume`      | `0.0` always                          | `session.volume`                           |
| `timestamp_ms`| `int(time.time() * 1000)` each tick   | `last_trade.sip_timestamp` or `updated`    |

### SSE event payload (what the frontend receives)

The SSE endpoint serialises `PriceQuote` objects. Each SSE `data:` line is a JSON object mapping ticker → quote:

```json
{
  "AAPL": {
    "ticker": "AAPL",
    "price": 191.34,
    "prev_close": 190.00,
    "change_pct": 0.7053,
    "volume": 0.0,
    "timestamp_ms": 1748995200000
  },
  "MSFT": { ... }
}
```

The frontend consumes this with `EventSource`. On each message it iterates the keys and updates the watchlist row for each ticker.

---

## 3. Price Cache

```python
# backend/market/cache.py

import threading
from .base import PriceQuote


class PriceCache:
    """Thread-safe in-memory store for the latest price per ticker.

    Both the simulator loop and the Massive poll run in threads/tasks and
    write here. SSE generator reads here. Lock kept fine-grained so the
    SSE loop is never blocked for more than a dict copy.
    """

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
            return dict(self._data)  # shallow copy; callers must not mutate

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._data.pop(ticker, None)

    def tickers(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())
```

---

## 4. Market Simulator

### Mathematical model

Each price tick applies geometric Brownian motion (GBM):

```
S(t+dt) = S(t) * exp((μ - σ²/2) * dt + σ * √dt * Z)
```

Where `dt = 0.5 / (365 * 24 * 3600)` (500 ms expressed as a fraction of a year).

Tickers share a common market factor `Z_market` drawn once per tick, plus independent idiosyncratic noise:

```
Z_ticker = ρ * Z_market + √(1 - ρ²) * Z_idiosyncratic
```

This produces natural sector co-movement without building an explicit correlation matrix.

### Full implementation

```python
# backend/market/simulator.py

import asyncio
import math
import random
import time
from dataclasses import dataclass
from typing import Sequence

from .base import MarketDataProvider, PriceQuote
from .cache import PriceCache

TICK_INTERVAL = 0.5                              # seconds
DT = TICK_INTERVAL / (365 * 24 * 3600)          # fraction of a year per tick

EVENT_PROB = 0.002   # ~0.2% per tick ≈ once every ~8 minutes per ticker
EVENT_MIN  = 0.02    # 2% jump
EVENT_MAX  = 0.05    # 5% jump

SEED_PRICES: dict[str, float] = {
    "AAPL":  190.00,
    "GOOGL": 175.00,
    "MSFT":  415.00,
    "AMZN":  185.00,
    "TSLA":  250.00,
    "NVDA":  870.00,
    "META":  510.00,
    "JPM":   195.00,
    "V":     275.00,
    "NFLX":  630.00,
}
DEFAULT_SEED_PRICE = 100.00


@dataclass
class TickerConfig:
    mu: float     # annualized drift (e.g. 0.07 = 7%)
    sigma: float  # annualized volatility (e.g. 0.30 = 30%)
    rho: float    # market correlation coefficient [0, 1]


TICKER_CONFIGS: dict[str, TickerConfig] = {
    "AAPL":  TickerConfig(mu=0.07, sigma=0.28, rho=0.65),
    "GOOGL": TickerConfig(mu=0.06, sigma=0.30, rho=0.60),
    "MSFT":  TickerConfig(mu=0.08, sigma=0.25, rho=0.65),
    "AMZN":  TickerConfig(mu=0.08, sigma=0.32, rho=0.55),
    "TSLA":  TickerConfig(mu=0.05, sigma=0.60, rho=0.45),
    "NVDA":  TickerConfig(mu=0.10, sigma=0.55, rho=0.60),
    "META":  TickerConfig(mu=0.07, sigma=0.35, rho=0.60),
    "JPM":   TickerConfig(mu=0.05, sigma=0.22, rho=0.35),
    "V":     TickerConfig(mu=0.06, sigma=0.20, rho=0.35),
    "NFLX":  TickerConfig(mu=0.06, sigma=0.38, rho=0.50),
}
DEFAULT_CONFIG = TickerConfig(mu=0.05, sigma=0.30, rho=0.40)


@dataclass
class _TickerState:
    ticker: str
    price: float
    prev_close: float   # seed price — held constant as "yesterday's close"
    config: TickerConfig

    @classmethod
    def from_seed(cls, ticker: str) -> "_TickerState":
        seed = SEED_PRICES.get(ticker, DEFAULT_SEED_PRICE)
        cfg  = TICKER_CONFIGS.get(ticker, DEFAULT_CONFIG)
        return cls(ticker=ticker, price=seed, prev_close=seed, config=cfg)

    def tick(self, z_market: float, rng: random.Random) -> None:
        cfg = self.config
        z_idio = rng.gauss(0, 1)
        z = cfg.rho * z_market + math.sqrt(1 - cfg.rho ** 2) * z_idio
        new_price = self.price * math.exp(
            (cfg.mu - 0.5 * cfg.sigma ** 2) * DT
            + cfg.sigma * math.sqrt(DT) * z
        )
        # random shock event
        if rng.random() < EVENT_PROB:
            direction = rng.choice([-1.0, 1.0])
            magnitude = rng.uniform(EVENT_MIN, EVENT_MAX)
            new_price *= 1 + direction * magnitude
        self.price = max(new_price, 0.01)  # price floor — never zero/negative


class MarketSimulator(MarketDataProvider):
    """
    In-process GBM price simulator. Default provider when MASSIVE_API_KEY is absent.
    Pass seed for deterministic output (unit tests, reproducible demos).
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._cache = PriceCache()
        self._states: dict[str, _TickerState] = {}
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def start(self, tickers: Sequence[str]) -> None:
        for t in tickers:
            t = t.upper()
            if t not in self._states:
                state = _TickerState.from_seed(t)
                self._states[t] = state
                self._cache.update(self._make_quote(state))
        self._task = asyncio.create_task(self._simulate_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------ #
    # Cache access (implements MarketDataProvider)                         #
    # ------------------------------------------------------------------ #

    def get_price(self, ticker: str) -> PriceQuote | None:
        return self._cache.get(ticker.upper())

    def get_all_prices(self) -> dict[str, PriceQuote]:
        return self._cache.get_all()

    def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        if ticker not in self._states:
            state = _TickerState.from_seed(ticker)
            self._states[ticker] = state
            self._cache.update(self._make_quote(state))
        # If ticker already exists, it's already running — no-op.

    def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._states.pop(ticker, None)
        self._cache.remove(ticker)

    # ------------------------------------------------------------------ #
    # Internal loop                                                        #
    # ------------------------------------------------------------------ #

    async def _simulate_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_INTERVAL)
            z_market = self._rng.gauss(0, 1)
            for state in list(self._states.values()):
                state.tick(z_market, self._rng)
                self._cache.update(self._make_quote(state))

    @staticmethod
    def _make_quote(state: _TickerState) -> PriceQuote:
        change_pct = (state.price - state.prev_close) / state.prev_close * 100
        return PriceQuote(
            ticker=state.ticker,
            price=round(state.price, 2),
            prev_close=round(state.prev_close, 2),
            change_pct=round(change_pct, 4),
            volume=0.0,
            timestamp_ms=int(time.time() * 1000),
        )
```

### Simulator behaviour notes

- **"Daily % change"**: `prev_close` is the seed price. It never changes within a session. The frontend should label this "Change since open" rather than "Daily change".
- **Dynamic tickers**: `add_ticker("PYPL")` on a running simulator initialises a new `_TickerState` at $100 with `DEFAULT_CONFIG`. The quote appears in the cache immediately; the SSE stream includes it within 500ms.
- **No ticker validation**: any string becomes a valid simulated ticker. Validation (e.g., checking against a known symbol list) belongs at the API route layer, not here.
- **Deterministic mode**: pass `seed=42` at construction. All `rng.*` calls use the seeded instance, producing a reproducible price sequence.

---

## 5. Massive API Client

### Overview

`MassiveClient` polls `GET /v3/snapshot` (Massive/Polygon.io unified snapshot endpoint) every 15 seconds and writes results into the shared `PriceCache`. The SSE stream reads from the same cache at 500ms regardless of the poll cadence, so the frontend sees smooth updates even though upstream data refreshes less often.

### Authentication

Use the query-parameter style for simplicity:

```
GET https://api.massive.com/v3/snapshot?apiKey=YOUR_KEY&ticker.any_of=AAPL,MSFT&limit=250
```

### Response mapping

```
Massive field                    → PriceQuote field
-------------------------------------------------
results[n].ticker               → ticker
results[n].last_trade.price     → price  (fallback: session.close)
results[n].session.previous_close → prev_close
results[n].session.change_percent → change_pct  (or computed)
results[n].session.volume       → volume
results[n].last_trade.sip_timestamp → timestamp_ms  (fallback: results[n].updated)
```

### Full implementation

```python
# backend/market/massive_client.py

import asyncio
import logging
import time
from typing import Sequence

import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError as ReqConnError

from .base import MarketDataProvider, PriceQuote
from .cache import PriceCache

logger = logging.getLogger(__name__)

BASE_URL = "https://api.massive.com"
DEFAULT_POLL_INTERVAL = 15.0   # seconds — safe for free/starter tiers
MAX_TICKERS_PER_REQUEST = 250  # API hard limit


class MassiveClient(MarketDataProvider):
    """
    REST-polling market data client for Massive (formerly Polygon.io).
    Polls /v3/snapshot for all watched tickers on a configurable interval.
    On poll failure, the last cached prices are kept — no crash, no empty SSE.
    """

    def __init__(self, api_key: str, poll_interval: float = DEFAULT_POLL_INTERVAL) -> None:
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._cache = PriceCache()
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def start(self, tickers: Sequence[str]) -> None:
        self._tickers = {t.upper() for t in tickers}
        # Fetch once immediately so the cache is populated before the first SSE push.
        try:
            await self._poll_once()
        except Exception:
            logger.warning("Initial Massive poll failed; cache will populate on next poll")
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------ #
    # Cache access (implements MarketDataProvider)                         #
    # ------------------------------------------------------------------ #

    def get_price(self, ticker: str) -> PriceQuote | None:
        return self._cache.get(ticker.upper())

    def get_all_prices(self) -> dict[str, PriceQuote]:
        return self._cache.get_all()

    def add_ticker(self, ticker: str) -> None:
        # Added to the set; included in the next poll cycle automatically.
        self._tickers.add(ticker.upper())

    def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker.upper())
        self._cache.remove(ticker.upper())

    # ------------------------------------------------------------------ #
    # Internal polling                                                     #
    # ------------------------------------------------------------------ #

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers:
            return
        try:
            quotes = await asyncio.to_thread(
                self._fetch_snapshots, list(self._tickers)
            )
            for q in quotes:
                self._cache.update(q)
        except Exception:
            logger.exception("Massive poll failed; keeping last cached prices")

    def _fetch_snapshots(self, tickers: list[str]) -> list[PriceQuote]:
        """Synchronous HTTP fetch, run in a thread via asyncio.to_thread."""
        # Batch into chunks if somehow we exceed the API limit.
        results: list[PriceQuote] = []
        for i in range(0, len(tickers), MAX_TICKERS_PER_REQUEST):
            chunk = tickers[i : i + MAX_TICKERS_PER_REQUEST]
            results.extend(self._fetch_chunk(chunk))
        return results

    def _fetch_chunk(self, tickers: list[str]) -> list[PriceQuote]:
        resp = self._get_with_retry(
            f"{BASE_URL}/v3/snapshot",
            params={
                "apiKey": self._api_key,
                "ticker.any_of": ",".join(tickers),
                "limit": len(tickers),
            },
        )
        now_ms = int(time.time() * 1000)
        quotes: list[PriceQuote] = []
        for r in resp.get("results", []):
            session    = r.get("session", {})
            last_trade = r.get("last_trade", {})

            price = (
                last_trade.get("price")
                or session.get("close")
                or 0.0
            )
            prev_close = session.get("previous_close") or price
            change_pct = (
                session.get("change_percent")
                or (
                    (price - prev_close) / prev_close * 100
                    if prev_close
                    else 0.0
                )
            )
            timestamp_ms = (
                last_trade.get("sip_timestamp")
                or r.get("updated")
                or now_ms
            )

            quotes.append(PriceQuote(
                ticker=r["ticker"],
                price=round(float(price), 2),
                prev_close=round(float(prev_close), 2),
                change_pct=round(float(change_pct), 4),
                volume=float(session.get("volume") or 0.0),
                timestamp_ms=int(timestamp_ms),
            ))
        return quotes

    def _get_with_retry(
        self,
        url: str,
        params: dict,
        retries: int = 3,
    ) -> dict:
        for attempt in range(retries):
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning("Rate limited by Massive; backing off %ds", wait)
                    import time as _time; _time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (Timeout, ReqConnError) as exc:
                if attempt == retries - 1:
                    raise
                logger.warning("Massive request failed (%s); retrying", exc)
        return {}  # unreachable but satisfies type checker
```

### Rate limit behaviour

| Tier             | `poll_interval` | Notes                              |
|-----------------|----------------|------------------------------------|
| Free             | 15 s           | 5 req/min limit; one call/15s = 4/min, safe |
| Starter/Developer| 15 s           | 15-min delayed data; fine for dev  |
| Advanced/Business| 2 s            | Real-time; pass `poll_interval=2.0` |

Pass `poll_interval` at construction when creating via the factory if a non-default rate is needed (e.g., read from an env var `MASSIVE_POLL_INTERVAL`).

### Market hours behaviour

Outside US market hours (pre-market, after-hours, weekends), Massive returns the last known price. `last_trade.price` reflects the final trade from the last session. `session.change_percent` reflects that session's change. This is correct behaviour — the frontend displays "stale but accurate" prices with unchanged arrows.

---

## 6. Factory

```python
# backend/market/factory.py

import os
from .base import MarketDataProvider
from .simulator import MarketSimulator
from .massive_client import MassiveClient

_provider: MarketDataProvider | None = None


def create_market_provider() -> MarketDataProvider:
    """
    Read MASSIVE_API_KEY from the environment.
    Return MassiveClient if set and non-empty, else MarketSimulator.
    """
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        poll_interval = float(os.getenv("MASSIVE_POLL_INTERVAL", "15.0"))
        return MassiveClient(api_key=api_key, poll_interval=poll_interval)
    return MarketSimulator()


def get_provider() -> MarketDataProvider:
    """Return the initialized provider. Raises if called before startup."""
    if _provider is None:
        raise RuntimeError("Market provider not initialized — call init_provider() first")
    return _provider


def init_provider(provider: MarketDataProvider) -> None:
    """Store the provider singleton. Called once during FastAPI lifespan."""
    global _provider
    _provider = provider
```

### `__init__.py` public API

```python
# backend/market/__init__.py

from .factory import create_market_provider, get_provider, init_provider
from .base import PriceQuote, MarketDataProvider

__all__ = [
    "create_market_provider",
    "get_provider",
    "init_provider",
    "PriceQuote",
    "MarketDataProvider",
]
```

---

## 7. FastAPI Integration

### Lifespan startup/shutdown

```python
# backend/main.py  (relevant section)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from .market import create_market_provider, init_provider
from .db import get_watchlist_tickers   # reads watchlist table, returns list[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    tickers = get_watchlist_tickers()   # ["AAPL", "GOOGL", ...]
    provider = create_market_provider()
    await provider.start(tickers)
    init_provider(provider)
    yield
    await provider.stop()


app = FastAPI(lifespan=lifespan)
```

### Trade fill price

```python
# backend/routes/portfolio.py  (relevant section)

from ..market import get_provider

def get_fill_price(ticker: str) -> float:
    quote = get_provider().get_price(ticker)
    if quote is None:
        raise ValueError(f"No price data available for {ticker!r}")
    return quote.price
```

No staleness check is applied. If the Massive API last updated 14 seconds ago, the trade fills at that price. This is acceptable for a simulated demo.

### Watchlist routes

```python
# backend/routes/watchlist.py  (relevant section)

from ..market import get_provider

@router.post("/api/watchlist")
async def add_to_watchlist(body: AddTickerRequest, db=Depends(get_db)):
    ticker = body.ticker.upper()
    # ... validate and insert into DB ...
    get_provider().add_ticker(ticker)
    return {"ticker": ticker}

@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, db=Depends(get_db)):
    ticker = ticker.upper()
    # ... delete from DB ...
    get_provider().remove_ticker(ticker)
    return {"ticker": ticker}
```

For the Massive client, `add_ticker` just inserts into `self._tickers`; the new ticker is included in the next poll cycle automatically. For the simulator, `add_ticker` initialises a `_TickerState` immediately and writes to the cache, so the SSE stream includes it within 500ms.

---

## 8. SSE Streaming Endpoint

```python
# backend/routes/stream.py

import asyncio
import json
from fastapi import Request
from fastapi.responses import StreamingResponse
from ..market import get_provider

SSE_INTERVAL = 0.5   # push rate to clients (2Hz), independent of poll cadence


async def price_stream(request: Request) -> StreamingResponse:
    async def event_generator():
        while not await request.is_disconnected():
            prices = get_provider().get_all_prices()
            payload = {
                ticker: {
                    "ticker":       q.ticker,
                    "price":        q.price,
                    "prev_close":   q.prev_close,
                    "change_pct":   q.change_pct,
                    "volume":       q.volume,
                    "timestamp_ms": q.timestamp_ms,
                }
                for ticker, q in prices.items()
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(SSE_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if proxied
        },
    )
```

Key points:
- The SSE loop runs at 500ms regardless of whether the upstream source is the simulator (also 500ms) or Massive (15s). Clients get smooth updates from the cache.
- `request.is_disconnected()` is a FastAPI/Starlette coroutine. The loop exits when the client tab closes or navigates away.
- `X-Accel-Buffering: no` prevents nginx from batching SSE events when the app runs behind a reverse proxy.

### Frontend consumption pattern

```typescript
// frontend — conceptual (TypeScript)

const es = new EventSource("/api/stream/prices");

es.onmessage = (event) => {
  const updates: Record<string, PriceQuote> = JSON.parse(event.data);
  for (const [ticker, quote] of Object.entries(updates)) {
    updateWatchlistRow(ticker, quote);      // flash green/red
    appendSparklinePoint(ticker, quote);   // accumulate in-memory
  }
};

es.onerror = () => {
  // EventSource retries automatically — just update the connection status dot
  setConnectionStatus("reconnecting");
};
```

---

## 9. Resolving Open Questions from PLAN.md §13

### SSE and dynamic watchlist changes

When `add_ticker` is called, both implementations update the provider's internal state immediately:

- **Simulator**: a new `_TickerState` and cache entry are created synchronously inside `add_ticker`. The next SSE push (≤500ms) will include the new ticker. **No reconnect needed.**
- **Massive**: the ticker is added to `self._tickers`. It is fetched in the next poll cycle (≤15s). The cache entry appears then, and the next SSE push after that delivers it. For a better UX, the watchlist route can synthesise a placeholder quote (price=0, change_pct=0) immediately so the frontend row appears instantly, then gets overwritten on the first real poll.

In both cases the client **does not need to reconnect**. The SSE stream delivers all tickers in `get_all_prices()` on each push.

### "Daily % change" source

- **Simulator**: `prev_close` = seed price (constant for the session). `change_pct` = drift from that baseline. Label it **"Change since open"** in the UI.
- **Massive**: `session.previous_close` = official prior session close. `change_pct` = `session.change_percent`. This is a true daily % change.

The `PriceQuote` data contract is identical for both; only the semantic meaning of `prev_close` differs. The frontend does not need to branch on which provider is active.

### Main chart data source

No historical price API endpoint is defined in the current scope. The main chart accumulates price points from the SSE stream in frontend memory (same as sparklines, but in a larger array). The chart shows session data only — since the simulator started, or since the page loaded for Massive.

If a `GET /api/prices/{ticker}/history` endpoint is added in the future, the chart can pre-populate from it. For now, it fills in progressively from SSE, consistent with the sparkline approach described in PLAN.md §2.

### `watchlist_changes` action values

Valid values for `action` in the LLM structured output `watchlist_changes` array:
- `"add"` — add ticker to watchlist (calls `POST /api/watchlist`)
- `"remove"` — remove ticker from watchlist (calls `DELETE /api/watchlist/{ticker}`)

These are the only two valid values. The LLM system prompt must enumerate them explicitly.

### SSE event payload field names

Canonical field names (as emitted by `backend/routes/stream.py`):

| Field          | Type    | Description                              |
|---------------|---------|------------------------------------------|
| `ticker`      | string  | Ticker symbol (uppercase)                |
| `price`       | float   | Current price, 2 decimal places          |
| `prev_close`  | float   | Prior close (or seed), 2 decimal places  |
| `change_pct`  | float   | % change from prev_close, 4 decimal places |
| `volume`      | float   | Session volume; 0.0 in simulator         |
| `timestamp_ms`| integer | Unix milliseconds of last update         |

`change_pct` is a signed number: positive = up, negative = down. The frontend derives the flash color (`change_pct > 0` → green, `< 0` → red, `=== 0` → no flash).

### Chat history truncation

The LLM integration should load the **last 20 messages** (10 user + 10 assistant turns) from `chat_messages`. This is a concrete limit; at ~200 tokens/message average, 20 messages ≈ 4,000 tokens — well within Cerebras context limits even with a rich system prompt and portfolio context prepended.

Implementation:

```python
# backend/routes/chat.py  (relevant section)

messages = db.execute(
    "SELECT role, content FROM chat_messages "
    "WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
    ("default",),
).fetchall()
history = [{"role": r, "content": c} for r, c in reversed(messages)]
```

### Ticker validation in simulator mode

No validation is applied in simulator mode — any string becomes a valid ticker. Validation is applied at the API route layer only when `MASSIVE_API_KEY` is set, because the Massive API will return an empty `results` array for unknown symbols. In that case the route should return a 404 with a clear error message.

Recommended route logic:

```python
@router.post("/api/watchlist")
async def add_ticker(body: AddTickerRequest):
    ticker = body.ticker.upper().strip()
    if not ticker.isalpha() or len(ticker) > 5:
        raise HTTPException(400, "Invalid ticker format")

    provider = get_provider()
    provider.add_ticker(ticker)

    # For Massive: verify a price arrived within 20s (one poll cycle)
    # For simulator: price appears immediately — skip the check
    # Simple approach: just accept the ticker and let the frontend show $0.00
    # until the next poll. Not worth blocking the UX for a demo.
    ...
```

---

## 10. Unit Tests

```python
# backend/tests/test_simulator.py

import asyncio
import pytest
from market.simulator import MarketSimulator, _TickerState, SEED_PRICES


def test_seed_price_is_initial_price():
    state = _TickerState.from_seed("AAPL")
    assert state.price == SEED_PRICES["AAPL"]
    assert state.prev_close == SEED_PRICES["AAPL"]


def test_gbm_price_bounded_after_many_ticks():
    import random
    rng = random.Random(0)
    state = _TickerState.from_seed("TSLA")  # high vol ticker
    for _ in range(10_000):
        state.tick(0.0, rng)
    assert 0.01 < state.price < 50_000


def test_unknown_ticker_uses_default_seed():
    state = _TickerState.from_seed("ZZZZZ")
    assert state.price == 100.00


@pytest.mark.asyncio
async def test_add_ticker_appears_in_cache_immediately():
    sim = MarketSimulator(seed=1)
    await sim.start(["AAPL"])
    sim.add_ticker("PYPL")
    quote = sim.get_price("PYPL")
    assert quote is not None
    assert quote.price == 100.00
    await sim.stop()


@pytest.mark.asyncio
async def test_remove_ticker_disappears_from_cache():
    sim = MarketSimulator(seed=2)
    await sim.start(["AAPL", "MSFT"])
    sim.remove_ticker("MSFT")
    assert sim.get_price("MSFT") is None
    await sim.stop()


@pytest.mark.asyncio
async def test_prices_change_after_two_ticks():
    sim = MarketSimulator(seed=7)
    await sim.start(["AAPL"])
    initial = sim.get_price("AAPL").price
    await asyncio.sleep(1.1)   # wait for ≥2 ticks
    updated = sim.get_price("AAPL").price
    assert updated != initial
    await sim.stop()


@pytest.mark.asyncio
async def test_deterministic_with_same_seed():
    async def run_sim(seed):
        sim = MarketSimulator(seed=seed)
        await sim.start(["AAPL"])
        await asyncio.sleep(1.1)
        price = sim.get_price("AAPL").price
        await sim.stop()
        return price

    p1 = await run_sim(42)
    p2 = await run_sim(42)
    assert p1 == p2


@pytest.mark.asyncio
async def test_all_prices_returns_all_started_tickers():
    sim = MarketSimulator(seed=3)
    await sim.start(["AAPL", "MSFT", "GOOGL"])
    prices = sim.get_all_prices()
    assert set(prices.keys()) == {"AAPL", "MSFT", "GOOGL"}
    await sim.stop()
```

```python
# backend/tests/test_massive_client.py

from unittest.mock import patch, MagicMock
from market.massive_client import MassiveClient
from market.base import PriceQuote

MOCK_RESPONSE = {
    "status": "OK",
    "results": [
        {
            "ticker": "AAPL",
            "session": {
                "close": 191.00,
                "previous_close": 189.50,
                "change_percent": 0.79,
                "volume": 52_000_000,
            },
            "last_trade": {
                "price": 191.34,
                "sip_timestamp": 1_700_000_000_000,
            },
            "updated": 1_700_000_000_000,
        }
    ],
}


def test_parse_snapshot_response():
    client = MassiveClient(api_key="test")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_RESPONSE
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        quotes = client._fetch_chunk(["AAPL"])

    assert len(quotes) == 1
    q = quotes[0]
    assert q.ticker == "AAPL"
    assert q.price == 191.34
    assert q.prev_close == 189.50
    assert q.change_pct == 0.79
    assert q.volume == 52_000_000
    assert q.timestamp_ms == 1_700_000_000_000


def test_missing_last_trade_falls_back_to_session_close():
    response = {
        "status": "OK",
        "results": [
            {
                "ticker": "AAPL",
                "session": {"close": 190.00, "previous_close": 189.00},
                "last_trade": {},
                "updated": 1_000,
            }
        ],
    }
    client = MassiveClient(api_key="test")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        quotes = client._fetch_chunk(["AAPL"])

    assert quotes[0].price == 190.00


def test_http_error_does_not_crash_poll():
    import asyncio
    client = MassiveClient(api_key="test")

    with patch.object(client, "_fetch_snapshots", side_effect=Exception("network down")):
        # _poll_once should log and swallow the exception
        asyncio.run(client._poll_once())   # must not raise

    # cache remains empty — no crash
    assert client.get_all_prices() == {}
```

```python
# backend/tests/test_cache.py

import threading
from market.cache import PriceCache
from market.base import PriceQuote


def _quote(ticker: str, price: float) -> PriceQuote:
    return PriceQuote(ticker=ticker, price=price, prev_close=price,
                      change_pct=0.0, volume=0.0, timestamp_ms=0)


def test_update_and_get():
    cache = PriceCache()
    cache.update(_quote("AAPL", 190.0))
    q = cache.get("AAPL")
    assert q is not None and q.price == 190.0


def test_get_missing_returns_none():
    cache = PriceCache()
    assert cache.get("ZZZZ") is None


def test_get_all_returns_copy():
    cache = PriceCache()
    cache.update(_quote("AAPL", 190.0))
    snapshot = cache.get_all()
    snapshot["AAPL"] = None   # mutate the copy
    assert cache.get("AAPL").price == 190.0  # original unaffected


def test_remove():
    cache = PriceCache()
    cache.update(_quote("AAPL", 190.0))
    cache.remove("AAPL")
    assert cache.get("AAPL") is None


def test_thread_safety():
    cache = PriceCache()
    errors = []

    def writer():
        try:
            for i in range(1000):
                cache.update(_quote("AAPL", float(i)))
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(1000):
                cache.get_all()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
```

---

## 11. Implementation Checklist

- [ ] `backend/market/base.py` — `PriceQuote`, `MarketDataProvider`
- [ ] `backend/market/cache.py` — `PriceCache`
- [ ] `backend/market/simulator.py` — `MarketSimulator`, `_TickerState`, seed prices, GBM
- [ ] `backend/market/massive_client.py` — `MassiveClient`, retry logic, response parsing
- [ ] `backend/market/factory.py` — `create_market_provider`, `get_provider`, `init_provider`
- [ ] `backend/market/__init__.py` — public exports
- [ ] `backend/main.py` — lifespan wires up provider against DB watchlist
- [ ] `backend/routes/stream.py` — SSE endpoint reads cache at 500ms
- [ ] `backend/routes/watchlist.py` — `add_ticker` / `remove_ticker` called on provider
- [ ] `backend/routes/portfolio.py` — `get_fill_price` uses `get_provider().get_price()`
- [ ] `backend/tests/test_simulator.py` — all unit tests passing
- [ ] `backend/tests/test_massive_client.py` — mock-based tests passing
- [ ] `backend/tests/test_cache.py` — thread-safety test passing
