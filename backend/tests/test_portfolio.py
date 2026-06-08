"""
Tests for portfolio trade logic and response shapes.

The DB and LLM modules may not be present (built by other agents), so
this file mocks all dependencies — DB queries, market provider, and the
db.init_db module — so these tests are fully self-contained.
"""

import sys
import types
import time
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Inject module stubs BEFORE any app module is imported so that all
# `from db.xxx import yyy` statements in routers resolve to our mocks.
# Stubs are installed lazily inside a session-scoped fixture so they do NOT
# contaminate sys.modules during test collection, which would break test_db.py.
# ---------------------------------------------------------------------------

def _make_mock_conn():
    """Return a MagicMock that acts as a context-manager sqlite3.Connection."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn


def _install_db_stubs():
    """
    Install minimal stub modules for db.init_db and db.queries.
    Returns (init_db_mod, queries_mod, mock_conn, saved_modules) where
    saved_modules is a snapshot of the original sys.modules entries so the
    caller can restore them on teardown.
    """
    mock_conn = _make_mock_conn()

    # Save whatever was in sys.modules before we install stubs
    saved = {
        key: sys.modules.get(key)
        for key in ("db", "db.init_db", "db.queries", "db.schema", "db.cache")
    }

    # db package stub — replace any real package already loaded
    db_pkg = types.ModuleType("db")
    sys.modules["db"] = db_pkg

    # db.init_db stub
    init_db_mod = types.ModuleType("db.init_db")
    init_db_mod.init_db = MagicMock()
    init_db_mod.get_connection = MagicMock(return_value=mock_conn)
    sys.modules["db.init_db"] = init_db_mod

    # db.queries stub
    queries_mod = types.ModuleType("db.queries")
    queries_mod.get_user_profile = MagicMock(return_value={"cash_balance": 10000.0})
    queries_mod.update_cash_balance = MagicMock()
    queries_mod.get_positions = MagicMock(return_value=[])
    queries_mod.get_position = MagicMock(return_value=None)
    queries_mod.upsert_position = MagicMock()
    queries_mod.delete_position = MagicMock()
    queries_mod.record_trade = MagicMock()
    queries_mod.record_portfolio_snapshot = MagicMock()
    queries_mod.get_portfolio_snapshots = MagicMock(return_value=[])
    queries_mod.get_watchlist = MagicMock(return_value=[])
    queries_mod.add_watchlist_ticker = MagicMock(return_value=True)
    queries_mod.remove_watchlist_ticker = MagicMock(return_value=True)
    queries_mod.get_chat_messages = MagicMock(return_value=[])
    queries_mod.add_chat_message = MagicMock()
    sys.modules["db.queries"] = queries_mod

    # Also expose queries as db.queries attribute on the db package
    sys.modules["db"].queries = queries_mod

    return init_db_mod, queries_mod, mock_conn, saved


def _remove_db_stubs(saved: dict) -> None:
    """Restore sys.modules to the state captured before _install_db_stubs."""
    for key, original in saved.items():
        if original is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original


# Module-level placeholders; populated by the session fixture below.
_INIT_DB_MOD: MagicMock = None  # type: ignore[assignment]
_QUERIES_MOD: MagicMock = None  # type: ignore[assignment]
_MOCK_CONN: MagicMock = None    # type: ignore[assignment]
_SAVED_MODULES: dict = {}


@pytest.fixture(scope="module", autouse=True)
def _db_stubs_for_module():
    """
    Install db stubs for the duration of this test module, then restore.
    autouse=True ensures every test in this file sees the stubs.
    """
    global _INIT_DB_MOD, _QUERIES_MOD, _MOCK_CONN, _SAVED_MODULES
    _INIT_DB_MOD, _QUERIES_MOD, _MOCK_CONN, _SAVED_MODULES = _install_db_stubs()
    yield
    _remove_db_stubs(_SAVED_MODULES)


def _make_quote(ticker="AAPL", price=100.0, prev_close=100.0):
    from market.base import PriceQuote
    return PriceQuote(
        ticker=ticker,
        price=price,
        prev_close=prev_close,
        change_pct=round((price - prev_close) / prev_close * 100, 4) if prev_close else 0.0,
        volume=0.0,
        timestamp_ms=int(time.time() * 1000),
    )


def _make_provider(price=100.0):
    provider = MagicMock()
    quote = _make_quote(price=price)
    provider.get_price = MagicMock(return_value=quote)
    provider.get_all_prices = MagicMock(return_value={"AAPL": quote})
    provider.add_ticker = MagicMock()
    provider.remove_ticker = MagicMock()
    return provider


# ---------------------------------------------------------------------------
# Module-scoped app and provider
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def provider():
    return _make_provider(price=100.0)


@pytest.fixture(scope="module")
def app(provider, _db_stubs_for_module):
    """
    Build the FastAPI app once per module, with a no-op lifespan and all
    deps patched.  Depends on _db_stubs_for_module to guarantee stubs are
    installed before main.py is imported.
    """
    # Patch lifespan before importing main
    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    with patch("market.factory.get_provider", return_value=provider), \
         patch("market.factory.create_market_provider", return_value=provider), \
         patch("market.factory.init_provider"):

        import main as app_module
        app_module.app.router.lifespan_context = _noop_lifespan
        return app_module.app


@pytest.fixture()
def tc(app):
    """Return a fresh TestClient for each test."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_mocks(provider):
    """Reset query mocks and provider mock before each test."""
    q = _QUERIES_MOD

    # Reset all mock call history
    q.get_user_profile.reset_mock()
    q.get_user_profile.return_value = {"cash_balance": 10000.0}
    q.update_cash_balance.reset_mock()
    q.get_positions.reset_mock()
    q.get_positions.return_value = []
    q.get_position.reset_mock()
    q.get_position.return_value = None
    q.upsert_position.reset_mock()
    q.delete_position.reset_mock()
    q.record_trade.reset_mock()
    q.record_portfolio_snapshot.reset_mock()
    q.get_portfolio_snapshots.return_value = []

    quote = _make_quote(price=100.0)
    provider.get_price.return_value = quote
    provider.get_all_prices.return_value = {"AAPL": quote}

    # Reset mock_conn context manager
    _MOCK_CONN.__enter__.return_value = _MOCK_CONN
    _INIT_DB_MOD.get_connection.return_value = _MOCK_CONN


