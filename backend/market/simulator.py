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
        self._cache.remove(ticker)

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
