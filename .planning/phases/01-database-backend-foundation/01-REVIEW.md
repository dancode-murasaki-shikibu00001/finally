---
phase: 01-database-backend-foundation
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - backend/app/db.py
  - backend/tests/test_db.py
  - backend/app/main.py
  - backend/tests/test_main.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-06-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Four files were reviewed: the database initialization module (`db.py`), the FastAPI application entry point (`main.py`), and their corresponding test files. The database schema, seeding logic, and connection management are well-structured and idempotent. However, a critical bug exists in the SSE stream router factory — it mutates a module-level singleton router object on every call, causing duplicate route registration each time the application lifespan restarts. This is already observable in the test suite (three `TestClient` lifespans register three `/prices` routes) and will manifest in production under any hot-reload scenario. Several warnings exist around missing error-handling in the lifespan, fragile test environment isolation, and implicit transaction behavior in the DB dependency.

---

## Critical Issues

### CR-01: `create_stream_router` Mutates a Module-Level Router — Duplicate Routes on Every Lifespan

**File:** `backend/app/market/stream.py:17,26`
**Issue:** `stream.py` declares `router = APIRouter(...)` at module scope (line 17). The factory function `create_stream_router()` uses `@router.get("/prices")` inside its body (line 26), which appends a new route to that shared singleton every time the function is called. The function then returns the same singleton. In `main.py` line 37, `app.include_router(create_stream_router(cache))` is called inside the lifespan context, which runs each time the application starts.

In `test_main.py`, three separate `TestClient(app)` context managers are opened (lines 16, 26, 40). Each one triggers the full lifespan, calling `create_stream_router(cache)` three times. After all three tests run, the module-level `router` has three `Route` objects for `/prices`, all pointing to different closure instances with different `price_cache` references. FastAPI resolves to the first registered route, making the others unreachable dead code — but the bloat is permanent for the process lifetime. In any framework that supports application reload (e.g., uvicorn `--reload`) this re-registers the route on every reload, compounding the problem.

**Fix:** Instantiate a fresh `APIRouter` inside `create_stream_router()` instead of closing over the module-level singleton:

```python
# backend/app/market/stream.py

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE streaming router with a reference to the price cache."""
    # Create a NEW router each time — do NOT use the module-level singleton
    local_router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @local_router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return local_router
```

Remove the module-level `router = APIRouter(...)` line (line 17 of `stream.py`) entirely, or leave it only if other routes not created by the factory need it.

---

## Warnings

### WR-01: Lifespan Has No Cleanup Guard If `source.start()` Raises

**File:** `backend/app/main.py:18-44`
**Issue:** The lifespan startup block calls `await source.start(tickers)` on line 29 without a `try/finally`. If `source.start()` raises (e.g., a network error when `MASSIVE_API_KEY` is set, or an unexpected exception in the simulator), execution never reaches `yield` and the `await source.stop()` cleanup on line 43 is never executed. Any background tasks or OS resources partially allocated by `start()` will leak for the process lifetime.

**Fix:** Wrap the startup-to-yield block in a try/finally:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    cache = PriceCache()
    source = create_market_data_source(cache)
    tickers = list(SEED_PRICES.keys())

    try:
        await source.start(tickers)
        logger.info("Market data source started with %d tickers", len(tickers))
        app.state.price_cache = cache
        app.state.market_source = source
        app.include_router(create_stream_router(cache))
        yield
    finally:
        logger.info("Stopping market data source...")
        await source.stop()
        logger.info("FinAlly backend stopped.")
