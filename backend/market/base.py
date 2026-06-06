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
