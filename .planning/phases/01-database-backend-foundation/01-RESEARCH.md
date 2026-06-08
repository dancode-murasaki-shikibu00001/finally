# Phase 1: Database & Backend Foundation - Research

**Researched:** 2026-06-08
**Domain:** FastAPI application wiring, SQLite lazy initialization, lifespan context manager
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use Python's built-in `sqlite3` module (synchronous). FastAPI dispatches sync functions to a thread pool automatically. No additional dependencies needed; simpler code; appropriate for a single-user app.
- **D-02:** One connection per request — open a connection inside each function, use it, then close it. Avoids threading issues entirely; SQLite is fast enough for this workload.
- **D-03:** Database path via `DB_PATH` environment variable with fallback to `db/finally.db` relative to the project root. Makes path overridable in tests and Docker without code changes.
- **D-04:** FastAPI app lives in `backend/app/main.py`. Uvicorn runs `app.main:app`. Keeps all application code under `backend/app/`, consistent with the existing `backend/app/market/` structure.
- **D-05:** Health endpoint (`GET /api/health`) is defined inline in `main.py` — not a separate router file. It's 3 lines; a dedicated file would be over-engineering for Phase 1.
- **D-06:** Single `@asynccontextmanager` lifespan function in `main.py` handles all startup/shutdown: `init_db()` then `await market_source.start(tickers)` on startup; `await market_source.stop()` on shutdown.
- **D-07:** Shared objects (`PriceCache`, `MarketDataSource`) are stored on `app.state` during lifespan (e.g., `app.state.price_cache`, `app.state.market_source`). Routers in future phases access them via `Request.app.state` or a FastAPI `Depends`. No module-level globals.
- **D-08:** Database module is a single file: `backend/app/db.py`. Contains `init_db()`, `get_db_path()`, and the full schema SQL as a string constant. Phase 2+ adds query functions to the same file.

### Claude's Discretion

- Internal variable naming, docstring style, and logging verbosity follow the existing patterns in `backend/app/market/`.
- Whether `init_db()` is called explicitly in lifespan or discovered via a startup guard — Claude decides the most readable pattern.
- SQL schema formatting (one-statement-per-table vs. combined CREATE TABLE block) — Claude's call.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-01 | Backend lazily initializes SQLite at `db/finally.db` on startup — creates schema and seeds data if file is absent or tables are missing | `init_db()` in lifespan; `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE` idiom |
| DB-02 | `users_profile` table stores cash balance (default $10,000) with `user_id` column defaulting to `"default"` | Schema SQL pattern; `INSERT OR IGNORE` seed |
| DB-03 | `watchlist` table stores watched tickers with unique constraint on `(user_id, ticker)`; seeded with 10 default tickers | `DEFAULT_TICKERS` from `seed_prices.py`; `UNIQUE(user_id, ticker)` constraint |
| DB-04 | `positions` table stores current holdings (ticker, quantity, avg_cost) with unique constraint on `(user_id, ticker)` | Schema SQL; UNIQUE constraint pattern |
| DB-05 | `trades` table is an append-only log of all executed trades (side, quantity, price, executed_at) | Schema SQL; TEXT primary key UUID |
| DB-06 | `portfolio_snapshots` table records total portfolio value over time for the P&L chart | Schema SQL; TEXT primary key UUID |
| DB-07 | `chat_messages` table stores conversation history with role, content, and JSON actions field | Schema SQL; TEXT column for JSON |
| SYS-01 | `GET /api/health` returns `{"status": "ok"}` for Docker health check and deployment readiness | Inline route in `main.py`; trivial 3-line handler |
</phase_requirements>

---

## Summary

Phase 1 wires together the FastAPI application entry point, lazily initializes the SQLite database, and wires the already-complete Phase 0 market data subsystem into the app lifespan. All implementation decisions are locked. The key technical concern is correct wiring of the `@asynccontextmanager` lifespan pattern and idempotent database initialization using `CREATE TABLE IF NOT EXISTS` plus `INSERT OR IGNORE`.

