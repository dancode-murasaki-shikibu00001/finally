---
phase: 1
slug: database-backend-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.24+ |
| **Config file** | `backend/pyproject.toml` — `[tool.pytest.ini_options]` section |
| **Quick run command** | `uv run --extra dev pytest tests/test_db.py tests/test_main.py -v` |
| **Full suite command** | `uv run --extra dev pytest -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --extra dev pytest tests/test_db.py tests/test_main.py -v`
- **After every plan wave:** Run `uv run --extra dev pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green (73 existing + new phase tests)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-db-01 | db | 1 | DB-01 | — | CREATE TABLE IF NOT EXISTS prevents crash on restart | unit | `pytest tests/test_db.py::TestInitDb::test_creates_all_six_tables -x` | ❌ W0 | ⬜ pending |
| 1-db-02 | db | 1 | DB-01 | — | init_db idempotent on second call | unit | `pytest tests/test_db.py::TestInitDb::test_idempotent_on_second_call -x` | ❌ W0 | ⬜ pending |
| 1-db-03 | db | 1 | DB-02 | — | users_profile seeded with $10k cash | unit | `pytest tests/test_db.py::TestInitDb::test_seeds_default_user_with_10k -x` | ❌ W0 | ⬜ pending |
| 1-db-04 | db | 1 | DB-03 | — | watchlist seeded with 10 tickers; UNIQUE constraint | unit | `pytest tests/test_db.py::TestInitDb::test_seeds_watchlist_tickers -x` | ❌ W0 | ⬜ pending |
| 1-db-05 | db | 1 | DB-04..DB-07 | — | all 6 tables exist with correct schema | unit | `pytest tests/test_db.py::TestInitDb::test_creates_all_six_tables -x` | ❌ W0 | ⬜ pending |
| 1-main-01 | main | 1 | SYS-01 | — | GET /api/health returns {"status": "ok"} HTTP 200 | integration | `pytest tests/test_main.py::test_health_endpoint -x` | ❌ W0 | ⬜ pending |
| 1-main-02 | main | 1 | SYS-01 | — | lifespan wires market data source without crash | integration | `pytest tests/test_main.py::test_lifespan_startup -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_db.py` — stubs/tests for DB-01 through DB-07
- [ ] `backend/tests/test_main.py` — stubs/tests for SYS-01 health endpoint and lifespan wiring

*Existing `tests/market/` infrastructure requires no changes.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| db/ directory created at correct path relative to project root | DB-01 | Path is CWD-dependent; Docker vs local differs | Run `uvicorn app.main:app` from project root; verify `db/finally.db` exists at top-level `db/` not inside `backend/db/` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
