# Phase 1: Database & Backend Foundation - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 4 new files
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/main.py` | config / app-entry | request-response + event-driven (lifespan) | `backend/app/market/stream.py` + `backend/app/market/factory.py` | role-match (no existing main.py) |
| `backend/app/db.py` | service / utility | CRUD (init + dependency) | `backend/app/market/cache.py` (shared-state object) + `backend/app/market/factory.py` (env-var-driven factory) | role-match |
| `backend/tests/test_db.py` | test | CRUD | `backend/tests/market/test_factory.py` | exact (env-patch + class structure) |
| `backend/tests/test_main.py` | test | request-response | `backend/tests/market/test_simulator_source.py` | role-match (async lifecycle) |

---

## Pattern Assignments

### `backend/app/main.py` (app entry point, request-response + lifespan)

**Primary Analog:** `backend/app/market/stream.py`
**Secondary Analog:** `backend/app/market/factory.py`

**Imports pattern** — copy from `backend/app/market/stream.py` lines 1-16 and `backend/app/market/factory.py` lines 1-13:
```python
"""FinAlly FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.market import PriceCache, create_market_data_source, stream_router
from app.market.seed_prices import SEED_PRICES

logger = logging.getLogger(__name__)
```

**Module docstring pattern** — copy from `backend/app/market/stream.py` line 1:
```python
"""SSE streaming endpoint for live price updates."""
```
Adapt to: `"""FinAlly FastAPI application entry point."""`

**Logger declaration pattern** — copy from `backend/app/market/factory.py` line 13:
```python
logger = logging.getLogger(__name__)
```

**Lifespan + app.state pattern** — no existing lifespan in codebase; use the reference pattern from RESEARCH.md §Pattern 1. Key constraints from decisions D-06 and D-07:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and market data on startup, clean up on shutdown."""
    logger.info("Starting FinAlly backend...")

    # 1. Initialize database (idempotent — CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE)
    init_db()

    # 2. Build shared objects
    cache = PriceCache()
    source = create_market_data_source(cache)
    tickers = list(SEED_PRICES.keys())
    await source.start(tickers)
    logger.info("Market data source started with %d tickers", len(tickers))

    # 3. Store on app.state — NO module-level globals (D-07)
    app.state.price_cache = cache
    app.state.market_source = source

    yield  # Application is running

    # Shutdown
    logger.info("Stopping market data source...")
    await source.stop()
    logger.info("FinAlly backend stopped.")


app = FastAPI(
    title="FinAlly",
    description="AI Trading Workstation",
    lifespan=lifespan,
)

app.include_router(stream_router)  # registered once at module level (CR-01 fix)
```

**Health endpoint pattern** — inline in main.py per D-05:
```python
@app.get("/api/health")
async def health_check():
    """Health check endpoint for Docker and deployment readiness."""
    return {"status": "ok"}
```

**`from __future__ import annotations` pattern** — copy from `backend/app/market/stream.py` line 3 and every market module:
```python
from __future__ import annotations
```
Apply to every new `.py` file in `backend/app/`.

---

### `backend/app/db.py` (service/utility, CRUD — init + per-request dependency)

**Primary Analog:** `backend/app/market/cache.py` (shared-state object, `from __future__`, module docstring, `__init__`, private `_lock`)
**Secondary Analog:** `backend/app/market/factory.py` (env-var read via `os.environ.get`, `logger = logging.getLogger(__name__)`)

**Module docstring pattern** — copy from `backend/app/market/cache.py` line 1:
```python
"""Thread-safe in-memory price cache."""
```
Adapt to: `"""Database initialization and connection management for FinAlly."""`

**Imports pattern** — modeled on `backend/app/market/factory.py` lines 1-13:
```python
"""Database initialization and connection management for FinAlly."""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends

logger = logging.getLogger(__name__)
```

**Env-var read pattern** — copy from `backend/app/market/factory.py` line 24:
```python
api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
```
Adapt to (D-03):
```python
def get_db_path() -> str:
    """Return the SQLite database path from DB_PATH env var or default."""
    return os.environ.get("DB_PATH", "db/finally.db")
