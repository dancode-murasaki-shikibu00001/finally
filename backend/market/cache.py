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
