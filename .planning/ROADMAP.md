# Roadmap: FinAlly — AI Trading Workstation

## Overview

Phase 0 (market data) is complete. The remaining 48 requirements span six phases: database and backend foundation, portfolio and watchlist REST APIs, LLM chat integration, the Next.js frontend, Docker packaging, and end-to-end testing. Each phase delivers a coherent, independently verifiable capability that the next phase builds on.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Database & Backend Foundation** - SQLite schema, lazy init, seed data, and health endpoint
- [ ] **Phase 2: Portfolio, Watchlist & Static Serving** - REST APIs for portfolio and watchlist, snapshot background task, static file serving
- [ ] **Phase 3: LLM Chat Integration** - Chat endpoint, LiteLLM/OpenRouter structured output, auto-execution, mock mode
- [ ] **Phase 4: Frontend** - Full Next.js TypeScript UI — watchlist, charts, heatmap, trade bar, AI chat panel
- [ ] **Phase 5: Docker & Deployment** - Multi-stage Dockerfile, start/stop scripts, docker-compose, .env.example
- [ ] **Phase 6: Testing** - Backend unit tests and E2E Playwright tests

## Phase Details

### Phase 1: Database & Backend Foundation
**Goal**: The backend initializes a clean, seeded SQLite database on first start and responds to health checks
**Depends on**: Nothing (Phase 0 — market data — already complete)
**Requirements**: DB-01, DB-02, DB-03, DB-04, DB-05, DB-06, DB-07, SYS-01
**Success Criteria** (what must be TRUE):
  1. Starting the backend against an empty `db/` directory creates `db/finally.db` with all six tables automatically — no manual setup step
  2. The seeded database contains one user profile with $10,000 cash and ten default tickers in the watchlist (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX)
  3. `GET /api/health` returns `{"status": "ok"}` with HTTP 200
  4. Re-starting the backend against an existing database makes no destructive changes — existing data is preserved
**Plans**: 2 plans

**Wave 1** *(no dependencies)*
- [ ] 01-01-PLAN.md — SQLite db.py module: SCHEMA_SQL, init_db(), get_db_path(), get_db(), DbDep (TDD — covers DB-01 through DB-07)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 01-02-PLAN.md — FastAPI main.py: lifespan wiring, health endpoint, router registration (covers SYS-01)

**Cross-cutting constraints:**
- `SEED_PRICES.keys()` from `backend/app/market/seed_prices.py` is canonical ticker list for both DB seed and market source start
- `app.state.price_cache` and `app.state.market_source` — no module-level globals (D-07)

**UI hint**: no

### Phase 2: Portfolio, Watchlist & Static Serving
**Goal**: Users can query and manage their portfolio and watchlist through REST endpoints, and the backend serves the frontend static files
**Depends on**: Phase 1
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, WTCH-01, WTCH-02, WTCH-03, SYS-02
**Success Criteria** (what must be TRUE):
  1. `GET /api/portfolio` returns positions with live P&L, cash balance, and total portfolio value
  2. `POST /api/portfolio/trade` with valid buy/sell data updates cash and positions atomically; invalid trades (insufficient cash, insufficient shares) return a clear error
  3. `GET /api/portfolio/history` returns time-ordered portfolio value snapshots; a new snapshot is recorded within 30 seconds of startup and immediately after each trade
  4. `GET /api/watchlist`, `POST /api/watchlist`, and `DELETE /api/watchlist/{ticker}` correctly retrieve, add, and remove tickers; adding a duplicate ticker does not raise an error
  5. The backend serves an HTML page (or static file index) from `/` — the static-serving mount point is wired and operational
**Plans**: TBD
**UI hint**: no

### Phase 3: LLM Chat Integration
**Goal**: Users can send natural language messages to the AI assistant, which reads their live portfolio and autonomously executes trades and watchlist changes
**Depends on**: Phase 2
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07, CHAT-08
**Success Criteria** (what must be TRUE):
  1. `POST /api/chat` with a user message returns a complete JSON response containing a conversational reply, any executed trades, and any watchlist changes — no streaming, no timeout errors
  2. The LLM response includes the user's current portfolio context (cash, positions with P&L, watchlist with live prices) in every system prompt
  3. Trades specified in the LLM response are automatically executed through the same validation logic as manual trades; failed trades surface their error in the chat response
  4. Watchlist additions and removals specified by the LLM are automatically applied
  5. All user and assistant messages are persisted in `chat_messages` with role, content, and executed actions; conversation history is included in subsequent prompts
  6. With `LLM_MOCK=true`, the endpoint returns a deterministic mock response without calling OpenRouter