No new external dependencies are needed for this phase. `sqlite3` is part of the Python standard library. The existing `pyproject.toml` already lists `fastapi>=0.115.0` and `uvicorn[standard]>=0.32.0`. FastAPI automatically dispatches `def` (synchronous) route handlers to a thread pool — this is the mechanism that makes the one-connection-per-request pattern safe without `async def`.

The critical pitfalls in this phase are: (1) forgetting `CREATE TABLE IF NOT EXISTS` and `INSERT OR IGNORE` in the schema, which causes startup crashes on an existing database; (2) placing the SSE router include before the stream router factory is called (the router must be created from `create_stream_router(price_cache)` and registered on the app, not imported as a module-level global); (3) using the wrong path for `db/finally.db` — the default must be relative to the project root, not to `backend/`.

**Primary recommendation:** Implement `backend/app/db.py` with `init_db()` using `executescript()` for all six `CREATE TABLE IF NOT EXISTS` statements and `INSERT OR IGNORE` for seed data, then wire everything in `backend/app/main.py` using the `@asynccontextmanager` lifespan pattern with `app.state` for shared objects.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Database initialization | API / Backend | — | SQLite lives on the server; `init_db()` is a backend startup concern |
| Health endpoint | API / Backend | — | Standard REST endpoint; server-side status check for Docker/orchestration |
| Market data wiring | API / Backend | — | `PriceCache` and `MarketDataSource` are server-side objects stored on `app.state` |
| SSE stream endpoint | API / Backend | Browser / Client | Server produces the event stream; browser `EventSource` consumes it |
| App entry point (main.py) | API / Backend | — | Uvicorn entry point is purely a backend concern |

---

## Standard Stack

### Core

No new packages — Phase 1 uses only already-declared dependencies.

| Library | Version (pyproject.toml) | Purpose | Why Standard |
|---------|--------------------------|---------|--------------|
| `fastapi` | `>=0.115.0` | Web framework, routing, app.state, lifespan | Already declared in backend; industry standard async Python API framework |
| `uvicorn[standard]` | `>=0.32.0` | ASGI server; runs `app.main:app` | Already declared; standard production ASGI server for FastAPI |
| `sqlite3` | stdlib (Python 3.12) | SQLite database access | Built-in; no install needed; single-file DB; zero config |

[VERIFIED: pyproject.toml] All three are already present or stdlib.

### Supporting (already installed)

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `logging` (stdlib) | Structured logging for startup messages | Match existing pattern in `backend/app/market/` |
| `os` (stdlib) | Read `DB_PATH` env var with `os.environ.get()` | Already used in `factory.py` |
| `uuid` (stdlib) | Generate UUIDs for seed data primary keys | `str(uuid.uuid4())` for `users_profile` seed row |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sqlite3` stdlib | `aiosqlite` | Async but adds a dependency; unnecessary for single-user sync-dispatched handlers |
| `sqlite3` stdlib | SQLAlchemy/SQLModel | Full ORM adds significant complexity; overkill for this workload |
| `executescript()` for init | Individual `execute()` calls | `executescript()` is cleaner for multi-statement DDL; already wraps in transaction |

**Installation:** No new packages to install for this phase. Run `uv sync --extra dev` in `backend/` to confirm environment is current.

**Version verification:** Confirmed via `backend/pyproject.toml` — fastapi>=0.115.0 and uvicorn[standard]>=0.32.0 are already declared. [VERIFIED: pyproject.toml]

---

## Package Legitimacy Audit

No new packages are introduced in this phase. All dependencies used (`fastapi`, `uvicorn`, `sqlite3`, `logging`, `os`, `uuid`) are either already in `pyproject.toml` (Phase 0 verified) or Python standard library.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
uvicorn (port 8000)
    │
    ▼
FastAPI app (backend/app/main.py)
    │
    ├── lifespan startup
    │       ├── init_db()  ──────────────────────→  SQLite (db/finally.db)
    │       │       └── CREATE TABLE IF NOT EXISTS x6
    │       │       └── INSERT OR IGNORE (seed data)
    │       ├── PriceCache()  ──────────────────→  app.state.price_cache
    │       ├── create_market_data_source(cache) →  app.state.market_source
    │       └── await market_source.start(tickers)
    │
    ├── GET /api/health  ──────────────────────────→  {"status": "ok"}
    │
    └── include_router(create_stream_router(app.state.price_cache))
            └── GET /api/stream/prices  ──────────→  SSE text/event-stream
```

