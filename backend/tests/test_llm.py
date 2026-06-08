import pytest
from pydantic import ValidationError

from llm import process_chat_message
from llm.schemas import ChatResponse, TradeRequest, WatchlistChange


def test_mock_mode_returns_fixed_response(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    result = process_chat_message("default", "hello", {}, [])
    assert "FinAlly" in result.message
    assert result.trades == []
    assert result.watchlist_changes == []


def test_chat_response_schema_full():
    data = {
        "message": "I bought 10 shares of AAPL",
        "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
        "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
    }
    r = ChatResponse.model_validate(data)
    assert r.trades[0].ticker == "AAPL"
    assert r.watchlist_changes[0].action == "add"


def test_chat_response_defaults_empty_lists():
    r = ChatResponse(message="hello")
    assert r.trades == []
    assert r.watchlist_changes == []


def test_trade_request_side_validation():
    with pytest.raises(ValidationError):
        TradeRequest(ticker="AAPL", side="hold", quantity=10)


def test_watchlist_change_action_validation():
    with pytest.raises(ValidationError):
        WatchlistChange(ticker="AAPL", action="toggle")
