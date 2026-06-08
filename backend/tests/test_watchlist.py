"""Tests for watchlist REST endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market import PriceCache


def _make_cache(*tickers_prices: tuple[str, float]) -> PriceCache:
    cache = PriceCache()
    for ticker, price in tickers_prices:
        cache.update(ticker, price)
    return cache


def _make_source() -> AsyncMock:
    source = AsyncMock()
    source.add_ticker = AsyncMock()
    source.remove_ticker = AsyncMock()
    return source


@pytest.fixture
def client(tmp_path):
    db_file = str(tmp_path / "test.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DB_PATH", db_file)
        with TestClient(app) as c:
            app.state.price_cache = _make_cache(
                ("AAPL", 200.0),
                ("GOOGL", 175.0),
                ("MSFT", 420.0),
                ("AMZN", 185.0),
                ("TSLA", 300.0),
                ("NVDA", 900.0),
                ("META", 500.0),
                ("JPM", 220.0),
                ("V", 280.0),
                ("NFLX", 650.0),
            )
            app.state.market_source = _make_source()
            yield c


class TestGetWatchlist:
    def test_returns_seeded_tickers(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert "tickers" in data
        tickers = [t["ticker"] for t in data["tickers"]]
        assert "AAPL" in tickers
        assert len(tickers) == 10

    def test_ticker_has_price_fields(self, client):
        resp = client.get("/api/watchlist")
        first = resp.json()["tickers"][0]
        assert "ticker" in first
        assert "price" in first
        assert "change" in first
        assert "change_percent" in first
        assert "direction" in first
        assert "added_at" in first

    def test_prices_populated_from_cache(self, client):
        resp = client.get("/api/watchlist")
        aapl = next(t for t in resp.json()["tickers"] if t["ticker"] == "AAPL")
        assert aapl["price"] == 200.0


class TestAddToWatchlist:
    def test_add_new_ticker_returns_201(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["ticker"] == "PYPL"
        assert "added_at" in data

    def test_add_normalizes_ticker_to_uppercase(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "pypl"})
        assert resp.status_code == 201
        assert resp.json()["ticker"] == "PYPL"

    def test_add_appears_in_subsequent_get(self, client):
        client.post("/api/watchlist", json={"ticker": "PYPL"})
        resp = client.get("/api/watchlist")
        tickers = [t["ticker"] for t in resp.json()["tickers"]]
        assert "PYPL" in tickers

    def test_add_duplicate_is_idempotent(self, client):
        # WTCH-02: duplicate add must succeed, not raise an error
        resp = client.post("/api/watchlist", json={"ticker": "AAPL"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert "added_at" in data

    def test_add_duplicate_does_not_call_market_source(self, client):
        # market_source.add_ticker must not be called again for an existing ticker
        app.state.market_source.reset_mock()
        client.post("/api/watchlist", json={"ticker": "AAPL"})
        app.state.market_source.add_ticker.assert_not_awaited()

    def test_add_calls_market_source(self, client):
        client.post("/api/watchlist", json={"ticker": "PYPL"})
        app.state.market_source.add_ticker.assert_awaited_with("PYPL")


class TestRemoveFromWatchlist:
    def test_remove_existing_ticker_returns_204(self, client):
        resp = client.delete("/api/watchlist/AAPL")
        assert resp.status_code == 204

    def test_remove_is_case_insensitive(self, client):
        resp = client.delete("/api/watchlist/aapl")
        assert resp.status_code == 204

    def test_removed_ticker_absent_from_get(self, client):
        client.delete("/api/watchlist/AAPL")
        resp = client.get("/api/watchlist")
        tickers = [t["ticker"] for t in resp.json()["tickers"]]
        assert "AAPL" not in tickers

    def test_remove_nonexistent_returns_404(self, client):
        resp = client.delete("/api/watchlist/ZZZZ")
        assert resp.status_code == 404

    def test_remove_calls_market_source(self, client):
        client.delete("/api/watchlist/AAPL")
        app.state.market_source.remove_ticker.assert_awaited_with("AAPL")