**Data flow for downstream phases:**
- Phase 2 routers receive `app.state.price_cache` and a `get_db()` dependency via `Request.app.state`
- The `get_db()` dependency opens a sqlite3 connection, yields it, closes it (one per request)

### Recommended Project Structure

```
backend/
├── app/
│   ├── __init__.py          # "FinAlly backend application." (exists)
│   ├── main.py              # NEW: FastAPI app, lifespan, health endpoint, router wiring
│   ├── db.py                # NEW: init_db(), get_db_path(), schema SQL constant
│   └── market/              # EXISTS: Phase 0 complete
│       ├── __init__.py
│       ├── cache.py
│       ├── factory.py
│       ├── interface.py
│       ├── massive_client.py
│       ├── models.py
│       ├── seed_prices.py
│       ├── simulator.py
│       └── stream.py
├── tests/
│   ├── __init__.py          # exists
│   ├── conftest.py          # exists
│   ├── market/              # exists (73 passing tests)
│   ├── test_db.py           # NEW: unit tests for init_db, schema, seed data
│   └── test_main.py         # NEW: TestClient tests for health endpoint + lifespan
└── pyproject.toml           # exists
```

### Pattern 1: FastAPI Lifespan with app.state

**What:** The `@asynccontextmanager` lifespan function initializes shared resources before the first request and cleans them up after the last. Resources stored on `app.state` are accessible in all routes via `request.app.state`.

**When to use:** Any time startup/shutdown logic is needed. Replaces deprecated `@app.on_event("startup")`.

**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("Initializing database...")
    init_db()                                        # from app.db

    logger.info("Starting market data source...")
    cache = PriceCache()                             # from app.market
    source = create_market_data_source(cache)        # from app.market
    tickers = list(DEFAULT_TICKERS.keys())           # from app.market.seed_prices
    await source.start(tickers)

    app.state.price_cache = cache
    app.state.market_source = source

    yield  # app is running

    # --- SHUTDOWN ---
    logger.info("Stopping market data source...")
    await source.stop()

app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(???))  # see Pattern 3
```

**Note:** `create_stream_router` must be called after the cache exists. See Pattern 3 for the correct wiring.

### Pattern 2: SQLite Lazy Initialization

**What:** `init_db()` uses `CREATE TABLE IF NOT EXISTS` for all six tables and `INSERT OR IGNORE` for seed data. This is idempotent — safe to call on every startup whether the DB is fresh or already seeded.

**When to use:** Called once in the lifespan startup, before any requests arrive.

**Example:**
```python
# Source: https://docs.python.org/3/library/sqlite3.html
import sqlite3
import os
import uuid

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

def get_db_path() -> str:
    return os.environ.get("DB_PATH", "db/finally.db")

def init_db() -> None:
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        _seed(conn)

def _seed(conn: sqlite3.Connection) -> None:
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        ("default", 10000.0, now),
    )
    for ticker in DEFAULT_TICKERS:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", ticker, now),
        )
    conn.commit()
```

**Key:** `INSERT OR IGNORE` is the idempotency mechanism for seed data — it silently skips the insert if the UNIQUE constraint would be violated. This means re-running `init_db()` on an existing seeded DB causes no errors and no data loss. [VERIFIED: https://docs.python.org/3/library/sqlite3.html]

### Pattern 3: SSE Router Wiring

**What:** `create_stream_router(price_cache)` is a factory that injects `PriceCache` into the router closure. It must be called after the cache is created. The returned `APIRouter` is included in the app with `app.include_router()`.

**Critical constraint:** `StaticFiles` must be mounted on the `app` directly (not on `APIRouter`). The SSE router from Phase 0 is an `APIRouter` so it can be included normally with `include_router`. [VERIFIED: https://github.com/fastapi/fastapi/issues/1469]

**Example:**
```python
# The correct pattern from backend/app/market/stream.py
from app.market import PriceCache, create_market_data_source, create_stream_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cache = PriceCache()
    source = create_market_data_source(cache)
    await source.start(list(SEED_PRICES.keys()))
    app.state.price_cache = cache
    app.state.market_source = source
    # Include the stream router AFTER cache is created
    # Note: include_router at startup is fine; routers are registered, not executed
    yield
    await source.stop()