**Plans**: TBD
**UI hint**: no

### Phase 4: Frontend
**Goal**: Users experience a dark, data-dense trading terminal in the browser — live prices, charts, portfolio visualization, manual trading, and AI chat — all connected to the backend
**Depends on**: Phase 3
**Requirements**: FRONT-01, FRONT-02, FRONT-03, FRONT-04, FRONT-05, FRONT-06, FRONT-07, FRONT-08, FRONT-09, FRONT-10, FRONT-11, FRONT-12, FRONT-13, FRONT-14
**Success Criteria** (what must be TRUE):
  1. Opening the app shows a watchlist panel where each row flashes green or red on price changes (fade-out over ~500ms) and displays a progressively filling sparkline mini-chart for the session
  2. Clicking a ticker in the watchlist renders a larger price-over-time chart in the main chart area
  3. The portfolio section shows a treemap heatmap (positions sized by weight, green/red by P&L) and a P&L line chart drawn from snapshot history
  4. The positions table lists all held positions with quantity, average cost, current price, unrealized P&L, and % change; the trade bar allows buy and sell market orders that immediately update the UI
  5. The AI chat sidebar accepts a message, shows a loading indicator, and renders the reply with inline trade-execution and watchlist-change confirmation cards
  6. The header shows live total portfolio value (updated from SSE prices), cash balance, and a connection status dot that correctly reflects the SSE connection state
**Plans**: TBD
**UI hint**: yes

### Phase 5: Docker & Deployment
**Goal**: Anyone can launch the entire application with a single command on macOS, Linux, or Windows
**Depends on**: Phase 4
**Requirements**: DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05, DOCK-06
**Success Criteria** (what must be TRUE):
  1. `docker build` on the repository produces a single image that bundles the Next.js static export and the FastAPI backend; `docker run` with port 8000 serves the full working application
  2. Running `scripts/start_mac.sh` builds the image (if absent) and starts the container with the correct volume, port, and env-file; running it a second time is safe and idempotent
  3. Running `scripts/stop_mac.sh` stops and removes the container while leaving the data volume intact
  4. The PowerShell equivalents (`start_windows.ps1`, `stop_windows.ps1`) perform the same operations on Windows
  5. `.env.example` documents all three environment variables with clear descriptions; `docker-compose.yml` starts the application with a single `docker compose up`
**Plans**: TBD
**UI hint**: no

### Phase 6: Testing
**Goal**: The application's critical logic is covered by automated tests and a full E2E suite validates the user experience in a containerized environment
**Depends on**: Phase 5
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Running `pytest` in `backend/` passes all unit tests covering portfolio trade logic (P&L math, insufficient cash, oversell, position updates)
  2. Backend unit tests for LLM output parsing pass — including valid schema, malformed response handling, and trade validation within the chat flow
  3. `docker compose -f test/docker-compose.test.yml up` spins up the app container and Playwright container; all E2E tests run with `LLM_MOCK=true`
  4. E2E tests verify: fresh start shows default watchlist with $10k balance and streaming prices; add/remove ticker works; buy/sell updates cash and positions; portfolio heatmap and P&L chart render; mocked AI chat returns a response with inline trade confirmation
**Plans**: TBD
**UI hint**: no

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Market Data (DONE) | - | Complete | 2026-06-08 |
| 1. Database & Backend Foundation | 0/2 | Not started | - |
| 2. Portfolio, Watchlist & Static Serving | 0/? | Not started | - |
| 3. LLM Chat Integration | 0/? | Not started | - |
| 4. Frontend | 0/? | Not started | - |
| 5. Docker & Deployment | 0/? | Not started | - |
| 6. Testing | 0/? | Not started | - |
