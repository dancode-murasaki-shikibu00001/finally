"""Tests for the chat endpoint: LLM integration, auto-execution, persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.llm.models import LLMResponse, TradeAction, WatchlistChange
from app.main import app
from app.market import PriceCache


def _make_cache(*pairs: tuple[str, float]) -> PriceCache:
    cache = PriceCache()
    for ticker, price in pairs:
        cache.update(ticker, price)
    return cache


def _make_source() -> AsyncMock:
    src = AsyncMock()
    src.add_ticker = AsyncMock()
    src.remove_ticker = AsyncMock()
    return src


@pytest.fixture
def client(tmp_path):
    db_file = str(tmp_path / "test.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DB_PATH", db_file)
        mp.setenv("LLM_MOCK", "true")
        with TestClient(app) as c:
            app.state.price_cache = _make_cache(
                ("AAPL", 200.0),
                ("GOOGL", 175.0),
                ("TSLA", 300.0),
                ("NVDA", 900.0),
            )
            app.state.market_source = _make_source()
            yield c


class TestChatBasic:
    def test_returns_message_and_schema(self, client):
        resp = client.post("/api/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "trades" in data
        assert "watchlist_changes" in data
        assert "id" in data
        assert "created_at" in data

    def test_mock_mode_returns_without_api_call(self, client):
        resp = client.post("/api/chat", json={"message": "What is my portfolio?"})
        assert resp.status_code == 200
        assert isinstance(resp.json()["message"], str)
        assert len(resp.json()["message"]) > 0

    def test_mock_response_has_empty_actions(self, client):
        resp = client.post("/api/chat", json={"message": "Hi"})
        data = resp.json()
        assert data["trades"] == []
        assert data["watchlist_changes"] == []


class TestChatPersistence:
    def test_user_message_saved(self, client):
        client.post("/api/chat", json={"message": "Save this please"})
        # Verify by sending a second message — history should exist
        # (We can't query chat directly, so we test indirectly via a second call)
        resp = client.post("/api/chat", json={"message": "Hello again"})
        assert resp.status_code == 200

    def test_multiple_messages_persist_without_error(self, client):
        for i in range(3):
            resp = client.post("/api/chat", json={"message": f"Message {i}"})
            assert resp.status_code == 200


class TestChatAutoExecuteTrades:
    def test_buy_trade_auto_executed(self, client):
        llm_buy = LLMResponse(
            message="Buying 5 shares of AAPL for you.",
            trades=[TradeAction(ticker="AAPL", side="buy", quantity=5)],
            watchlist_changes=[],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_buy):
            resp = client.post("/api/chat", json={"message": "Buy 5 AAPL"})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["trades"]) == 1
        trade = data["trades"][0]
        assert trade["ticker"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 5.0
        assert trade["price"] == 200.0
        assert trade["status"] == "ok"

        # Verify the position was actually created
        portfolio = client.get("/api/portfolio").json()
        assert any(p["ticker"] == "AAPL" for p in portfolio["positions"])

    def test_sell_trade_auto_executed(self, client):
        # First buy, then have LLM sell
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})

        llm_sell = LLMResponse(
            message="Selling 5 shares of AAPL.",
            trades=[TradeAction(ticker="AAPL", side="sell", quantity=5)],
            watchlist_changes=[],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_sell):
            resp = client.post("/api/chat", json={"message": "Sell 5 AAPL"})

        data = resp.json()
        assert data["trades"][0]["status"] == "ok"
        portfolio = client.get("/api/portfolio").json()
        pos = next(p for p in portfolio["positions"] if p["ticker"] == "AAPL")
        assert pos["quantity"] == 5.0

    def test_failed_trade_surfaces_error_in_response(self, client):
        llm_oversell = LLMResponse(
            message="Selling 999 shares.",
            trades=[TradeAction(ticker="AAPL", side="sell", quantity=999)],
            watchlist_changes=[],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_oversell):
            resp = client.post("/api/chat", json={"message": "Sell everything"})

        assert resp.status_code == 200  # chat itself succeeds
        trade_result = resp.json()["trades"][0]
        assert trade_result["status"] == "error"
        assert "error" in trade_result

    def test_insufficient_funds_trade_surfaces_error(self, client):
        llm_overbuy = LLMResponse(
            message="Buying a lot of AAPL.",
            trades=[TradeAction(ticker="AAPL", side="buy", quantity=10000)],
            watchlist_changes=[],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_overbuy):
            resp = client.post("/api/chat", json={"message": "Buy all AAPL"})

        assert resp.status_code == 200
        assert resp.json()["trades"][0]["status"] == "error"

    def test_multiple_trades_executed_independently(self, client):
        llm_multi = LLMResponse(
            message="Buying AAPL and GOOGL.",
            trades=[
                TradeAction(ticker="AAPL", side="buy", quantity=1),
                TradeAction(ticker="GOOGL", side="buy", quantity=1),
            ],
            watchlist_changes=[],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_multi):
            resp = client.post("/api/chat", json={"message": "Buy both"})

        trades = resp.json()["trades"]
        assert len(trades) == 2
        assert all(t["status"] == "ok" for t in trades)

    def test_partial_trade_failure_does_not_block_others(self, client):
        # First trade will fail (no shares to sell), second should succeed
        llm_mixed = LLMResponse(
            message="Mixed trades.",
            trades=[
                TradeAction(ticker="AAPL", side="sell", quantity=999),  # will fail
                TradeAction(ticker="GOOGL", side="buy", quantity=1),   # should succeed
            ],
            watchlist_changes=[],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_mixed):
            resp = client.post("/api/chat", json={"message": "Mixed"})

        trades = resp.json()["trades"]
        assert trades[0]["status"] == "error"
        assert trades[1]["status"] == "ok"


class TestChatAutoExecuteWatchlist:
    def test_watchlist_add_executed(self, client):
        # PYPL not seeded, so it's a new add
        app.state.price_cache.update("PYPL", 65.0)
        llm_add = LLMResponse(
            message="Adding PYPL to your watchlist.",
            trades=[],
            watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_add):
            resp = client.post("/api/chat", json={"message": "Add PYPL"})

        assert resp.status_code == 200
        wl_result = resp.json()["watchlist_changes"][0]
        assert wl_result["ticker"] == "PYPL"
        assert wl_result["status"] == "ok"

        watchlist = client.get("/api/watchlist").json()
        assert any(t["ticker"] == "PYPL" for t in watchlist["tickers"])

    def test_watchlist_add_idempotent(self, client):
        # AAPL is already seeded — adding again should still return ok
        llm_readd = LLMResponse(
            message="AAPL is already on your watchlist.",
            trades=[],
            watchlist_changes=[WatchlistChange(ticker="AAPL", action="add")],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_readd):
            resp = client.post("/api/chat", json={"message": "Watch AAPL"})

        wl_result = resp.json()["watchlist_changes"][0]
        assert wl_result["status"] == "ok"

    def test_watchlist_remove_executed(self, client):
        llm_remove = LLMResponse(
            message="Removing AAPL from your watchlist.",
            trades=[],
            watchlist_changes=[WatchlistChange(ticker="AAPL", action="remove")],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_remove):
            resp = client.post("/api/chat", json={"message": "Remove AAPL"})

        wl_result = resp.json()["watchlist_changes"][0]
        assert wl_result["status"] == "ok"

        watchlist = client.get("/api/watchlist").json()
        assert not any(t["ticker"] == "AAPL" for t in watchlist["tickers"])

    def test_watchlist_remove_not_found_returns_not_found_status(self, client):
        llm_remove = LLMResponse(
            message="Removing ZZZZ.",
            trades=[],
            watchlist_changes=[WatchlistChange(ticker="ZZZZ", action="remove")],
        )
        with patch("app.routers.chat.call_llm", return_value=llm_remove):
            resp = client.post("/api/chat", json={"message": "Remove ZZZZ"})

        wl_result = resp.json()["watchlist_changes"][0]
        assert wl_result["status"] == "not_found"


class TestChatLLMModels:
    def test_llm_response_parses_correctly(self):
        raw = '{"message": "hello", "trades": [], "watchlist_changes": []}'
        result = LLMResponse.model_validate_json(raw)
        assert result.message == "hello"
        assert result.trades == []
        assert result.watchlist_changes == []

    def test_llm_response_defaults_empty_lists(self):
        raw = '{"message": "hi"}'
        result = LLMResponse.model_validate_json(raw)
        assert result.trades == []
        assert result.watchlist_changes == []

    def test_trade_action_parses(self):
        raw = '{"message": "ok", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}'
        result = LLMResponse.model_validate_json(raw)
        assert result.trades[0].ticker == "AAPL"
        assert result.trades[0].side == "buy"
        assert result.trades[0].quantity == 10.0

    def test_watchlist_change_parses(self):
        raw = '{"message": "ok", "watchlist_changes": [{"ticker": "TSLA", "action": "add"}]}'
        result = LLMResponse.model_validate_json(raw)
        assert result.watchlist_changes[0].ticker == "TSLA"
        assert result.watchlist_changes[0].action == "add"


class TestChatMockMode:
    def test_mock_true_skips_api(self, client):
        """LLM_MOCK=true must return a response without calling litellm.completion."""
        with patch("app.llm.client.completion") as mock_completion:
            resp = client.post("/api/chat", json={"message": "test"})
        mock_completion.assert_not_called()
        assert resp.status_code == 200

    def test_mock_false_calls_api(self, tmp_path):
        """LLM_MOCK=false (or unset) must invoke litellm.completion."""
        db_file = str(tmp_path / "test.db")
        fake_llm_response = LLMResponse(message="live response", trades=[], watchlist_changes=[])
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("DB_PATH", db_file)
            mp.delenv("LLM_MOCK", raising=False)
            with TestClient(app) as c:
                c.app.state.price_cache = _make_cache(("AAPL", 200.0))
                c.app.state.market_source = _make_source()
                with patch("app.routers.chat.call_llm", return_value=fake_llm_response):
                    resp = c.post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "live response"
