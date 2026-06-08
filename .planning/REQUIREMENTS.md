# Requirements: FinAlly — AI Trading Workstation

**Defined:** 2026-06-08
**Core Value:** An AI chat assistant that can read the user's live portfolio and autonomously execute trades and watchlist changes through natural language.

## Already Complete (Phase 0 — Market Data)

The following requirements are already shipped and validated:

- ✓ **MKT-01**: Market data simulator generates prices via GBM with configurable drift/volatility per ticker
- ✓ **MKT-02**: Simulator runs as in-process background task at ~500ms intervals with correlated moves and random events
- ✓ **MKT-03**: Massive API client polls REST endpoint and parses response into shared format
- ✓ **MKT-04**: Both implementations conform to the same abstract interface; selection is env-var driven
- ✓ **MKT-05**: Shared in-memory price cache holds latest price, previous price, and timestamp per ticker
- ✓ **MKT-06**: `GET /api/stream/prices` SSE endpoint pushes all ticker updates to connected clients at ~500ms cadence

## v1 Requirements

### Database (DB)

- [ ] **DB-01**: Backend lazily initializes SQLite at `db/finally.db` on startup — creates schema and seeds data if file is absent or tables are missing
- [ ] **DB-02**: `users_profile` table stores cash balance (default $10,000) with `user_id` column defaulting to `"default"`
- [ ] **DB-03**: `watchlist` table stores watched tickers with unique constraint on `(user_id, ticker)`; seeded with 10 default tickers (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX)
- [ ] **DB-04**: `positions` table stores current holdings (ticker, quantity, avg\_cost) with unique constraint on `(user_id, ticker)`
- [ ] **DB-05**: `trades` table is an append-only log of all executed trades (side, quantity, price, executed\_at)
- [ ] **DB-06**: `portfolio_snapshots` table records total portfolio value over time for the P&L chart
- [ ] **DB-07**: `chat_messages` table stores conversation history with role, content, and JSON actions field

### Portfolio (PORT)

- [ ] **PORT-01**: `GET /api/portfolio` returns current positions with live prices, unrealized P&L per position, cash balance, and total portfolio value
- [ ] **PORT-02**: `POST /api/portfolio/trade` executes a market order (`{ticker, quantity, side}`) — validates sufficient cash for buys and sufficient shares for sells, updates positions and cash atomically
- [ ] **PORT-03**: `GET /api/portfolio/history` returns portfolio value snapshots ordered by time for the P&L chart
- [ ] **PORT-04**: Background task records portfolio snapshots every 30 seconds and immediately after each trade execution

### Watchlist (WTCH)

- [ ] **WTCH-01**: `GET /api/watchlist` returns all watched tickers with their latest prices from the price cache
- [ ] **WTCH-02**: `POST /api/watchlist` adds a ticker `{ticker}` to the watchlist (idempotent — no error if already present)
- [ ] **WTCH-03**: `DELETE /api/watchlist/{ticker}` removes a ticker from the watchlist

### Chat & LLM (CHAT)

- [ ] **CHAT-01**: `POST /api/chat` accepts a user message, returns complete JSON response (no streaming) with message, executed trades, and watchlist changes
- [ ] **CHAT-02**: Backend calls LiteLLM → OpenRouter using model `openrouter/openai/gpt-oss-120b` (Cerebras inference) with the OPENROUTER\_API\_KEY from `.env`
- [ ] **CHAT-03**: LLM response uses structured output schema: `{message: string, trades: [{ticker, side, quantity}], watchlist_changes: [{ticker, action}]}`
- [ ] **CHAT-04**: Trades specified in LLM response are auto-executed through the same portfolio trade logic (with validation); errors are included in chat response
- [ ] **CHAT-05**: Watchlist changes specified in LLM response are auto-executed; errors are included in chat response
- [ ] **CHAT-06**: System prompt includes current portfolio context (cash, positions with P&L, watchlist with live prices, total value) and recent conversation history
- [ ] **CHAT-07**: All chat messages (user and assistant) are stored in `chat_messages` table with role, content, and executed actions JSON
- [ ] **CHAT-08**: When `LLM_MOCK=true` environment variable is set, backend returns deterministic mock responses instead of calling OpenRouter

### System (SYS)

- [ ] **SYS-01**: `GET /api/health` returns `{"status": "ok"}` for Docker health check and deployment readiness
- [ ] **SYS-02**: FastAPI serves the Next.js static export from a `static/` directory, mounting it at `/` with SPA fallback

### Frontend (FRONT)