# ---------------------------------------------------------------------------
# test_buy_sufficient_cash
# ---------------------------------------------------------------------------

def test_buy_sufficient_cash(tc):
    """cash=10000, price=100, qty=1 → cost=100 ≤ 10000 → 200."""
    _QUERIES_MOD.get_user_profile.return_value = {"cash_balance": 10000.0}
    _QUERIES_MOD.get_position.return_value = None
    _QUERIES_MOD.get_positions.return_value = []

    response = tc.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1, "side": "buy"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["side"] == "buy"
    assert data["quantity"] == 1
    assert data["price"] == 100.0


# ---------------------------------------------------------------------------
# test_buy_insufficient_cash
# ---------------------------------------------------------------------------

def test_buy_insufficient_cash(tc, provider):
    """cash=100, price=200, qty=100 → cost=20000 > 100 → 400."""
    quote = _make_quote(price=200.0)
    provider.get_price.return_value = quote

    _QUERIES_MOD.get_user_profile.return_value = {"cash_balance": 100.0}
    _QUERIES_MOD.get_position.return_value = None
    _QUERIES_MOD.get_positions.return_value = []

    response = tc.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 100, "side": "buy"},
    )
    assert response.status_code == 400
    assert "Insufficient cash" in response.json()["detail"]


# ---------------------------------------------------------------------------
# test_sell_sufficient
# ---------------------------------------------------------------------------

def test_sell_sufficient(tc):
    """Have 10 shares, sell 5 → 200."""
    _QUERIES_MOD.get_user_profile.return_value = {"cash_balance": 5000.0}
    _QUERIES_MOD.get_position.return_value = {
        "id": "pos-uuid",
        "user_id": "default",
        "ticker": "AAPL",
        "quantity": 10.0,
        "avg_cost": 90.0,
        "updated_at": "2026-01-01T00:00:00.000Z",
    }
    _QUERIES_MOD.get_positions.return_value = []

    response = tc.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 5, "side": "sell"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["side"] == "sell"
    assert data["quantity"] == 5