```

**Logger info pattern** — copy from `backend/app/market/factory.py` lines 27, 30:
```python
logger.info("Market data source: Massive API (real data)")
logger.info("Market data source: GBM Simulator")
```
Adapt to:
```python
logger.info("Initializing database at %s", db_path)
```

**SCHEMA_SQL constant** — full `CREATE TABLE IF NOT EXISTS` block for all 6 tables per PLAN.md §7 and DB-01 through DB-07:
```python
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0.0,
    avg_cost REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
);
"""
```

**`init_db()` pattern** — executescript for DDL, then separate seed inserts per RESEARCH.md Pitfall 3:
```python
DEFAULT_USER_ID = "default"


def init_db() -> None:
    """Initialize the database: create tables and seed default data.

    Safe to call on every startup — CREATE TABLE IF NOT EXISTS and
    INSERT OR IGNORE make this idempotent.
    """
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    logger.info("Initializing database at %s", db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)   # DDL — do NOT wrap in `with conn:`
        _seed_default_data(conn)
    finally:
        conn.close()


def _seed_default_data(conn: sqlite3.Connection) -> None:
    """Insert default user and watchlist if not already present."""
    from app.market.seed_prices import SEED_PRICES  # local import to avoid circular

    now = datetime.now(timezone.utc).isoformat()
    with conn:                           # auto-commit context manager for DML
        conn.execute(
            "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, 10000.0, now),
        )
        for ticker in SEED_PRICES:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
            )
```

**`get_db()` dependency pattern** — per-request connection, D-01 / D-02 / Pattern 4 in RESEARCH.md:
```python
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield one sqlite3 connection per request, then close it."""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


DbDep = Annotated[sqlite3.Connection, Depends(get_db)]
```

---

### `backend/tests/test_db.py` (test, CRUD — unit)

**Primary Analog:** `backend/tests/market/test_factory.py`

**File header + imports pattern** — copy from `backend/tests/market/test_factory.py` lines 1-9:
```python
"""Tests for market data source factory."""

import os
from unittest.mock import patch

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource
```
Adapt to:
```python
"""Tests for database initialization and connection management."""

import os
import sqlite3
from unittest.mock import patch

import pytest

from app.db import get_db_path, init_db
```

**Env-patch pattern** — copy from `backend/tests/market/test_factory.py` lines 19-20:
```python
with patch.dict(os.environ, {}, clear=True):
    source = create_market_data_source(cache)
```
Adapt to `DB_PATH` override for every test:
```python
with patch.dict(os.environ, {"DB_PATH": str(tmp_path / "test.db")}):
    init_db()
```

**Class + docstring structure** — copy from `backend/tests/market/test_factory.py` lines 12-14:
```python
class TestFactory:
    """Tests for create_market_data_source factory."""

    def test_creates_simulator_when_no_api_key(self):
        """Test that simulator is created when MASSIVE_API_KEY is not set."""
```
Adapt to:
```python
class TestInitDb:
    """Unit tests for init_db() — schema creation and seed data."""

    def test_creates_all_six_tables(self, tmp_path):
        """All six tables must exist after init_db()."""
```

**`tmp_path` fixture usage** — pytest built-in, no import needed. Use for every test that calls `init_db()` to avoid touching the real DB:
```python
def test_creates_all_six_tables(self, tmp_path):
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file}):
        init_db()
    conn = sqlite3.connect(db_file)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"users_profile", "watchlist", "positions", "trades",
            "portfolio_snapshots", "chat_messages"} == tables
```

**Idempotency test pattern** — double-call without error, then assert no duplicate rows:
```python
def test_idempotent_on_second_call(self, tmp_path):
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file}):
        init_db()
        init_db()  # Must not raise
    conn = sqlite3.connect(db_file)
    count = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
    conn.close()
    assert count == 1  # No duplicate user
```

**Seed validation test pattern** — open the DB directly and assert row values:
```python
def test_seeds_default_user_with_10k(self, tmp_path):
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
```

**Watchlist count test pattern** — assert 10 tickers seeded (matching SEED_PRICES):
```python
def test_seeds_ten_watchlist_tickers(self, tmp_path):
    from app.market.seed_prices import SEED_PRICES
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file}):
        init_db()
    conn = sqlite3.connect(db_file)
    count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    conn.close()
    assert count == len(SEED_PRICES)
```

---

### `backend/tests/test_main.py` (test, request-response + lifespan)

**Primary Analog:** `backend/tests/market/test_simulator_source.py` (async lifecycle, `pytest.mark.asyncio`)
**Secondary Analog:** `backend/tests/market/test_factory.py` (env-patch, class structure)

**File header + imports pattern** — modeled on `backend/tests/market/test_simulator_source.py` lines 1-8:
```python
"""Integration tests for SimulatorDataSource."""

import asyncio

import pytest

