# Phase 1: Database & Backend Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 1-database-backend-foundation
**Areas discussed:** DB access library, App entry point location, Startup wiring

---

## DB Access Library

| Option | Description | Selected |
|--------|-------------|----------|
| sqlite3 (sync, stdlib) | Python's built-in library. FastAPI runs sync functions in a thread pool. Zero extra dependencies. | ✓ |
| aiosqlite (async) | True async SQLite. Adds a dependency, requires await everywhere. Consistent with FastAPI's async nature but overkill for a single-user app. | |

**User's choice:** sqlite3 (sync, stdlib)
**Notes:** Recommended option selected. No further discussion.

---

| Option | Description | Selected |
|--------|-------------|----------|
| One connection per request | Open a connection in each function, use it, close it. Avoids threading issues. | ✓ |
| Module-level connection singleton | Create one connection at startup, reuse everywhere. Requires check_same_thread=False. | |

**User's choice:** One connection per request
**Notes:** Recommended option selected.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Environment variable with fallback | DB_PATH env var, defaults to db/finally.db. Easy to override in tests and Docker. | ✓ |
| Hardcoded constant in db module | A single constant in db.py. Simple but harder to override in tests. | |

**User's choice:** Environment variable with fallback
**Notes:** Recommended option selected.

---

## App Entry Point Location

| Option | Description | Selected |
|--------|-------------|----------|
| backend/app/main.py | Inside the app package. uvicorn runs `app.main:app`. Consistent with existing backend/app/ structure. | ✓ |
| backend/main.py | At the backend root alongside pyproject.toml. uvicorn runs `main:app`. | |

**User's choice:** backend/app/main.py
**Notes:** Recommended option selected.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in main.py | Simple @app.get('/api/health') directly in main.py. 3 lines; separate file is overkill. | ✓ |
| Separate backend/app/routers/health.py | Its own router file, consistent with Phase 2+ router structure. | |

**User's choice:** Inline in main.py
**Notes:** Recommended option selected. Phase 2 will introduce the routers/ directory when there's more to add.

---

## Startup Wiring

| Option | Description | Selected |
|--------|-------------|----------|
| Single lifespan context manager in main.py | @asynccontextmanager lifespan handles both DB init and market data start/stop. FastAPI-idiomatic. | ✓ |
| Separate startup/shutdown event handlers | @app.on_event deprecated in FastAPI 0.93+. Still works but less preferred. | |

**User's choice:** Single lifespan context manager
**Notes:** Recommended option selected.

---

| Option | Description | Selected |
|--------|-------------|----------|
| app.state | Store shared objects on app.state during lifespan. No globals, no coupling. | ✓ |
| Module-level globals in main.py | price_cache = PriceCache() at module level. Simple but circular-import risk. | |

**User's choice:** app.state
**Notes:** Recommended option selected.

---

| Option | Description | Selected |
|--------|-------------|----------|
| backend/app/db.py (single file) | One file with init_db(), get_db_path(), schema SQL. Phase 2+ adds query functions to same file. | ✓ |
| backend/app/db/ (package) | Sub-package with schema.py, seed.py, connection.py. More organized but complex for Phase 1 scope. | |

**User's choice:** backend/app/db.py (single file)
**Notes:** Recommended option selected. Can be split into a package in a future phase if it grows too large.

---

## Claude's Discretion

- Internal variable naming, docstring style, and logging verbosity
- Whether `init_db()` is called with an explicit guard or via lifespan ordering
- SQL schema formatting style (per-table or combined block)

## Deferred Ideas

None — discussion stayed within phase scope.
