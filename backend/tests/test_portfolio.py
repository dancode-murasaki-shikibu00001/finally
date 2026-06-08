"""Tests for portfolio REST endpoints."""

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
                ("TSLA", 300.0),
            )
            app.state.market_source = _make_source()
            yield c


class TestGetPortfolio:
    def test_returns_default_cash_no_positions(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash_balance"] == 10000.0
        assert data["positions"] == []
        assert data["positions_value"] == 0.0
        assert data["total_value"] == 10000.0

    def test_reflects_positions_after_buy(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        resp = client.get("/api/portfolio")
        data = resp.json()
        assert len(data["positions"]) == 1
        pos = data["positions"][0]
        assert pos["ticker"] == "AAPL"
        assert pos["quantity"] == 10.0
        assert pos["avg_cost"] == 200.0
        assert pos["current_price"] == 200.0
        assert pos["unrealized_pnl"] == 0.0
        assert data["cash_balance"] == pytest.approx(10000.0 - 2000.0)
        assert data["positions_value"] == pytest.approx(2000.0)
        assert data["total_value"] == pytest.approx(10000.0)


class TestExecuteTrade:
    def test_buy_deducts_cash(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "buy", "quantity": 5},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] is True
        assert data["ticker"] == "AAPL"
        assert data["side"] == "buy"
        assert data["quantity"] == 5.0
        assert data["price"] == 200.0
        assert data["cash_balance"] == pytest.approx(10000.0 - 1000.0)

    def test_buy_case_insensitive_ticker(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "aapl", "side": "buy", "quantity": 1},
        )
        assert resp.status_code == 201
        assert resp.json()["ticker"] == "AAPL"

    def test_sell_adds_cash(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "sell", "quantity": 5},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] is True
        assert data["side"] == "sell"
        assert data["cash_balance"] == pytest.approx(10000.0 - 1000.0 - 1000.0 + 1000.0)

    def test_sell_removes_position_when_quantity_zero(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5})
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 5})
        portfolio = client.get("/api/portfolio").json()
        assert portfolio["positions"] == []

    def test_buy_insufficient_funds_returns_400(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "buy", "quantity": 1000},
        )
        assert resp.status_code == 400
        assert "Insufficient funds" in resp.json()["detail"]

    def test_sell_insufficient_shares_returns_400(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "sell", "quantity": 1},
        )
        assert resp.status_code == 400
        assert "Insufficient shares" in resp.json()["detail"]

    def test_invalid_side_returns_400(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "hold", "quantity": 1},
        )
        assert resp.status_code == 400

    def test_zero_quantity_returns_400(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "buy", "quantity": 0},
        )
        assert resp.status_code == 400

    def test_unknown_ticker_no_price_returns_400(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "ZZZZ", "side": "buy", "quantity": 1},
        )
        assert resp.status_code == 400
        assert "No price available" in resp.json()["detail"]

    def test_buy_updates_avg_cost(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        # Update price and buy more
        app.state.price_cache.update("AAPL", 210.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        portfolio = client.get("/api/portfolio").json()
        pos = portfolio["positions"][0]
        assert pos["avg_cost"] == pytest.approx(205.0)

    def test_trade_creates_snapshot(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})
        history = client.get("/api/portfolio/history").json()
        assert len(history["snapshots"]) >= 1


class TestPortfolioHistory:
    def test_empty_history_initially(self, client):
        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200
        assert resp.json()["snapshots"] == []

    def test_history_grows_after_trades(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 1})
        history = client.get("/api/portfolio/history").json()
        assert len(history["snapshots"]) == 2

    def test_snapshot_total_value_correct(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5})
        history = client.get("/api/portfolio/history").json()
        snap = history["snapshots"][0]
        assert snap["total_value"] == pytest.approx(10000.0)
        assert "recorded_at" in snap
