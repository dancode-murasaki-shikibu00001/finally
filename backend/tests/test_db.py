"""
Tests for the FinAlly database module (db/).

Each test uses a fresh SQLite database in pytest's tmp_path so tests are
fully isolated and leave no artefacts on disk.

The DB_PATH environment variable is set via monkeypatch so get_db_path() and
get_connection() automatically use the temporary file.
"""

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open(tmp_db: Path) -> sqlite3.Connection:
    """Open the test database with row_factory already set."""
    conn = sqlite3.connect(str(tmp_db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """
    Yield the path to a fresh temporary SQLite file and configure DB_PATH so
    all db.* helpers use it automatically.
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    return db_file


@pytest.fixture()
def initialized_db(tmp_db):
    """
    Yield a (path, connection) tuple for a fully initialised database.
    The connection is closed after the test.
    """
    from db.init_db import init_db, get_connection

    init_db()
    conn = get_connection()
    yield tmp_db, conn
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInitCreatesAllTables:
    def test_init_creates_all_tables(self, tmp_db):
        """After init_db(), all 6 tables must exist."""
        from db.init_db import init_db
        from db.schema import TABLE_NAMES

        init_db()

        conn = _open(tmp_db)
        try:
            existing = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()

        for table in TABLE_NAMES:
            assert table in existing, f"Table '{table}' was not created"

    def test_init_is_idempotent(self, tmp_db):
        """Calling init_db() twice must not raise or duplicate seed data."""
        from db.init_db import init_db

        init_db()
        init_db()  # second call must be a no-op

        conn = _open(tmp_db)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM users_profile WHERE id='default'"
            ).fetchone()[0]
        finally:
            conn.close()

        assert count == 1


class TestSeedData:
    def test_default_user_has_correct_cash(self, initialized_db):
        """Seeded default user must start with $10,000 cash."""
        _, conn = initialized_db
        from db.queries import get_user_profile

        profile = get_user_profile(conn, "default")
        assert profile["cash_balance"] == 10000.0

    def test_watchlist_has_ten_tickers(self, initialized_db):
        """Seeded watchlist must contain exactly 10 tickers."""
        _, conn = initialized_db
        from db.queries import get_watchlist

        watchlist = get_watchlist(conn, "default")
        assert len(watchlist) == 10

    def test_watchlist_contains_expected_tickers(self, initialized_db):
        """Seeded watchlist must include the 10 canonical tickers."""
        _, conn = initialized_db
        from db.queries import get_watchlist
        from db.init_db import DEFAULT_TICKERS

        tickers = {row["ticker"] for row in get_watchlist(conn, "default")}
        assert tickers == set(DEFAULT_TICKERS)


class TestAddRemoveTicker:
    def test_add_ticker_appears_in_watchlist(self, initialized_db):
        _, conn = initialized_db
        from db.queries import get_watchlist, add_watchlist_ticker

        result = add_watchlist_ticker(conn, "default", "PYPL")
        assert result is True

        tickers = {row["ticker"] for row in get_watchlist(conn, "default")}
        assert "PYPL" in tickers

    def test_add_duplicate_returns_false(self, initialized_db):
        _, conn = initialized_db
        from db.queries import add_watchlist_ticker

        add_watchlist_ticker(conn, "default", "PYPL")
        result = add_watchlist_ticker(conn, "default", "PYPL")
        assert result is False

    def test_remove_ticker_disappears_from_watchlist(self, initialized_db):
        _, conn = initialized_db
        from db.queries import get_watchlist, add_watchlist_ticker, remove_watchlist_ticker

        add_watchlist_ticker(conn, "default", "PYPL")
        result = remove_watchlist_ticker(conn, "default", "PYPL")
        assert result is True

        tickers = {row["ticker"] for row in get_watchlist(conn, "default")}
        assert "PYPL" not in tickers

    def test_remove_nonexistent_returns_false(self, initialized_db):
        _, conn = initialized_db
        from db.queries import remove_watchlist_ticker

        result = remove_watchlist_ticker(conn, "default", "ZZZZ")
        assert result is False

    def test_add_ticker_normalised_to_uppercase(self, initialized_db):
        _, conn = initialized_db
        from db.queries import add_watchlist_ticker, get_watchlist

        add_watchlist_ticker(conn, "default", "pypl")
        tickers = {row["ticker"] for row in get_watchlist(conn, "default")}
        assert "PYPL" in tickers
        assert "pypl" not in tickers


class TestRecordTradeAndPosition:
    def test_record_trade_is_logged(self, initialized_db):
        _, conn = initialized_db
        from db.queries import record_trade, get_trades

        trade_id = record_trade(conn, "default", "AAPL", "buy", 5.0, 190.0)
        assert isinstance(trade_id, str) and len(trade_id) == 36  # UUID format

        trades = get_trades(conn, "default")
        assert len(trades) == 1
        t = trades[0]
        assert t["ticker"] == "AAPL"
        assert t["side"] == "buy"
        assert t["quantity"] == 5.0
        assert t["price"] == 190.0

    def test_record_sell_trade(self, initialized_db):
        _, conn = initialized_db
        from db.queries import record_trade, get_trades

        record_trade(conn, "default", "TSLA", "sell", 2.0, 250.0)
        trades = get_trades(conn, "default")
        assert trades[0]["side"] == "sell"

    def test_multiple_trades_ordered_newest_first(self, initialized_db):
        _, conn = initialized_db
        from db.queries import record_trade, get_trades

        record_trade(conn, "default", "AAPL", "buy", 1.0, 100.0)
        # Tiny sleep to ensure distinct timestamps
        time.sleep(0.01)
        record_trade(conn, "default", "MSFT", "buy", 2.0, 200.0)

        trades = get_trades(conn, "default")
        assert trades[0]["ticker"] == "MSFT"  # newest first
        assert trades[1]["ticker"] == "AAPL"


class TestUpsertPosition:
    def test_new_position_created(self, initialized_db):
        _, conn = initialized_db
        from db.queries import upsert_position, get_position

        upsert_position(conn, "default", "AAPL", 10.0, 190.0)
        pos = get_position(conn, "default", "AAPL")
        assert pos is not None
        assert pos["ticker"] == "AAPL"
        assert pos["quantity"] == 10.0
        assert pos["avg_cost"] == 190.0

    def test_update_existing_position(self, initialized_db):
        _, conn = initialized_db
        from db.queries import upsert_position, get_position

        upsert_position(conn, "default", "AAPL", 10.0, 190.0)
        upsert_position(conn, "default", "AAPL", 20.0, 195.0)  # update

        pos = get_position(conn, "default", "AAPL")
        assert pos["quantity"] == 20.0
        assert pos["avg_cost"] == 195.0

    def test_upsert_preserves_uuid_on_update(self, initialized_db):
        _, conn = initialized_db
        from db.queries import upsert_position, get_position

        upsert_position(conn, "default", "AAPL", 10.0, 190.0)
        first_id = get_position(conn, "default", "AAPL")["id"]

        upsert_position(conn, "default", "AAPL", 20.0, 195.0)
        second_id = get_position(conn, "default", "AAPL")["id"]

        assert first_id == second_id  # UUID must not change on update

    def test_delete_position(self, initialized_db):
        _, conn = initialized_db
        from db.queries import upsert_position, delete_position, get_position

        upsert_position(conn, "default", "AAPL", 10.0, 190.0)
        delete_position(conn, "default", "AAPL")
        assert get_position(conn, "default", "AAPL") is None

    def test_get_positions_returns_all(self, initialized_db):
        _, conn = initialized_db
        from db.queries import upsert_position, get_positions

        upsert_position(conn, "default", "AAPL", 5.0, 190.0)
        upsert_position(conn, "default", "MSFT", 3.0, 300.0)

        positions = get_positions(conn, "default")
        tickers = {p["ticker"] for p in positions}
        assert tickers == {"AAPL", "MSFT"}


class TestPortfolioSnapshot:
    def test_record_and_retrieve_snapshot(self, initialized_db):
        _, conn = initialized_db
        from db.queries import record_portfolio_snapshot, get_portfolio_snapshots

        snap_id = record_portfolio_snapshot(conn, "default", 12345.67)
        assert isinstance(snap_id, str) and len(snap_id) == 36

        snapshots = get_portfolio_snapshots(conn, "default")
        assert len(snapshots) == 1
        assert snapshots[0]["total_value"] == 12345.67

    def test_snapshots_ordered_oldest_first(self, initialized_db):
        _, conn = initialized_db
        from db.queries import record_portfolio_snapshot, get_portfolio_snapshots

        record_portfolio_snapshot(conn, "default", 10000.0)
        time.sleep(0.01)
        record_portfolio_snapshot(conn, "default", 10500.0)
        time.sleep(0.01)
        record_portfolio_snapshot(conn, "default", 11000.0)

        snapshots = get_portfolio_snapshots(conn, "default")
        values = [s["total_value"] for s in snapshots]
        assert values == sorted(values) or values == [10000.0, 10500.0, 11000.0]

    def test_snapshot_limit_respected(self, initialized_db):
        _, conn = initialized_db
        from db.queries import record_portfolio_snapshot, get_portfolio_snapshots

        for i in range(5):
            record_portfolio_snapshot(conn, "default", float(10000 + i * 100))

        snapshots = get_portfolio_snapshots(conn, "default", limit=3)
        assert len(snapshots) == 3


class TestChatMessages:
    def test_add_and_retrieve_messages(self, initialized_db):
        _, conn = initialized_db
        from db.queries import add_chat_message, get_chat_messages

        uid1 = add_chat_message(conn, "default", "user", "Hello FinAlly!")
        time.sleep(0.01)
        uid2 = add_chat_message(conn, "default", "assistant", "Hi there!", actions=None)

        assert isinstance(uid1, str) and len(uid1) == 36
        assert isinstance(uid2, str) and len(uid2) == 36

        messages = get_chat_messages(conn, "default")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_messages_ordered_oldest_first(self, initialized_db):
        _, conn = initialized_db
        from db.queries import add_chat_message, get_chat_messages

        for i in range(5):
            add_chat_message(conn, "default", "user", f"Message {i}")
            time.sleep(0.01)

        messages = get_chat_messages(conn, "default")
        contents = [m["content"] for m in messages]
        assert contents == [f"Message {i}" for i in range(5)]

    def test_limit_returns_last_n_messages(self, initialized_db):
        _, conn = initialized_db
        from db.queries import add_chat_message, get_chat_messages

        for i in range(10):
            add_chat_message(conn, "default", "user", f"msg {i}")
            time.sleep(0.005)

        messages = get_chat_messages(conn, "default", limit=3)
        assert len(messages) == 3
        # Should be the last 3, in chronological order
        assert messages[-1]["content"] == "msg 9"
        assert messages[-2]["content"] == "msg 8"
        assert messages[-3]["content"] == "msg 7"

    def test_actions_serialised_and_deserialised(self, initialized_db):
        _, conn = initialized_db
        from db.queries import add_chat_message, get_chat_messages

        actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}
        add_chat_message(conn, "default", "assistant", "Bought AAPL", actions=actions)

        messages = get_chat_messages(conn, "default")
        assert messages[0]["actions"] == actions  # round-tripped as dict

    def test_no_actions_stored_as_none(self, initialized_db):
        _, conn = initialized_db
        from db.queries import add_chat_message, get_chat_messages

        add_chat_message(conn, "default", "user", "Just a question")
        messages = get_chat_messages(conn, "default")
        assert messages[0]["actions"] is None


class TestPruneSnapshots:
    def test_old_snapshots_deleted(self, initialized_db):
        """Snapshots with recorded_at older than 24 hours should be pruned."""
        _, conn = initialized_db
        from db.queries import prune_old_snapshots

        # Directly insert an old snapshot bypassing record_portfolio_snapshot
        # (which would auto-prune before we can test)
        old_ts = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        import uuid as _uuid
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
            VALUES (?, 'default', 9999.0, ?)
            """,
            (str(_uuid.uuid4()), old_ts),
        )

        # Also insert a recent snapshot
        recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
            VALUES (?, 'default', 10500.0, ?)
            """,
            (str(_uuid.uuid4()), recent_ts),
        )

        prune_old_snapshots(conn, "default", keep_hours=24)

        remaining = conn.execute(
            "SELECT total_value FROM portfolio_snapshots WHERE user_id='default'"
        ).fetchall()
        values = [r[0] for r in remaining]

        assert 9999.0 not in values, "Old snapshot was not pruned"
        assert 10500.0 in values, "Recent snapshot was incorrectly pruned"

    def test_recent_snapshots_kept(self, initialized_db):
        """Snapshots within the keep window must survive pruning."""
        _, conn = initialized_db
        from db.queries import record_portfolio_snapshot, prune_old_snapshots, get_portfolio_snapshots

        record_portfolio_snapshot(conn, "default", 10000.0)
        record_portfolio_snapshot(conn, "default", 10200.0)

        prune_old_snapshots(conn, "default", keep_hours=24)

        snapshots = get_portfolio_snapshots(conn, "default")
        assert len(snapshots) >= 2


class TestUpdateCashBalance:
    def test_cash_balance_updated(self, initialized_db):
        _, conn = initialized_db
        from db.queries import update_cash_balance, get_user_profile

        update_cash_balance(conn, "default", 7500.0)
        profile = get_user_profile(conn, "default")
        assert profile["cash_balance"] == 7500.0

    def test_get_nonexistent_user_raises(self, initialized_db):
        _, conn = initialized_db
        from db.queries import get_user_profile

        with pytest.raises(KeyError):
            get_user_profile(conn, "nonexistent_user")