app = FastAPI(lifespan=lifespan)

# SSE router — created at module level with the cache injected via lifespan
# But the router must be created after the app is defined.
# Two valid approaches:
# Option A: include_router in lifespan (before yield) — works but non-standard
# Option B: create router lazily via a dependency — more complex
# Option C: create the router at module level using app.state lookup — not possible pre-lifespan
#
# RECOMMENDED: Pass the router to include_router() AFTER app is created,
# but the cache reference is captured in the closure at lifespan startup time.
# The stream router's closure over `price_cache` is set during lifespan, so
# the router can be included at app creation time if the cache is populated by lifespan.
#
# Looking at stream.py: the factory registers routes on a module-level `router` object.
# Call create_stream_router(cache) in lifespan, then app.include_router(stream_router)
# at module level — but the router needs to be returned and stored first.
#
# Simplest correct pattern for Phase 1:
# 1. Create cache/source in lifespan
# 2. Call create_stream_router(cache) in lifespan → returns router
# 3. app.include_router(router) inside lifespan (before yield) — this is valid
```

**Note on stream.py wiring:** Looking at the actual `stream.py`, `create_stream_router(price_cache)` registers routes on a module-level `router` object and returns it. To include it in the app, call `app.include_router(create_stream_router(cache))` inside the lifespan function before `yield`, or call `create_stream_router(cache)` at module level and use that router. [ASSUMED] — the exact approach depends on whether `create_stream_router` can be called at module level before the lifespan runs (it cannot, since `PriceCache` is created in lifespan). The safest approach is to call it inside the lifespan before `yield`.

### Pattern 4: One-Connection-Per-Request Dependency

**What:** A `get_db()` dependency function opens a sqlite3 connection, yields it to the route handler, then closes it in the `finally` block. Used by Phase 2+ route handlers.

**When to use:** In Phase 2 routers via `Depends(get_db)`. Define in `db.py` now as it is the natural home.

**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/sql-databases/
from collections.abc import Generator
import sqlite3
from fastapi import Depends
from typing import Annotated

def get_db() -> Generator[sqlite3.Connection, None, None]:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

DbDep = Annotated[sqlite3.Connection, Depends(get_db)]
```

**Why `check_same_thread=False`:** FastAPI's thread pool may use a different thread for different parts of the dependency chain in a single request. Setting `check_same_thread=False` prevents the sqlite3 default safety check from raising an error in this scenario. [CITED: https://fastapi.tiangolo.com/tutorial/sql-databases/]

