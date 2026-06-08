---
phase: 01-database-backend-foundation
plan: 02
subsystem: app-entry-point
tags: [fastapi, lifespan, asynccontextmanager, health-endpoint, sse-wiring, tdd]

# Dependency graph
requires:
  - "backend/app/db.py: init_db() (from Plan 01)"
  - "backend/app/market/__init__.py: PriceCache, create_market_data_source, stream_router (Phase 0)"
  - "backend/app/market/seed_prices.py: SEED_PRICES (Phase 0)"
provides:
  - "backend/app/main.py: FastAPI app entry point with lifespan, health endpoint, router wiring"
  - "GET /api/health: returns {\"status\": \"ok\"} HTTP 200 (SYS-01)"
  - "Lifespan wiring: init_db() -> PriceCache -> market source -> app.state -> SSE router"
  - "app.state.price_cache and app.state.market_source for Phase 2+ route handlers"
affects: [02-portfolio-api, 03-watchlist-api, 04-chat-api, 05-frontend, 06-docker-e2e]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asynccontextmanager lifespan pattern (replaces deprecated @app.on_event)"
    - "app.state for shared objects — no module-level globals (D-07)"
    - "app.include_router(stream_router) at module level; SSE handler reads price_cache from request.app.state.price_cache (CR-01 fix applied post-execution)"
    - "TestClient route-list inspection instead of streaming HTTP call for SSE route test"
    - "TDD RED/GREEN cycle: test file committed first with failing tests, then implementation"

key-files:
  created:
    - backend/app/main.py
    - backend/tests/test_main.py
  modified: []

key-decisions:
  - "Lifespan wiring order: init_db() first, then PriceCache, then market source start, then app.state assignment, then SSE router include (D-06)"
  - "No module-level globals for PriceCache or MarketDataSource — stored on app.state (D-07)"
  - "stream_router registered once at module level via app.include_router(stream_router); SSE handler reads cache from request.app.state.price_cache (CR-01 fix applied post-execution)"
  - "Health endpoint defined inline in main.py — not a separate router file (D-05)"
  - "SSE route test checks app.routes list rather than making an HTTP call — avoids test hanging on infinite SSE stream"

patterns-established:
  - "Pattern: lifespan as single assembly point for all subsystems — init_db then market source then routers"
  - "Pattern: app.state.price_cache and app.state.market_source accessible to Phase 2+ routers via request.app.state"
  - "Pattern: TestClient route-list inspection for routes that return infinite/streaming responses"

requirements-completed: [SYS-01]

# Metrics
duration: 8min
completed: 2026-06-08
---

# Phase 1 Plan 02: FastAPI App Entry Point Summary

**FastAPI app entry point with asynccontextmanager lifespan wiring SQLite init, market data source, SSE router, and health endpoint using no module-level globals**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-08T04:55:57Z
- **Completed:** 2026-06-08T05:03:XX Z
- **Tasks:** 2 (RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Created `backend/tests/test_main.py` with 3 failing tests (RED phase) for health endpoint, lifespan startup, and SSE route registration
- Created `backend/app/main.py` with full lifespan pattern: init_db() -> PriceCache -> market source -> app.state -> SSE router include (GREEN phase)
- All 3 new tests pass; full suite (82 tests: 73 existing + 6 DB + 3 main) green with no regressions
- GET /api/health returns {"status": "ok"} with HTTP 200 (SYS-01 complete)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_main.py with integration tests (RED)** - `c3d790b` (test)
2. **Task 2: Implement main.py and make all tests pass (GREEN)** - `9bb337c` (feat)

_TDD plan: test commit first (RED), then implementation commit (GREEN)_

## Files Created/Modified

- `backend/app/main.py` - FastAPI app entry point: lifespan context manager, app.state wiring, health endpoint, SSE router include
- `backend/tests/test_main.py` - 3 integration tests covering health endpoint, lifespan startup, and SSE route registration

## Decisions Made

- Followed all locked decisions from CONTEXT.md (D-04, D-05, D-06, D-07) exactly as specified
- Stream router wired via `app.include_router(stream_router)` at module level (not inside lifespan); SSE handler reads `price_cache` from `request.app.state.price_cache`. Original lifespan-include approach was changed by CR-01 fix applied post-execution.
- Used `app.state.price_cache` and `app.state.market_source` per D-07 (no module-level globals)
- Health endpoint defined inline in `main.py` per D-05 (3 lines, not worth a separate router file)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SSE route test to avoid infinite stream hang**
- **Found during:** Task 2 (GREEN) — `test_sse_route_registered` with `stream=True` keyword failed (not a valid TestClient.get() argument), then without the keyword the test hung indefinitely because SSE is an infinite streaming response
- **Issue:** TestClient reads the entire response body before returning; an SSE endpoint with an infinite generator loop hangs synchronously. Plan spec said "call client.get('/api/stream/prices', stream=True)" but `stream=True` is not a valid kwarg for TestClient.get()
- **Fix:** Changed test to inspect `app.routes` list directly for the path `/api/stream/prices` rather than making an HTTP call. This correctly verifies route registration without triggering the infinite stream
- **Files modified:** `backend/tests/test_main.py`
- **Commit:** `9bb337c`

## Issues Encountered

None beyond the auto-fixed test hang described above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `backend/app/main.py` is ready for Phase 2 route handlers to be mounted via `app.include_router()` at module level
- `app.state.price_cache` is accessible in Phase 2 route handlers via `request.app.state.price_cache`
- `DbDep` from `db.py` is ready for Phase 2 route handlers to use via `Depends(get_db)`
- No blockers

## Threat Surface Scan

No new security-relevant surface beyond what was planned:
- GET /api/health: returns static JSON only; no input processing; no server internals exposed (T-02-01 accepted)
- app.state: internal to Python process; not accessible to end users (T-02-02 accepted)
- Lifespan startup failure: init_db() is idempotent (tested); market source failure raises exception uvicorn reports (T-02-03 mitigated)
- SSE router: registered once at module level; route count confirmed stable at 1 across TestClient lifespans (T-02-04 mitigated; CR-01 fixed post-execution)

## Self-Check: PASSED

- `backend/app/main.py`: FOUND
- `backend/tests/test_main.py`: FOUND
- Commit `c3d790b`: FOUND (test - RED phase)
- Commit `9bb337c`: FOUND (feat - GREEN phase)
- All 82 tests pass (full suite green)
- `grep "from app.db import init_db" backend/app/main.py`: FOUND
- `grep "app.state.price_cache" backend/app/main.py`: FOUND
- `grep "/api/health" backend/app/main.py`: FOUND
- `grep "asynccontextmanager" backend/app/main.py`: FOUND

---
*Phase: 01-database-backend-foundation*
*Completed: 2026-06-08*
