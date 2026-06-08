"""Tests for database initialization and connection management."""

import os
import sqlite3
from unittest.mock import patch

from app.db import get_db_path, init_db


class TestInitDb:
    """Unit tests for init_db() — schema creation and seed data."""

    def test_creates_all_six_tables(self, tmp_path):
        """All six tables must exist after init_db()."""
        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"DB_PATH": db_file}):
            init_db()
        conn = sqlite3.connect(db_file)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        expected = {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        }
        assert expected == tables

    def test_seeds_default_user_with_10k(self, tmp_path):
        """users_profile must have a default user with cash_balance=10000.0."""
        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"DB_PATH": db_file}):
            init_db()
        conn = sqlite3.connect(db_file)
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id='default'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 10000.0

    def test_seeds_watchlist_tickers(self, tmp_path):
        """watchlist must be seeded with exactly len(SEED_PRICES) tickers."""
        from app.market.seed_prices import SEED_PRICES

        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"DB_PATH": db_file}):
            init_db()
        conn = sqlite3.connect(db_file)
        count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        conn.close()
        assert count == len(SEED_PRICES)

    def test_idempotent_on_second_call(self, tmp_path):
        """Calling init_db() twice must not raise and must not duplicate rows."""
        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"DB_PATH": db_file}):
            init_db()
            init_db()  # Must not raise
        conn = sqlite3.connect(db_file)
        count = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
        conn.close()
        assert count == 1  # No duplicate user

    def test_get_db_path_uses_env_var(self):
        """get_db_path() must return the value of the DB_PATH env var when set."""
        with patch.dict(os.environ, {"DB_PATH": "/tmp/custom.db"}):
            assert get_db_path() == "/tmp/custom.db"


def test_get_db_path_default():
    """get_db_path() must return 'db/finally.db' when DB_PATH is not set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_db_path() == "db/finally.db"
