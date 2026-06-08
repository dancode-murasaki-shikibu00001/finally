# FinAlly — AI Trading Workstation

## What This Is

FinAlly (Finance Ally) is a visually stunning, AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio with $10,000 in virtual cash, and integrates an LLM chat assistant that can analyze positions and execute trades autonomously on the user's behalf. It targets developers and students as a capstone demonstration of orchestrated agentic AI building a production-quality full-stack application — a Bloomberg-terminal aesthetic with an AI copilot.

## Core Value

An AI chat assistant that can read the user's live portfolio and autonomously execute trades and watchlist changes through natural language — demonstrating agentic AI in a real, impressive, working product.

## Requirements

### Validated

- ✓ Market data simulator (GBM-based, correlated moves, configurable seed prices) — Phase 0
- ✓ Massive API client (REST polling, same interface as simulator) — Phase 0
- ✓ Shared in-memory price cache (latest price, previous price, timestamp per ticker) — Phase 0
- ✓ SSE streaming endpoint (`GET /api/stream/prices`) — Phase 0
- ✓ Background price update task (500ms cadence) — Phase 0
- ✓ Market data abstraction (both implementations behind same interface) — Phase 0

### Active

- ✓ SQLite database with lazy initialization (schema creation + seeding on first start) — Phase 1
- [ ] Portfolio REST API (positions, cash, P&L, trade execution, history snapshots)
- [ ] Watchlist REST API (get, add, remove tickers)
- [ ] LLM chat endpoint with structured output (message + trades + watchlist changes)
- [ ] Auto-execution of trades and watchlist changes from LLM responses
- [ ] Portfolio snapshot background task (every 30s + after each trade)
- [ ] Next.js TypeScript frontend (static export, served by FastAPI)
- [ ] Watchlist panel with live price flashing (green/red CSS transitions)
- [ ] Sparkline mini-charts (accumulated from SSE since page load)
- [ ] Main chart area for selected ticker (larger price-over-time chart)
- [ ] Portfolio heatmap / treemap (positions sized by weight, colored by P&L)
- [ ] P&L line chart (total portfolio value over time from snapshots)
- [ ] Positions table (ticker, qty, avg cost, current price, unrealized P&L, % change)
- [ ] Trade bar (ticker, quantity, buy/sell buttons — market orders, instant fill)
- [ ] AI chat panel (docked sidebar, message input, conversation history, loading indicator)
- [ ] Header (live total value, cash balance, SSE connection status dot)
- [ ] Multi-stage Docker build (Node 20 → Python 3.12, single container port 8000)
- [ ] Start/stop scripts (mac/linux .sh, windows .ps1)
- [ ] Backend unit tests (portfolio math, trade validation, LLM output parsing)
- [ ] E2E Playwright tests (docker-compose.test.yml, LLM_MOCK=true)

### Out of Scope

- Real-time WebSockets — SSE is sufficient for one-way server push
- User authentication / multi-user — single user "default", no login
- Limit orders / order book — market orders only, eliminates order book complexity
- Database server (Postgres) — SQLite self-contained, zero config needed
- Cloud deployment Terraform — stretch goal, not in core build
- Fractional share display complexity — fractional shares supported in DB but UI shows simple numbers
- Mobile-first design — desktop-first, functional on tablet

## Context

- **Phase 0 complete**: market data engine (`backend/app/market/`), price cache, and SSE endpoint.
- **Phase 1 complete**: SQLite DB module (`backend/app/db.py`) and FastAPI entry point (`backend/app/main.py`) — 82 backend tests passing, health endpoint live, DB initialized on startup.
- **Backend stack**: FastAPI (Python/uv), existing `pyproject.toml` and `uv.lock`. New code extends this project.
- **Frontend**: Not yet started. Next.js TypeScript, `output: 'export'`, served as static files by FastAPI from `frontend/` build output.
- **Single origin**: Frontend talks to `/api/*` on the same host — no CORS needed.
- **LLM**: LiteLLM → OpenRouter → `openrouter/openai/gpt-oss-120b` (Cerebras inference). `OPENROUTER_API_KEY` is in `.env`.
- **Database**: SQLite at `db/finally.db`, volume-mounted, lazy-initialized on first backend start.
- **Visual design**: Dark theme (`#0d1117` / `#1a1a2e`), accent yellow `#ecad0a`, blue `#209dd7`, purple `#753991`. Bloomberg terminal aesthetic.
- **Capstone course context**: Built entirely by coding agents to demonstrate orchestrated AI. Every design choice is explained in `planning/PLAN.md`.

## Constraints

- **Tech stack**: FastAPI + uv (backend), Next.js TypeScript static export (frontend), SQLite, Docker — no alternatives
- **Single container**: Everything on port 8000, single `docker run` command, no docker-compose for production
- **LLM provider**: OpenRouter via LiteLLM, model `openrouter/openai/gpt-oss-120b`, Cerebras inference
- **No auth**: Hardcoded `user_id = "default"` throughout; schema has column for future multi-user
- **Market data abstraction**: Both simulator and Massive API must implement the same interface; downstream code is agnostic
- **Dependencies**: `OPENROUTER_API_KEY` required for chat; `MASSIVE_API_KEY` optional (simulator used by default)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE over WebSockets | One-way push is all we need; simpler, universal browser support | — Pending |
| Static Next.js export | Single origin, no CORS, one port, one container | — Pending |
| SQLite over Postgres | No auth = no multi-user = no DB server needed | — Pending |
| Single Docker container | Students run one command; no service orchestration | — Pending |
| uv for Python | Fast, modern, reproducible lockfile | — Pending |
| Market orders only | Eliminates order book, partial fills, dramatically simpler portfolio math | — Pending |
| LiteLLM → OpenRouter (Cerebras) | Fast inference, structured outputs, single API key | — Pending |
| Structured LLM output | Enables auto-execution of trades without parsing; reliable JSON schema | — Pending |
| No confirmation dialogs for AI trades | Fake money, zero stakes — creates impressive agentic demo | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-08 after Phase 1 completion*
