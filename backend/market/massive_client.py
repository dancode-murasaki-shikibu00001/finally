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