```

### WR-02: Test Environment Does Not Isolate `MASSIVE_API_KEY` — Tests May Make Real API Calls

**File:** `backend/tests/test_main.py:13-43`
**Issue:** Every test in `test_main.py` patches only `DB_PATH`. None of them patch or clear `MASSIVE_API_KEY`. The `create_market_data_source()` factory reads `MASSIVE_API_KEY` from the real environment (via `os.environ.get`). If the developer's environment has `MASSIVE_API_KEY` set (as it would be for any user running with real market data), the lifespan will instantiate a `MassiveDataSource` and `source.start()` will attempt real network connections to the Massive API. This makes the tests non-deterministic, slow, and potentially billable.

**Fix:** Explicitly clear `MASSIVE_API_KEY` in every test that triggers the lifespan, or create a shared fixture:

```python
@pytest.fixture(autouse=True)
def isolate_env(tmp_path):
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file, "MASSIVE_API_KEY": ""}):
        yield
```

Then remove the per-test `patch.dict` blocks and use the fixture instead.

### WR-03: `get_db` Dependency Does Not Commit or Rollback on Request Exceptions

**File:** `backend/db.py:113-120`
**Issue:** The `get_db` dependency yields a raw `sqlite3.Connection` with no transaction management. A caller that executes DML (`INSERT`, `UPDATE`, `DELETE`) directly against the connection without explicitly using `with conn:` (the sqlite3 auto-commit context manager) will have those changes silently discarded if the request raises an exception before the handler commits. Nothing in the dependency enforces consistent transaction boundaries, and the pattern invites divergence as new route handlers are added.

**Fix:** Either document this explicitly and enforce the convention that all DML callers must use `with conn:`, or add rollback-on-exception behavior in the dependency itself:

```python
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()   # commit if handler completed without exception
    except Exception:
        conn.rollback() # rollback on any exception
        raise
    finally:
        conn.close()
```

Note: this approach changes semantics for callers that already use `with conn:` internally (double-commit is harmless; double-rollback is harmless for SQLite), but is consistent and safe.

### WR-04: `test_sse_route_registered` Silently Passes Even When Routes Are Duplicated

**File:** `backend/tests/test_main.py:32-43`
**Issue:** The test at line 32 checks `assert "/api/stream/prices" in routes` which is a membership test. It will pass whether there is 1 route or 3 duplicate routes registered (due to CR-01). The test therefore does not catch the route duplication bug and gives a false sense of correctness. If CR-01 is fixed, this test remains correct but never detects a regression back to the broken state.

**Fix:** Assert that there is exactly one matching route:

```python
price_routes = [r for r in app.routes if getattr(r, "path", None) == "/api/stream/prices"]
assert len(price_routes) == 1, f"Expected exactly 1 /api/stream/prices route, found {len(price_routes)}"
```

---

## Info

### IN-01: `import pytest` Is Unused in Both Test Files

**File:** `backend/tests/test_db.py:7`, `backend/tests/test_main.py:6`
**Issue:** Both test files import `pytest` but never reference `pytest.*` directly. The `tmp_path` fixture is injected by pytest's parameter injection mechanism, not via `pytest.tmp_path`, so the import is unused. This will trigger a `ruff` lint warning (`F401 imported but unused`).

**Fix:** Remove `import pytest` from both files unless `pytest.raises`, `pytest.mark`, or another `pytest.*` symbol is added in future.

### IN-02: `_seed_default_data` Uses a Local Import to Avoid Circular Imports — Fragile Architecture Signal

**File:** `backend/app/db.py:97`
**Issue:** The comment `# local import to avoid circular` on line 97 is a signal that the module dependency graph has a problematic structure. `db.py` importing from `app.market.seed_prices` inside a function to break a circular dependency means `db` → `market` is a real dependency that is hidden from static analysis tools (mypy, ruff, IDE import ordering). If the circular dependency is actually `market` → `db` → `market`, it is worth resolving at the architecture level.

**Fix:** Move `SEED_PRICES` to a standalone constants module (e.g., `app/constants.py` or `app/tickers.py`) that neither `db` nor `market` imports from, allowing both to import from it at the top level. This eliminates the circular import and the hidden dependency.

---

_Reviewed: 2026-06-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
