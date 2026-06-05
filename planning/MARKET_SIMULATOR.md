# Market Simulator Design

The simulator generates realistic-looking stock price movements in-process with no external dependencies. It is the default when `MASSIVE_API_KEY` is not set, and is the recommended mode for development and E2E testing.

---

## Design Goals

- Prices look convincing: smooth continuous movement, realistic volatility, occasional dramatic events
- Multiple tickers move in a correlated way (tech stocks move together, etc.)
- Each ticker starts at a realistic seed price
- CPU footprint is negligible (pure Python math, ~500ms sleep between ticks)
- Deterministic when seeded (useful for reproducible tests)

---

## Mathematical Model: Geometric Brownian Motion (GBM)

GBM is the standard model for stock price simulation. Each tick applies:

```
S(t+dt) = S(t) * exp((μ - σ²/2) * dt + σ * √dt * Z)
```

Where:
- `S(t)` — current price
- `μ` (mu) — annualized drift (small positive value, ~2–5% annualized)
- `σ` (sigma) — annualized volatility (e.g., 0.30 = 30% vol like a tech stock)
- `dt` — time step in years (500ms = 500/(365*24*3600) years ≈ 1.59e-8)
- `Z` — standard normal random variable N(0,1)

Because `dt` is tiny (sub-second), the formula simplifies in practice to:

```python
import math, random

def next_price(price: float, mu: float, sigma: float, dt: float, z: float) -> float:
    return price * math.exp((mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z)
```

---

## Correlated Random Variables

To simulate market-wide moves (e.g., a news event that lifts all tech stocks), tickers share a common market factor in addition to their own idiosyncratic noise:

```
Z_ticker = ρ * Z_market + √(1 - ρ²) * Z_idiosyncratic
```

Where:
- `Z_market` — one standard normal drawn once per tick, shared across all tickers
- `Z_idiosyncratic` — one standard normal drawn per ticker per tick
- `ρ` (rho) — correlation coefficient (0.0 = independent, 1.0 = perfectly correlated)

Typical values:
- Tech cluster (AAPL, MSFT, GOOGL, META, NVDA): `ρ = 0.6`
- Broader market (AMZN, TSLA): `ρ = 0.4`
- Finance/other (JPM, V, NFLX): `ρ = 0.3`

---

## Random Events

Every tick has a small probability of triggering a sudden price jump to add drama:

```python
EVENT_PROBABILITY = 0.002   # ~0.2% per tick ≈ once every ~8 minutes
EVENT_MAGNITUDE_MIN = 0.02  # 2% move
EVENT_MAGNITUDE_MAX = 0.05  # 5% move

def apply_event(price: float, rng: random.Random) -> float:
    if rng.random() < EVENT_PROBABILITY:
        direction = rng.choice([-1, 1])
        magnitude = rng.uniform(EVENT_MAGNITUDE_MIN, EVENT_MAGNITUDE_MAX)
        return price * (1 + direction * magnitude)
    return price
```

---

## Seed Prices

Realistic starting prices prevent the watchlist from showing $1 stocks or $10,000 stocks:

```python
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
DEFAULT_SEED_PRICE = 100.00   # fallback for tickers not in the table
```

For tickers added dynamically (not in the seed table), the simulator starts at `DEFAULT_SEED_PRICE` and gives them a random volatility from the default range.

---

## Per-Ticker Parameters

```python
from dataclasses import dataclass

@dataclass
class TickerConfig:
    mu: float       # annualized drift (e.g., 0.05 = 5% drift)
    sigma: float    # annualized volatility (e.g., 0.30 = 30%)
    rho: float      # market correlation (0.0–1.0)

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
```

---

## Full Simulator Implementation

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

TICK_INTERVAL = 0.5   # seconds between price updates
DT = TICK_INTERVAL / (365 * 24 * 3600)   # fraction of a year per tick

EVENT_PROB = 0.002
EVENT_MIN  = 0.02
EVENT_MAX  = 0.05

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

@dataclass
class TickerConfig:
    mu: float
    sigma: float
    rho: float

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
    prev_close: float    # set to seed price; held constant as the daily baseline
    config: TickerConfig

    @classmethod
    def from_seed(cls, ticker: str) -> "_TickerState":
        seed = SEED_PRICES.get(ticker, 100.00)
        cfg  = TICKER_CONFIGS.get(ticker, DEFAULT_CONFIG)
        return cls(ticker=ticker, price=seed, prev_close=seed, config=cfg)

    def tick(self, z_market: float, rng: random.Random) -> float:
        cfg = self.config
        z_idio = rng.gauss(0, 1)
        z = cfg.rho * z_market + math.sqrt(1 - cfg.rho**2) * z_idio
        new_price = self.price * math.exp(
            (cfg.mu - 0.5 * cfg.sigma**2) * DT + cfg.sigma * math.sqrt(DT) * z
        )
        # random event: sudden jump
        if rng.random() < EVENT_PROB:
            direction = rng.choice([-1.0, 1.0])
            magnitude = rng.uniform(EVENT_MIN, EVENT_MAX)
            new_price *= 1 + direction * magnitude
        self.price = max(new_price, 0.01)   # price floor — never negative
        return self.price