from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource
```
Adapt to:
```python
"""Integration tests for main FastAPI app — health endpoint and lifespan."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
```

**TestClient with lifespan pattern** — wrap in `with` to trigger startup/shutdown (RESEARCH.md Pattern 5):
```python
def test_health_endpoint(tmp_path):
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file}):
        with TestClient(app) as client:
            response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Async lifecycle test structure** — copy from `backend/tests/market/test_simulator_source.py` lines 11-12 (class + `@pytest.mark.asyncio`):
```python
@pytest.mark.asyncio
class TestSimulatorDataSource:
    """Integration tests for the SimulatorDataSource."""
```
Note: `asyncio_mode = "auto"` is set in `pyproject.toml` line 35, so `@pytest.mark.asyncio` is optional but shown in existing tests for explicitness.

**No `asyncio` import needed for synchronous TestClient tests** — TestClient is synchronous even for async FastAPI apps; no `pytest.mark.asyncio` required for health check tests.

---

## Shared Patterns

### `from __future__ import annotations`
**Source:** Every file in `backend/app/market/` (e.g., `stream.py` line 3, `cache.py` line 3, `factory.py` line 3, `interface.py` line 3)
**Apply to:** `backend/app/main.py`, `backend/app/db.py`
```python
from __future__ import annotations
```

### Module-level logger declaration
**Source:** `backend/app/market/factory.py` line 13, `backend/app/market/stream.py` line 15
**Apply to:** `backend/app/main.py`, `backend/app/db.py`
```python
logger = logging.getLogger(__name__)
```

### Env-var read with default
**Source:** `backend/app/market/factory.py` line 24
**Apply to:** `backend/app/db.py` `get_db_path()`
```python
api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
```

### `patch.dict(os.environ, {...})` for test isolation
**Source:** `backend/tests/market/test_factory.py` lines 19-20, 25-26, 30-31, 36-37
**Apply to:** `backend/tests/test_db.py`, `backend/tests/test_main.py`
```python
with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}, clear=True):
    source = create_market_data_source(cache)
```

### Class-based test organization with docstrings
**Source:** `backend/tests/market/test_factory.py` lines 12-14; `backend/tests/market/test_cache.py` lines 6-8
**Apply to:** `backend/tests/test_db.py`
```python
class TestFactory:
    """Tests for create_market_data_source factory."""

    def test_creates_simulator_when_no_api_key(self):
        """Test that simulator is created when MASSIVE_API_KEY is not set."""
```

### pytest `asyncio_mode = "auto"` (no per-test decorator needed)
**Source:** `backend/pyproject.toml` line 35
**Apply to:** `backend/tests/test_main.py` — if async tests are needed, no `@pytest.mark.asyncio` required (but existing tests use it for explicitness)
```toml
asyncio_mode = "auto"
```

### `tmp_path` pytest fixture for file isolation
**Source:** pytest built-in — used implicitly throughout `test_simulator_source.py` style (no `tmpdir` or manual cleanup)
**Apply to:** `backend/tests/test_db.py` every test method that calls `init_db()`

---

## No Analog Found

All four new files have close analogs in the existing codebase. No files require falling back to RESEARCH.md patterns exclusively.

---

## Critical Wiring Notes for Planner

1. **`stream_router` is registered at module level via `app.include_router(stream_router)` — not inside lifespan.** The SSE handler reads `price_cache` from `request.app.state.price_cache`, which is set during lifespan startup. Calling `include_router` inside lifespan caused route accumulation across `TestClient` lifespans (CR-01 fix; see `backend/app/market/stream.py` line 17 and `backend/app/main.py` line 50).

2. **`executescript()` outside `with conn:` for DDL** — `executescript()` implicitly commits; wrapping it in `with conn:` causes double-commit. Call it directly on the connection object. (RESEARCH.md Pitfall 3.)

3. **Import `SEED_PRICES` locally inside `_seed_default_data()`** — prevents circular imports at module load time. Pattern: `from app.market.seed_prices import SEED_PRICES` inside the function body. (RESEARCH.md Pitfall 4.)

4. **`DB_PATH` env var must be overridden in every test that calls `init_db()`** — use `patch.dict(os.environ, {"DB_PATH": str(tmp_path / "test.db")})`. Pattern from `test_factory.py` lines 19-20.

5. **`app.include_router()` at module level is the correct approach** — `stream_router` is a module-level singleton that does NOT close over `PriceCache`. Instead the handler reads `request.app.state.price_cache` at request time, so `include_router` can safely be called before lifespan runs. Including inside lifespan caused triangular route accumulation across `TestClient` lifespans (CR-01 fix).

---

## Metadata

**Analog search scope:** `backend/app/market/`, `backend/tests/market/`, `backend/pyproject.toml`
**Files scanned:** 11 source files + 1 config file
**Pattern extraction date:** 2026-06-08
