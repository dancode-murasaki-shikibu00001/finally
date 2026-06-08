# Roadmap: FinAlly — AI Trading Workstation

## Overview

All six phases are complete. The application is fully implemented: market data streaming, database layer, REST APIs, LLM chat integration, Next.js frontend, Docker packaging, and automated testing.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Database & Backend Foundation** - SQLite schema, lazy init, seed data, and health endpoint ✓ 2026-06-08
- [x] **Phase 2: Portfolio, Watchlist & Static Serving** - REST APIs for portfolio and watchlist, snapshot background task, static file serving ✓ 2026-06-08
- [x] **Phase 3: LLM Chat Integration** - Chat endpoint, LiteLLM/OpenRouter structured output, auto-execution, mock mode ✓ 2026-06-08
- [x] **Phase 4: Frontend** - Full Next.js TypeScript UI — watchlist, charts, heatmap, trade bar, AI chat panel ✓ 2026-06-08
- [x] **Phase 5: Docker & Deployment** - Multi-stage Dockerfile, start/stop scripts, docker-compose, .env.example ✓ 2026-06-08
- [x] **Phase 6: Testing** - Backend unit tests and E2E Playwright tests ✓ 2026-06-08

## Phase Details

### Phase 1: Database & Backend Foundation
**Goal**: The backend initializes a clean, seeded SQLite database on first start and responds to health checks
**Depends on**: Nothing (Phase 0 — market data — already complete)
**Requirements**: DB-01, DB-02, DB-03, DB-04, DB-05, DB-06, DB-07, SYS-01
**Status**: ✅ Complete — implementation complete, CR-01 fix applied in 2e212fa

**Wave 1** *(no dependencies)*
- [x] 01-01-PLAN.md — SQLite db.py module: SCHEMA_SQL, init_db(), get_db_path(), get_db(), DbDep ✓ 2026-06-08

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-02-PLAN.md — FastAPI main.py: lifespan wiring, health endpoint, router registration ✓ 2026-06-08

### Phase 2: Portfolio, Watchlist & Static Serving
**Goal**: Users can query and manage their portfolio and watchlist through REST endpoints, and the backend serves the frontend static files
**Depends on**: Phase 1
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, WTCH-01, WTCH-02, WTCH-03, SYS-02
**Status**: ✅ Complete — commit d75dd91

**Delivered:**
- `GET /api/portfolio` — positions with live P&L, cash balance, total value
- `POST /api/portfolio/trade` — atomic buy/sell with validation (insufficient cash, oversell)
- `GET /api/portfolio/history` — time-ordered portfolio value snapshots
- `GET/POST/DELETE /api/watchlist` — retrieve, add, remove tickers; duplicate add is idempotent
- Static file serving mounted at `/` (Next.js export)
- Background snapshot task (every 30s + immediately after each trade)

### Phase 3: LLM Chat Integration
**Goal**: Users can send natural language messages to the AI assistant, which reads their live portfolio and autonomously executes trades and watchlist changes
**Depends on**: Phase 2
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07, CHAT-08
**Status**: ✅ Complete — commit 88784e1

**Delivered:**
- `POST /api/chat` — complete JSON response (message + executed trades + watchlist changes)
- Portfolio context injected into every system prompt
- LiteLLM → OpenRouter → `openrouter/openai/gpt-oss-120b` (Cerebras inference)
- Structured output parsing via Pydantic `LLMResponse` model
- Auto-execution of trades and watchlist changes through same validation as manual trades
- Failed trades surface error in chat response without blocking other actions
- Chat history persisted in `chat_messages` table; included in subsequent prompts
- `LLM_MOCK=true` returns deterministic mock response without calling OpenRouter

### Phase 4: Frontend
**Goal**: Users experience a dark, data-dense trading terminal in the browser — live prices, charts, portfolio visualization, manual trading, and AI chat — all connected to the backend
**Depends on**: Phase 3
**Requirements**: FRONT-01 through FRONT-14
**Status**: ✅ Complete — commit 6f6a3f5

**Delivered:**
- Watchlist panel: price flash (green/red ~500ms CSS fade), sparkline mini-charts from SSE history
- Main chart area: lightweight-charts price-over-time for selected ticker
- Portfolio heatmap: recharts treemap sized by weight, colored by P&L
- P&L chart: line chart from `/api/portfolio/history` snapshots
- Positions table: quantity, avg cost, current price, unrealized P&L, % change
- Trade bar: ticker + qty inputs, BUY/SELL buttons, success/error flash messages
- AI chat sidebar: collapsible, message input, loading indicator, inline trade/watchlist confirmation cards
- Header: live total portfolio value, cash balance, SSE connection status dot (green/yellow/red)
- `usePriceStream` hook: EventSource SSE connection with auto-reconnect and sparkline accumulation

### Phase 5: Docker & Deployment
**Goal**: Anyone can launch the entire application with a single command on macOS, Linux, or Windows
**Depends on**: Phase 4
**Requirements**: DOCK-01 through DOCK-06
**Status**: ✅ Complete — commit fef5efa

**Delivered:**
- Multi-stage Dockerfile: Stage 1 (Node 20, Next.js static export) → Stage 2 (Python 3.12, uv, FastAPI)
- `docker-compose.yml` — single `docker compose up` starts app with volume + port + env-file
- `scripts/start_mac.sh` / `scripts/stop_mac.sh` — idempotent build+run / stop scripts for macOS/Linux
- `scripts/start_windows.ps1` / `scripts/stop_windows.ps1` — PowerShell equivalents for Windows
- `.env.example` — documents OPENROUTER_API_KEY, MASSIVE_API_KEY, LLM_MOCK with descriptions

### Phase 6: Testing
**Goal**: The application's critical logic is covered by automated tests and a full E2E suite validates the user experience in a containerized environment
**Depends on**: Phase 5
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Status**: ✅ Complete — commit e1fd09a

**Delivered:**
- **Backend (pytest)**: 133 tests — market data (cache, simulator, Massive API, factory, models), portfolio trade logic, watchlist CRUD, LLM structured output parsing, chat auto-execution, DB init, health/lifespan
- **Frontend (Jest + RTL)**: 52 tests across 5 suites — Header, PositionsTable, ChatPanel, TradeBar, WatchlistPanel; jsdom polyfills for EventSource/canvas; stubs for lightweight-charts and recharts
- **E2E (Playwright)**: 18 tests — fresh start, watchlist CRUD, buy/sell/error trades, portfolio heatmap, P&L chart, AI chat (mock), API smoke tests, health endpoint
- `test/docker-compose.test.yml` — CI infrastructure: app container + Playwright container, health-checked startup
- `test/playwright.config.ts` — configurable BASE_URL, chromium, retries on CI
- `/api/debug/reset` endpoint (LLM_MOCK=true only) — drops/re-seeds DB and re-adds market source tickers; enables hermetic `beforeEach` isolation
- Confirmed 18/18 pass on two consecutive runs against a live server

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Market Data (DONE) | - | Complete | 2026-06-08 |
| 1. Database & Backend Foundation | 2/2 | Complete | 2026-06-08 |
| 2. Portfolio, Watchlist & Static Serving | complete | Complete | 2026-06-08 |
| 3. LLM Chat Integration | complete | Complete | 2026-06-08 |
| 4. Frontend | complete | Complete | 2026-06-08 |
| 5. Docker & Deployment | complete | Complete | 2026-06-08 |
| 6. Testing | complete | Complete | 2026-06-08 |

**Overall: 100% — all phases implemented and verified**