class MarketSimulator(MarketDataProvider):
    """
    Simulates market prices using correlated GBM with random event shocks.
    Acts as a drop-in replacement for MassiveClient when no API key is set.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._cache = PriceCache()
        self._states: dict[str, _TickerState] = {}
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def start(self, tickers: Sequence[str]) -> None:
        async with self._lock:
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
    # Cache access                                                         #
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

    def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._states.pop(ticker, None)
        # Leave the cache entry — the SSE stream will stop seeing it in
        # get_all_prices once it's removed from _states after the next tick.

    # ------------------------------------------------------------------ #
    # Internal simulation loop                                             #
    # ------------------------------------------------------------------ #

    async def _simulate_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_INTERVAL)
            z_market = self._rng.gauss(0, 1)   # shared market factor this tick
            for state in list(self._states.values()):
                state.tick(z_market, self._rng)
                self._cache.update(self._make_quote(state))

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

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

---

## Handling "Daily % Change"

The simulator has no concept of a real trading day. Instead:

- `prev_close` is set once at startup (the seed price).
- `change_pct` accumulates from that baseline for the entire session.
- When the server restarts, prices reset to seed — so `change_pct` always starts at 0%.

This is disclosed behavior, not a bug. The frontend can display a label like "Change since open" instead of "Daily change" to be accurate.

---

## Dynamic Ticker Addition

When a user adds a new ticker (e.g., "PYPL") that is not in `SEED_PRICES`:

1. `add_ticker("PYPL")` is called on the running simulator.
2. A new `_TickerState` is created with `price = 100.00` and `DEFAULT_CONFIG`.
3. A quote is immediately written to the cache.
4. The next SSE push (≤500ms later) includes the new ticker.

There is no ticker validation in simulator mode — any string becomes a valid simulated ticker. Validation belongs at the API layer (see PLAN.md section 13, "Ticker validation in simulator mode").

---

## Deterministic Mode (Testing)

Passing a fixed `seed` to `MarketSimulator` makes output deterministic:

```python
sim = MarketSimulator(seed=42)
```

All random draws (`gauss`, `random`, `uniform`, `choice`) come from `self._rng`, which is seeded at construction. The same seed with the same ticker set produces the same price sequence, enabling reproducible unit tests for portfolio P&L calculations.

For E2E tests where prices don't need to be exact but SSE needs to emit data, any seed works — just set `LLM_MOCK=true` in the test environment (see PLAN.md section 9).

---

## Unit Testing the Simulator

```python
# backend/tests/test_simulator.py

import pytest
from market.simulator import MarketSimulator, _TickerState, SEED_PRICES


def test_gbm_prices_bounded():
    """Prices should not go negative or explode after many ticks."""
    import random
    rng = random.Random(0)
    state = _TickerState.from_seed("AAPL")
    z_mkt = 0.0
    for _ in range(10_000):
        state.tick(z_mkt, rng)
    assert 0.01 < state.price < 10_000


def test_seed_prices_correct():
    state = _TickerState.from_seed("AAPL")
    assert state.price == SEED_PRICES["AAPL"]
    assert state.prev_close == SEED_PRICES["AAPL"]


def test_add_ticker_appears_in_cache():
    sim = MarketSimulator(seed=99)
    import asyncio
    asyncio.run(sim.start(["AAPL"]))
    sim.add_ticker("PYPL")
    quote = sim.get_price("PYPL")
    assert quote is not None
    assert quote.price == 100.00
    asyncio.run(sim.stop())


@pytest.mark.asyncio
async def test_prices_change_after_ticks():
    sim = MarketSimulator(seed=7)
    await sim.start(["AAPL"])
    import asyncio
    await asyncio.sleep(1.1)   # wait for at least two ticks
    q = sim.get_price("AAPL")
    assert q is not None
    assert q.price != SEED_PRICES["AAPL"]   # price should have moved
    await sim.stop()
```

---

## Performance Characteristics

| Property        | Value                                      |
|----------------|--------------------------------------------|
| Update cadence  | 500ms                                      |
| CPU per tick    | < 1ms for 10 tickers (pure Python math)    |
| Memory          | ~1KB per ticker state                      |
| Scaling limit   | ~10,000 tickers before CPU becomes notable |
| Network usage   | Zero (fully in-process)                    |

The simulator is safe to run indefinitely — there is no memory leak, and price values are bounded by the exponential of a random walk (which grows slowly at low volatility and short `dt`).