- [ ] **FRONT-01**: Watchlist panel displays all watched tickers in a grid/table with ticker symbol, current price, daily change %, and sparkline mini-chart
- [ ] **FRONT-02**: Price flash animation: on each price update, the price cell briefly highlights green (uptick) or red (downtick) and fades over ~500ms via CSS transition
- [ ] **FRONT-03**: Sparkline mini-charts per ticker accumulate price history from SSE since page load (fill in progressively as data arrives)
- [ ] **FRONT-04**: Clicking a ticker in the watchlist selects it and displays a larger chart in the main chart area showing price over time
- [ ] **FRONT-05**: Portfolio heatmap (treemap visualization) shows each position as a rectangle sized by portfolio weight and colored green (profit) or red (loss) by P&L
- [ ] **FRONT-06**: P&L line chart shows total portfolio value over time using data from `GET /api/portfolio/history`
- [ ] **FRONT-07**: Positions table shows: ticker, quantity, average cost, current price, unrealized P&L, and % change for all held positions
- [ ] **FRONT-08**: Trade bar allows user to enter ticker and quantity, and click Buy or Sell — market order, instant fill, no confirmation dialog
- [ ] **FRONT-09**: AI chat panel is a docked sidebar with scrolling conversation history, message input, send button, and loading indicator while awaiting LLM response
- [ ] **FRONT-10**: AI chat panel shows trade executions and watchlist changes inline as confirmation cards within the conversation
- [ ] **FRONT-11**: Header shows live total portfolio value (updating from SSE), cash balance, and SSE connection status dot (green=connected, yellow=reconnecting, red=disconnected)
- [ ] **FRONT-12**: Frontend uses `EventSource` to connect to `GET /api/stream/prices` and handles reconnection automatically
- [ ] **FRONT-13**: Frontend is a Next.js TypeScript project with `output: 'export'` — `npm run build` produces a static export in `out/`
- [ ] **FRONT-14**: Dark terminal aesthetic using Tailwind CSS: backgrounds `#0d1117`/`#1a1a2e`, accent yellow `#ecad0a`, blue `#209dd7`, purple `#753991`

### Docker & Deployment (DOCK)

- [ ] **DOCK-01**: Multi-stage Dockerfile: Stage 1 (Node 20) builds Next.js static export; Stage 2 (Python 3.12) installs backend via uv, copies static build, exposes port 8000
- [ ] **DOCK-02**: `scripts/start_mac.sh` builds image if needed and runs container with volume mount (`finally-data:/app/db`), port 8000, and `.env` file; idempotent
- [ ] **DOCK-03**: `scripts/stop_mac.sh` stops and removes the container without deleting the volume; idempotent
- [ ] **DOCK-04**: `scripts/start_windows.ps1` and `scripts/stop_windows.ps1` are PowerShell equivalents of the mac scripts
- [ ] **DOCK-05**: `docker-compose.yml` provides a convenience wrapper with volume, port, and env-file configuration
- [ ] **DOCK-06**: `.env.example` documents all environment variables (`OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`) with descriptions

### Testing (TEST)

- [ ] **TEST-01**: Backend unit tests (pytest) cover portfolio trade logic: P&L calculations, buy with insufficient cash, sell more than owned, position updates
- [ ] **TEST-02**: Backend unit tests cover LLM structured output parsing: valid schema, malformed response handling, trade validation within chat flow
- [ ] **TEST-03**: `test/docker-compose.test.yml` spins up the app container plus Playwright container; tests run with `LLM_MOCK=true`
- [ ] **TEST-04**: E2E Playwright tests cover: fresh start (default watchlist, $10k balance, streaming prices), add/remove ticker, buy/sell shares, portfolio visualization renders, AI chat (mocked) receives response with inline trade confirmation

## v2 Requirements

### Deployment

- **DEPL-01**: Terraform configuration for AWS App Runner deployment in `deploy/` directory
- **DEPL-02**: CI/CD pipeline for automated build and deployment

### Advanced Features

- **ADV-01**: Multi-user support (session tokens, auth middleware, per-user data isolation)
- **ADV-02**: Limit orders with order book simulation
- **ADV-03**: Mobile-optimized responsive layout
- **ADV-04**: Frontend component unit tests (React Testing Library)
- **ADV-05**: SSE reconnection resilience E2E test

## Out of Scope

| Feature | Reason |
|---------|--------|
| WebSockets | SSE is sufficient for one-way server push; no bidirectional complexity needed |
| User authentication / login | Single user "default"; hardcoded in all DB queries |
| Limit orders / order book | Eliminates partial fills and order book complexity; market orders only |
| Postgres / database server | SQLite is self-contained, zero config; no multi-user = no need for DB server |
| Cloud deployment (Terraform) | Stretch goal; not part of the core course build |
| Mobile-first design | Desktop-first; functional on tablet |
| LLM streaming responses | Cerebras inference is fast enough; loading indicator is sufficient |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 through DB-07 | Phase 1 | Pending |
| PORT-01 through PORT-04 | Phase 2 | Pending |
| WTCH-01 through WTCH-03 | Phase 2 | Pending |
| SYS-01 through SYS-02 | Phase 2 | Pending |
| CHAT-01 through CHAT-08 | Phase 3 | Pending |
| FRONT-01 through FRONT-14 | Phase 4 | Pending |
| DOCK-01 through DOCK-06 | Phase 5 | Pending |
| TEST-01 through TEST-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 48 total (plus 6 already complete from Phase 0)
- Mapped to phases: 48
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-08*
*Last updated: 2026-06-08 after initial definition*