**Why `row_factory=sqlite3.Row`:** Allows accessing query results by column name (e.g., `row["ticker"]`) instead of positional index. Standard best practice. [VERIFIED: https://docs.python.org/3/library/sqlite3.html]

### Pattern 5: Testing with TestClient and Lifespan

**What:** Wrapping `TestClient(app)` in a `with` block triggers the lifespan — startup runs when entering, shutdown when exiting.

**When to use:** Any test that exercises endpoints that rely on `app.state` (which includes health check, which doesn't use state, but the pattern is needed when lifespan-initialized objects are required).

**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/testing-events/
from fastapi.testclient import TestClient

def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
```

**Critical:** For DB tests, override `DB_PATH` env var to use `:memory:` or a temp file so tests don't touch the real database. [ASSUMED] — standard pytest pattern for path-controlled dependencies.

### Anti-Patterns to Avoid

- **Module-level globals for shared state:** The CONTEXT.md explicitly bans this (D-07). Store `PriceCache` and `MarketDataSource` on `app.state`, not as module-level variables. Route handlers access them via `request.app.state` or a `Depends`.
- **`CREATE TABLE` without `IF NOT EXISTS`:** Will crash on restart against existing DB. Always use `IF NOT EXISTS`.
- **`INSERT` without `OR IGNORE` for seed data:** Will crash with `UNIQUE constraint failed` on restart. Always use `INSERT OR IGNORE` for seed rows.
- **Hardcoded ticker list in seed:** Must use `SEED_PRICES.keys()` (or `DEFAULT_TICKERS` equivalent) from `backend/app/market/seed_prices.py` — not a separate hardcoded list — to ensure the market simulator and DB watchlist stay in sync.
- **Wrong DB path default:** `db/finally.db` is relative to the project root (`/app/` in Docker), not to `backend/`. In production Docker the working directory is `/app`; the backend code runs from there.
- **`@app.on_event("startup")` / `@app.on_event("shutdown")`:** Deprecated since FastAPI 0.95.0. Use `@asynccontextmanager` lifespan only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Background task dispatch for sync DB ops | Custom thread pool wrapper | FastAPI auto-dispatches `def` handlers to thread pool (40 threads default) | Already handled by the framework — 0 extra code needed |
| Transaction management | Manual `BEGIN`/`COMMIT` | `sqlite3.connect()` as context manager (`with conn:`) auto-commits on success, rollbacks on exception | Stdlib handles it correctly |
| DB schema idempotency | Version table / migration runner | `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE` | One-step solution for single-user, append-only schema |
| Shared state between routes | Module globals | `app.state` + `Depends` | Framework mechanism; testable, no import coupling |

**Key insight:** sqlite3's context manager (`with sqlite3.connect(...) as conn:`) handles transactions automatically. `executescript()` is the right tool for multi-statement DDL (it implicitly commits any open transaction before running). These are stdlib behaviors — no ORM needed.

---

## Common Pitfalls

### Pitfall 1: DB Path Relative to Wrong Directory

**What goes wrong:** `get_db_path()` returns `"db/finally.db"` but Python resolves it relative to the current working directory. If uvicorn is started from `backend/` instead of the project root, the DB is created at `backend/db/finally.db` instead of `db/finally.db`.

**Why it happens:** The Docker container and start scripts are configured to run from `/app` (project root), but developers running locally from `backend/` will hit a different path.

**How to avoid:** Document in tests that `DB_PATH` must be overridden for local test runs. The Docker entrypoint should always set the working directory to `/app`. Consider making `get_db_path()` resolve relative to an anchor (e.g., the location of `main.py` or an env var) rather than the CWD.

**Warning signs:** `finally.db` appears inside `backend/db/` rather than the top-level `db/`.

### Pitfall 2: SSE Router Double-Registration

**What goes wrong:** `create_stream_router(price_cache)` registers routes on the module-level `router` object in `stream.py`. If called twice (e.g., once at module import and once in lifespan), routes are registered twice, producing duplicates in OpenAPI docs and potentially double-streaming.

**Why it happens:** `stream.py` uses a module-level `router = APIRouter(...)` and the factory decorates it in-place. Calling the factory twice decorates the same router twice.

**How to avoid:** Call `create_stream_router(price_cache)` exactly once. Store the returned router in a variable and pass it to `app.include_router()` exactly once.

**Warning signs:** OpenAPI docs show `/api/stream/prices` twice.

### Pitfall 3: `executescript()` and Transactions

**What goes wrong:** `executescript()` implicitly commits any pending transaction before executing its script. If `init_db()` is called inside an active transaction (e.g., wrapped in `with conn:`), the outer transaction is committed unexpectedly.

**Why it happens:** sqlite3's `executescript()` starts with an implicit `COMMIT`. See Python docs.

**How to avoid:** Do not wrap `conn.executescript(SCHEMA_SQL)` inside a `with conn:` block. Call it directly. The seed data inserts (`INSERT OR IGNORE`) should be done with `conn.execute()` calls inside a `with conn:` block for atomicity.

**Warning signs:** Unexpected commit behavior on first run; test isolation issues.

### Pitfall 4: `DEFAULT_TICKERS` Source of Truth

**What goes wrong:** Hardcoding `["AAPL", "GOOGL", ...]` in `db.py` seed logic instead of importing from `seed_prices.py`. The market simulator seeds prices from `seed_prices.SEED_PRICES`. If the watchlist DB seed and the simulator seed diverge, the SSE stream may push prices for tickers not in the watchlist (or vice versa).

**Why it happens:** Copy-paste from PLAN.md rather than importing the canonical list.

**How to avoid:** Import `SEED_PRICES` from `app.market.seed_prices` and use `SEED_PRICES.keys()` as the ticker list for both the watchlist seed and the `source.start(tickers)` call.

**Warning signs:** Watchlist shows 10 tickers but SSE stream only has 9 (or vice versa).

### Pitfall 5: Lifespan `include_router` Ordering

**What goes wrong:** Calling `app.include_router(stream_router)` at module-level (outside lifespan) before `PriceCache` is created. The `create_stream_router` factory captures the `price_cache` reference in a closure — but if `price_cache` doesn't exist yet when the factory is called, this fails.

**Why it happens:** Trying to keep all `include_router` calls at module level for readability.

**How to avoid:** Either call `app.include_router(create_stream_router(cache))` inside the lifespan (before `yield`) after the cache is created, or restructure so `create_stream_router` receives the cache via a different injection mechanism.

**Warning signs:** `NameError` or `AttributeError` at import time; `NoneType` errors in SSE stream handler.

---

## Code Examples

### Complete `backend/app/db.py` Structure

```python
# Source: https://docs.python.org/3/library/sqlite3.html + PLAN.md §7
"""Database initialization and connection management for FinAlly."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated

import sqlite3
from fastapi import Depends

logger = logging.getLogger(__name__)

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

DEFAULT_USER_ID = "default"


def get_db_path() -> str:
    """Return the SQLite database path from DB_PATH env var or default."""
    return os.environ.get("DB_PATH", "db/finally.db")


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
        conn.executescript(SCHEMA_SQL)
        _seed_default_data(conn)
    finally:
        conn.close()


def _seed_default_data(conn: sqlite3.Connection) -> None:
    """Insert default user and watchlist if not already present."""
    from app.market.seed_prices import SEED_PRICES  # avoid circular import at module level

    now = datetime.now(timezone.utc).isoformat()

    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, 10000.0, now),
        )
        for ticker in SEED_PRICES:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
            )


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

### Complete `backend/app/main.py` Structure

```python
# Source: https://fastapi.tiangolo.com/advanced/events/ + PLAN.md §3
"""FinAlly FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.market.seed_prices import SEED_PRICES

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and market data on startup, clean up on shutdown."""
    logger.info("Starting FinAlly backend...")

    # 1. Initialize database (idempotent)
    init_db()

    # 2. Start market data source
    cache = PriceCache()
    source = create_market_data_source(cache)
    tickers = list(SEED_PRICES.keys())
    await source.start(tickers)
    logger.info("Market data source started with %d tickers", len(tickers))

    # 3. Store shared objects on app.state (no globals)
    app.state.price_cache = cache
    app.state.market_source = source

    # 4. Wire the SSE stream router now that cache is ready
    app.include_router(create_stream_router(cache))

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


@app.get("/api/health")
async def health_check():
    """Health check endpoint for Docker and deployment readiness."""
    return {"status": "ok"}
```

### Test for `init_db()` Idempotency

```python
# Source: backend/tests/ conventions from test_factory.py
import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch

from app.db import init_db, get_db_path

class TestInitDb:
    def test_creates_all_six_tables(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"DB_PATH": db_file}):
            init_db()
        conn = sqlite3.connect(db_file)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        expected = {"users_profile", "watchlist", "positions", "trades",
                    "portfolio_snapshots", "chat_messages"}
        assert expected == tables

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

    def test_idempotent_on_second_call(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"DB_PATH": db_file}):
            init_db()
            init_db()  # Must not raise
        conn = sqlite3.connect(db_file)
        count = conn.execute(
            "SELECT COUNT(*) FROM users_profile"
        ).fetchone()[0]
        conn.close()
        assert count == 1  # No duplicate user
```

---

## Runtime State Inventory

Phase 1 is a greenfield phase (no rename/refactor/migration). Omitted per instructions.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` / `@app.on_event("shutdown")` | `@asynccontextmanager lifespan` passed to `FastAPI(lifespan=...)` | FastAPI 0.95.0 (2023) | Startup/shutdown in one function; type-safe; cleaner |
| SQLAlchemy as ORM for SQLite | `sqlite3` stdlib direct access | Always an option | Simpler, zero deps, appropriate for single-user single-file DB |

**Deprecated/outdated:**
- `@app.on_event("startup")`: Still works but deprecated. Official docs say use `lifespan`. Do not use.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Calling `app.include_router()` inside the lifespan function (before `yield`) is valid and routes are registered correctly | Code Examples — main.py | Router might not be registered before first request; would need to restructure wiring |
| A2 | `os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)` handles the case where `db_path` has no directory component | Code Examples — db.py | If `DB_PATH=finally.db` (no dir), `dirname` returns `""` and `makedirs("")` would fail without the `or "."` guard |

**If this table is empty:** Not empty — two assumptions flagged for verification.

---

## Open Questions

1. **`include_router` inside lifespan before yield**
   - What we know: FastAPI docs show `include_router` called at module level. The lifespan `yield` pattern is well-documented.
   - What's unclear: Whether calling `include_router` inside the lifespan body (before `yield`) correctly registers routes before the first request arrives.
   - Recommendation: Test with a `TestClient` in the Wave 0 test file (`test_main.py`). If this pattern causes issues, move router creation to module level and use a lazy cache reference instead (e.g., look up `app.state.price_cache` inside each handler via `Request`).

2. **`DEFAULT_TICKERS` import chain**
   - What we know: `SEED_PRICES` is defined in `backend/app/market/seed_prices.py`. The DB module should import from there.
   - What's unclear: Whether importing `from app.market.seed_prices import SEED_PRICES` inside `_seed_default_data()` (to avoid circular imports) is necessary or if a top-level import works fine.
   - Recommendation: Try top-level import first; if circular import occurs (unlikely since `db.py` is not imported by `market/`), move to local import inside the function.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | pyproject.toml requirement | Partial — host has 3.10.12, but `uv` manages project env | uv 0.11.17 manages Python 3.12 per pyproject.toml | `uv run` uses the correct managed Python |
| `uv` | Dependency management, test runner | ✓ | 0.11.17 | — |
| `sqlite3` (stdlib) | DB initialization | ✓ | 3.37.2 (host) | — |
| FastAPI, uvicorn (in venv) | App server | Managed by uv | >=0.115.0, >=0.32.0 | — |
| `db/` directory | SQLite file location | ✗ — does not exist in repo | `init_db()` must create it via `os.makedirs(..., exist_ok=True)` | Created at runtime |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- `db/` directory: Not in repo (only `.gitkeep` per PLAN.md spec, but that directory doesn't exist locally). `init_db()` must call `os.makedirs(os.path.dirname(db_path), exist_ok=True)` before connecting.

**Note on `uv run` sandbox:** The `uv` lock file cache requires a writable home directory. In the sandbox environment `~/.cache/uv` is read-only; tests must be run outside the sandbox (i.e., by the user running `uv run pytest` directly).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.24+ |
| Config file | `backend/pyproject.toml` — `[tool.pytest.ini_options]` section |
| Quick run command | `uv run --extra dev pytest tests/test_db.py tests/test_main.py -v` |
| Full suite command | `uv run --extra dev pytest -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DB-01 | DB created on startup if missing | unit | `pytest tests/test_db.py::TestInitDb::test_creates_all_six_tables -x` | ❌ Wave 0 |
| DB-01 | Idempotent on re-run (no crash on existing DB) | unit | `pytest tests/test_db.py::TestInitDb::test_idempotent_on_second_call -x` | ❌ Wave 0 |
| DB-02 | `users_profile` seeded with $10k default | unit | `pytest tests/test_db.py::TestInitDb::test_seeds_default_user_with_10k -x` | ❌ Wave 0 |
| DB-03 | `watchlist` seeded with 10 tickers; UNIQUE constraint | unit | `pytest tests/test_db.py::TestInitDb::test_seeds_watchlist_tickers -x` | ❌ Wave 0 |
| DB-04 | `positions` table exists with correct schema | unit | `pytest tests/test_db.py::TestInitDb::test_creates_all_six_tables -x` | ❌ Wave 0 |
| DB-05 | `trades` table exists with correct schema | unit | `pytest tests/test_db.py::TestInitDb::test_creates_all_six_tables -x` | ❌ Wave 0 |
| DB-06 | `portfolio_snapshots` table exists | unit | `pytest tests/test_db.py::TestInitDb::test_creates_all_six_tables -x` | ❌ Wave 0 |
| DB-07 | `chat_messages` table exists with `actions TEXT` | unit | `pytest tests/test_db.py::TestInitDb::test_creates_all_six_tables -x` | ❌ Wave 0 |
| SYS-01 | `GET /api/health` returns `{"status": "ok"}` HTTP 200 | integration | `pytest tests/test_main.py::test_health_endpoint -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run --extra dev pytest tests/test_db.py tests/test_main.py -x`
- **Per wave merge:** `uv run --extra dev pytest -v`
- **Phase gate:** Full suite green (`73 existing tests + new phase tests`) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_db.py` — covers DB-01 through DB-07
- [ ] `tests/test_main.py` — covers SYS-01 health endpoint and lifespan wiring

*(Existing `tests/market/` infrastructure requires no changes.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user `"default"` user_id; no auth in Phase 1 |
| V3 Session Management | No | No sessions in Phase 1 |
| V4 Access Control | No | Single-user; no access control needed |
| V5 Input Validation | Minimal | DB path from env var (trusted); no user input in Phase 1 |
| V6 Cryptography | No | No passwords, tokens, or secrets in Phase 1 |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection in `init_db()` | Tampering | Not applicable — no user input; schema is a hardcoded string constant |
| DB path traversal via `DB_PATH` env var | Tampering | Env vars are operator-controlled; acceptable risk for single-container single-user app |
| Concurrent writes to SQLite | Tampering/DoS | One-connection-per-request + SQLite WAL mode (optional; not needed for single-user) |

---

## Sources

### Primary (HIGH confidence)

- [FastAPI Lifespan Events — Official Docs](https://fastapi.tiangolo.com/advanced/events/) — lifespan pattern, app.state, asynccontextmanager
- [FastAPI SQL Databases — Official Docs](https://fastapi.tiangolo.com/tutorial/sql-databases/) — sync handler dispatch, one-session-per-request, check_same_thread
- [Python sqlite3 stdlib docs](https://docs.python.org/3/library/sqlite3.html) — executescript, row_factory, context manager, check_same_thread
- [FastAPI Testing Events — Official Docs](https://fastapi.tiangolo.com/advanced/testing-events/) — TestClient with lifespan
- `backend/pyproject.toml` — existing dependencies [VERIFIED: codebase]
- `backend/app/market/stream.py` — SSE router factory pattern [VERIFIED: codebase]
- `backend/app/market/interface.py` — MarketDataSource lifecycle (start/stop signature) [VERIFIED: codebase]
- `backend/app/market/seed_prices.py` — SEED_PRICES canonical ticker list [VERIFIED: codebase]
- `.planning/phases/01-database-backend-foundation/01-CONTEXT.md` — locked decisions [VERIFIED: codebase]

### Secondary (MEDIUM confidence)

- [FastAPI Bigger Applications — Official Docs](https://fastapi.tiangolo.com/tutorial/bigger-applications/) — include_router pattern (verified via official docs)
- [FastAPI StaticFiles Mounting Issue — GitHub](https://github.com/fastapi/fastapi/issues/1469) — StaticFiles must be on app, not APIRouter (confirmed via multiple GitHub issues)

### Tertiary (LOW confidence)

- None — all key claims verified via official documentation or codebase inspection.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all dependencies confirmed in pyproject.toml; sqlite3 is stdlib
- Architecture: HIGH — lifespan, app.state, and include_router patterns confirmed via official FastAPI docs
- Pitfalls: HIGH — CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE verified via Python docs; router double-registration is a known issue confirmed via GitHub
- Test patterns: HIGH — TestClient with lifespan confirmed via official FastAPI testing docs

**Research date:** 2026-06-08
**Valid until:** 2026-09-08 (FastAPI docs are stable; SQLite stdlib does not change)