# ---------------------------------------------------------------------------
# test_sell_too_many
# ---------------------------------------------------------------------------

def test_sell_too_many(tc):
    """Have 2 shares, sell 5 → 400."""
    _QUERIES_MOD.get_user_profile.return_value = {"cash_balance": 5000.0}
    _QUERIES_MOD.get_position.return_value = {
        "id": "pos-uuid",
        "user_id": "default",
        "ticker": "AAPL",
        "quantity": 2.0,
        "avg_cost": 90.0,
        "updated_at": "2026-01-01T00:00:00.000Z",
    }
    _QUERIES_MOD.get_positions.return_value = []

    response = tc.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 5, "side": "sell"},
    )
    assert response.status_code == 400
    assert "Insufficient shares" in response.json()["detail"]


# ---------------------------------------------------------------------------
# test_weighted_avg_cost
# ---------------------------------------------------------------------------

def test_weighted_avg_cost(tc, provider):
    """
    Buy 10@100, then buy 10@110 → new avg_cost = (10*100 + 10*110)/20 = 105.
    Verified by inspecting the upsert_position call on the second buy.
    """
    # --- First buy: 10@100 ---
    quote100 = _make_quote(price=100.0)
    provider.get_price.return_value = quote100
    _QUERIES_MOD.get_user_profile.return_value = {"cash_balance": 10000.0}
    _QUERIES_MOD.get_position.return_value = None
    _QUERIES_MOD.get_positions.return_value = []

    r1 = tc.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
    )
    assert r1.status_code == 200

    first_call = _QUERIES_MOD.upsert_position.call_args
    assert first_call.args[3] == 10.0    # qty
    assert first_call.args[4] == 100.0   # avg_cost

    # --- Second buy: 10@110, already hold 10@100 ---
    _QUERIES_MOD.upsert_position.reset_mock()
    quote110 = _make_quote(price=110.0)
    provider.get_price.return_value = quote110
    _QUERIES_MOD.get_user_profile.return_value = {"cash_balance": 9000.0}
    _QUERIES_MOD.get_position.return_value = {
        "id": "pos-uuid",
        "user_id": "default",
        "ticker": "AAPL",
        "quantity": 10.0,
        "avg_cost": 100.0,
        "updated_at": "2026-01-01T00:00:00.000Z",
    }

    r2 = tc.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
    )
    assert r2.status_code == 200

    second_call = _QUERIES_MOD.upsert_position.call_args
    assert second_call.args[3] == 20.0                        # new total qty
    assert abs(second_call.args[4] - 105.0) < 0.001          # new avg_cost ≈ 105


# ---------------------------------------------------------------------------
# test_portfolio_response_shape
# ---------------------------------------------------------------------------

def test_portfolio_response_shape(tc, provider):
    """GET /api/portfolio returns correct fields with correct math."""
    _QUERIES_MOD.get_user_profile.return_value = {"cash_balance": 5000.0}
    _QUERIES_MOD.get_positions.return_value = [
        {
            "id": "pos-uuid",
            "user_id": "default",
            "ticker": "AAPL",
            "quantity": 10.0,
            "avg_cost": 90.0,
            "updated_at": "2026-01-01T00:00:00.000Z",
        }
    ]
    quote = _make_quote(price=100.0, prev_close=90.0)
    provider.get_price.return_value = quote

    response = tc.get("/api/portfolio")
    assert response.status_code == 200

    data = response.json()
    assert "positions" in data
    assert "cash_balance" in data
    assert "total_value" in data

    assert data["cash_balance"] == 5000.0
    # total_value = 5000 + 10 * 100 = 6000
    assert abs(data["total_value"] - 6000.0) < 0.01

    assert len(data["positions"]) == 1
    pos = data["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10.0
    assert pos["avg_cost"] == 90.0
    assert pos["current_price"] == 100.0
    assert "unrealized_pnl" in pos
    assert "pnl_pct" in pos

    # unrealized_pnl = (100 - 90) * 10 = 100
    assert abs(pos["unrealized_pnl"] - 100.0) < 0.01
    # pnl_pct = (100 - 90) / 90 * 100 ≈ 11.11
    assert abs(pos["pnl_pct"] - 11.1111) < 0.01
