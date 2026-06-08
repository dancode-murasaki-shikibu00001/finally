# Phase 1: Database & Backend Foundation - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire up the FastAPI application entry point, lazily initialize the SQLite database (creating all 6 tables + seed data on first start), and expose a health endpoint. This phase produces a runnable backend that Phase 2 can mount its REST routers onto. The market data subsystem (Phase 0) is already complete and must be wired into the app lifespan here.

</domain>

<decisions>
## Implementation Decisions

### DB Access Library
- **D-01:** Use Python's built-in `sqlite3` module (synchronous). FastAPI dispatches sync functions to a thread pool automatically. No additional dependencies needed; simpler code; appropriate for a single-user app.
- **D-02:** One connection per request — open a connection inside each function, use it, then close it. Avoids threading issues entirely; SQLite is fast enough for this workload.
- **D-03:** Database path via `DB_PATH` environment variable with fallback to `db/finally.db` relative to the project root. Makes path overridable in tests and Docker without code changes.

### App Entry Point Location
- **D-04:** FastAPI app lives in `backend/app/main.py`. Uvicorn runs `app.main:app`. Keeps all application code under `backend/app/`, consistent with the existing `backend/app/market/` structure.
- **D-05:** Health endpoint (`GET /api/health`) is defined inline in `main.py` — not a separate router file. It's 3 lines; a dedicated file would be over-engineering for Phase 1.

### Startup Wiring
- **D-06:** Single `@asynccontextmanager` lifespan function in `main.py` handles all startup/shutdown: `init_db()` then `await market_source.start(tickers)` on startup; `await market_source.stop()` on shutdown.
- **D-07:** Shared objects (`PriceCache`, `MarketDataSource`) are stored on `app.state` during lifespan (e.g., `app.state.price_cache`, `app.state.market_source`). Routers in future phases access them via `Request.app.state` or a FastAPI `Depends`. No module-level globals.
- **D-08:** Database module is a single file: `backend/app/db.py`. Contains `init_db()`, `get_db_path()`, and the full schema SQL as a string constant. Phase 2+ adds query functions to the same file.

### Claude's Discretion
- Internal variable naming, docstring style, and logging verbosity follow the existing patterns in `backend/app/market/`.
- Whether `init_db()` is called explicitly in lifespan or discovered via a startup guard — Claude decides the most readable pattern.
- SQL schema formatting (one-statement-per-table vs. combined CREATE TABLE block) — Claude's call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Design
- `planning/PLAN.md` — Full project specification: single-container architecture, DB schema definitions, API endpoints, environment variables, seed data
- `planning/MARKET_DATA_SUMMARY.md` — Phase 0 summary: what was built, module map, public API, usage patterns for downstream code

### Existing Backend Code
- `backend/app/market/__init__.py` — Market data public API: `PriceCache`, `create_market_data_source`, `stream_router`
- `backend/app/market/stream.py` — SSE router factory pattern (model for how Phase 1 wires the stream router into the app)
- `backend/CLAUDE.md` — Backend developer guide: project setup, market data usage, test commands

### Configuration
- `backend/pyproject.toml` — Existing dependencies (`fastapi`, `uvicorn`, `numpy`, `massive`, `rich`); `sqlite3` is stdlib so no new dep needed

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_market_data_source(cache)` — factory in `backend/app/market/factory.py`; returns the correct data source based on `MASSIVE_API_KEY` env var. Phase 1 calls this during lifespan startup.
- `stream_router` — module-level `APIRouter` exported from `backend/app/market/__init__.py`; included once at app level with `app.include_router(stream_router)` in `main.py`. The SSE handler reads `price_cache` from `request.app.state.price_cache` at request time.
- `PriceCache` — from `backend/app/market/cache.py`; instantiated once during lifespan and stored on `app.state.price_cache`.

### Established Patterns
- **`app.state` pattern for shared objects in route handlers** — `stream_router`'s SSE handler reads `price_cache` from `request.app.state.price_cache`. Phase 2+ routers should follow this pattern for accessing `PriceCache`, `MarketDataSource`, or any lifespan-initialized object.
- **Module `__init__.py` as public API** — `backend/app/market/__init__.py` exposes only the public surface. `backend/app/db.py` should be the same: clean function exports, no internal details in `__init__.py`.

### Integration Points
- `backend/app/main.py` — the single integration point. Imports `create_market_data_source`, `stream_router`, `PriceCache`, and `init_db`. `app.include_router(stream_router)` at module level; lifespan handles `init_db()`, `PriceCache`, and `app.state` assignment.
- `backend/app/market/seed_prices.py` — contains `DEFAULT_TICKERS` list (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX); the watchlist seed and the market data `start(tickers)` call should both use this list as the source of truth.

</code_context>

<specifics>
## Specific Ideas

- The lifespan should call `init_db()` before starting the market data source, so DB is ready before any requests arrive.
- `GET /api/health` returns `{"status": "ok"}` with HTTP 200 — exact response shape from PLAN.md §8.
- The DB path default is `db/finally.db` — relative to the project root (one level above `backend/`). In Docker the project root is `/app`, so the DB lands at `/app/db/finally.db` on the volume mount.
- Seed data for `watchlist` table must match `seed_prices.py`'s ticker list exactly so the market simulator and the DB are in sync from the start.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-database-backend-foundation*
*Context gathered: 2026-06-08*
