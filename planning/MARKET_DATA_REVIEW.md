# Market Data Backend — Code Review

**Reviewer**: Claude Code (Sonnet 4.6)  
**Date**: 2026-06-06  
**Scope**: `backend/market/` module and `backend/tests/` suite  
**Reference docs**: `MARKET_DATA_DESIGN.md`, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md`

---

## 1. Test Results

### Correct invocation (with dev extras)

```
uv run --with "pytest,pytest-asyncio" pytest tests/ -v
23 passed in 3.89s
```

**All 23 tests pass.** Breakdown:

| File | Tests | Result |
|------|-------|--------|
| `test_cache.py` | 6 | ✅ All pass |
| `test_massive_client.py` | 7 | ✅ All pass |
| `test_simulator.py` | 10 | ✅ All pass |

### Failure mode without dev extras

Running `uv run pytest tests/` (without `--extra dev`) produces **5 failures** — every async simulator test. Root cause: `pytest-asyncio` is declared in `[project.optional-dependencies] dev` in `pyproject.toml` and is present in `uv.lock`, but is not installed unless the dev extras are explicitly requested. The failures are not code bugs; they are an environment setup issue.

**Action required**: Document or script the correct test invocation. A `Makefile` target (`make test`) or a note in `README.md` pointing developers to `uv sync --extra dev && uv run pytest` would prevent this from confusing future contributors.

---

## 2. File-by-File Review

### `backend/market/base.py` — ✅ Correct

`PriceQuote` dataclass and `MarketDataProvider` ABC match the design specification exactly. All 6 abstract methods are present with correct signatures. No issues.

### `backend/market/cache.py` — ✅ Correct

Thread-safe wrapper around a `dict[str, PriceQuote]` using `threading.Lock`. The implementation:
- Returns a shallow copy in `get_all()` — correct; callers cannot corrupt internal state
- Has `remove()` and `tickers()` methods matching the design
- The lock is fine-grained (held only for the duration of the dict operation), consistent with the design intent of keeping SSE reads fast

No issues.

### `backend/market/simulator.py` — ✅ Correct, with minor observation

The GBM implementation is mathematically correct:

```python
z = cfg.rho * z_market + math.sqrt(1 - cfg.rho ** 2) * z_idio
new_price = self.price * math.exp(
    (cfg.mu - 0.5 * cfg.sigma ** 2) * DT + cfg.sigma * math.sqrt(DT) * z
)
```

This correctly decomposes Z into a shared market factor and idiosyncratic noise, and applies the Itô-corrected GBM formula. The price floor (`max(new_price, 0.01)`) correctly prevents zero/negative prices.

**Observation — `asyncio.Lock` dropped from `start()`**: `MARKET_SIMULATOR.md` shows `start()` acquiring `self._lock = asyncio.Lock()`, but the final implementation omits it. This is the correct decision: FastAPI route handlers and the simulate loop both run on the single asyncio event loop thread (cooperative scheduling), so there is no concurrent access to `_states`. The lock added noise without providing safety.

**Observation — `remove_ticker` clears the cache**: `MARKET_SIMULATOR.md` says "Leave the cache entry", but the implementation calls `self._cache.remove(ticker)`. The implementation is correct and aligns with `MARKET_DATA_DESIGN.md` (the authoritative spec). The removed ticker disappears from the SSE stream on the next push, which is the right UX.

**Observation — `tick()` return type**: `MARKET_SIMULATOR.md` shows `tick()` returning `self.price`; the implementation returns `None`. The return value is unused in `_simulate_loop`, so there is no functional difference. The implementation's `-> None` is cleaner.

### `backend/market/massive_client.py` — ✅ Correct with two minor issues

**Issue 1 — Inline `import time` is redundant (low severity)**

`massive_client.py:147`:
```python
import time as _time; _time.sleep(wait)
```

`time` is already imported at the top of the file (`import time`). This should be `time.sleep(wait)`. The inline import works correctly — Python's module cache means `import time` is instantaneous — but it's a code smell suggesting the line was written in isolation.

**Issue 2 — `return {}` after exhausting 429 retries is silently swallowed (low severity)**

The comment on the final `return {}` reads "unreachable but satisfies type checker", but it *is* reachable: if all 3 retry attempts receive a 429 response, all 3 iterations `continue` and the loop falls through to `return {}`. An empty dict causes `_fetch_chunk` to return `[]`, `_fetch_snapshots` returns `[]`, `_poll_once` gets no quotes, and the cache goes stale without any log entry. Compare this with a network timeout, which propagates as an exception and triggers `logger.exception("Massive poll failed...")` in `_poll_once`.

For a demo project this is acceptable (last cached prices are kept), but the comment is misleading and the asymmetric logging is worth noting.

**Issue 3 — `or` operator treats `0.0` change_pct as falsy (negligible for demo)**

```python
change_pct = (
    session.get("change_percent")
    or (
        (price - prev_close) / prev_close * 100
        if prev_close
        else 0.0
    )
)
```

When `session.change_percent` is exactly `0.0` (no daily change), the `or` branch computes the value from price and prev_close, which is also 0.0. The numeric result is the same. However, semantically this is incorrect: a field value of `0.0` should not be treated as "absent". A correct check is `if session.get("change_percent") is not None`. For a trading terminal demo this has no visible effect.

**Positive notes on `massive_client.py`**:
- The upfront `_poll_once()` call in `start()` correctly populates the cache before the first SSE push
- The `asyncio.to_thread` wrapper for the synchronous HTTP call is the correct pattern — the event loop is never blocked during network I/O
- The chunking logic for >250 tickers is correct (though irrelevant for the default 10-ticker watchlist)
- Exponential backoff on 429 (`2**attempt` seconds) runs in the worker thread, not the event loop thread — correct

### `backend/market/factory.py` — ✅ Correct

The factory correctly reads `MASSIVE_API_KEY` and `MASSIVE_POLL_INTERVAL` from the environment, defaulting to `MarketSimulator`. The `init_provider` / `get_provider` singleton pattern is clean and will integrate naturally with FastAPI's lifespan.

### `backend/market/__init__.py` — ✅ Correct

Public API matches the design spec. All downstream code should import only from here.

---

## 3. Test Suite Quality

### Coverage analysis

| Behaviour | Tested |
|-----------|--------|
| Seed prices correct | ✅ `test_seed_price_is_initial_price` |
| GBM price bounded after 10k ticks | ✅ `test_gbm_price_bounded_after_many_ticks` |
| Price floor prevents zero | ✅ `test_price_floor_prevents_zero` |
| Unknown ticker → default seed | ✅ `test_unknown_ticker_uses_default_seed` |
| `add_ticker` updates cache immediately | ✅ `test_add_ticker_appears_in_cache_immediately` |
| `add_ticker` on existing ticker is no-op | ✅ `test_add_existing_ticker_is_noop` |
| `remove_ticker` clears cache | ✅ `test_remove_ticker_disappears_from_cache` |
| Prices change after ticks | ✅ `test_prices_change_after_two_ticks` |
| Deterministic with same seed | ✅ `test_deterministic_with_same_seed` |
| `get_all_prices` returns all started tickers | ✅ `test_all_prices_returns_all_started_tickers` |
| API response parsing (full fields) | ✅ `test_parse_snapshot_response` |
| Fallback to session.close when no last_trade | ✅ `test_missing_last_trade_falls_back_to_session_close` |
| Computed change_pct when field absent | ✅ `test_change_pct_computed_when_missing` |
| Poll error does not crash | ✅ `test_http_error_does_not_crash_poll` |
| 429 retry with backoff | ✅ `test_rate_limit_retry` |
| `add_ticker` included in next poll | ✅ `test_add_ticker_included_in_next_poll` |
| `remove_ticker` excluded from polling | ✅ `test_remove_ticker_excluded_from_polling` |
| Cache thread safety | ✅ `test_thread_safety` |
| Cache copy isolation | ✅ `test_get_all_returns_copy` |

### Gaps

The following scenarios are not tested:

| Gap | Risk |
|-----|------|
| `factory.create_market_provider()` with env var set | Low — trivial logic |
| `factory.get_provider()` raises before `init_provider()` called | Low |
| `MassiveClient` chunking when >250 tickers | Low — 10 tickers in practice |
| Concurrently calling `add_ticker` while `_simulate_loop` is ticking | Low — asyncio cooperative scheduling makes this safe by design |
| `_get_with_retry` exhausts all 3 retries on 429 (hits `return {}`) | Medium — the silent path; tests mock a 429 followed by success but not 3 consecutive 429s |

None of these gaps represent a risk for the course project. For a production system, the 429-exhaustion path would warrant a test and an explicit log.

---

## 4. Spec Conformance

### Conforming to design

| Requirement | Status |
|-------------|--------|
| Both providers implement `MarketDataProvider` ABC | ✅ |
| `PriceQuote` fields match contract | ✅ |
| Simulator uses GBM with correlated market factor | ✅ |
| Simulator price floor at `0.01` | ✅ |
| Simulator deterministic with `seed` | ✅ |
| `add_ticker` on simulator → cache populated immediately | ✅ |
| `add_ticker` on Massive → added to next poll cycle | ✅ |
| Massive upfront poll in `start()` | ✅ (design improvement implemented) |
| 429 rate limit backoff | ✅ |
| Poll error keeps last cached prices | ✅ |
| `MASSIVE_POLL_INTERVAL` env var support | ✅ |
| `init_provider` / `get_provider` singleton | ✅ |
| Public exports via `__init__.py` | ✅ |

### Out of scope for this PR (checklist items not yet implemented)

Per `MARKET_DATA_DESIGN.md §11`, the following remain to be built:
- `backend/main.py` — FastAPI lifespan wiring
- `backend/routes/stream.py` — SSE endpoint
- `backend/routes/watchlist.py` — watchlist CRUD calling provider
- `backend/routes/portfolio.py` — trade fill price via provider

These are expected gaps — the market data module is correctly isolated and ready to be integrated.

---

## 5. Issues Summary

| # | Severity | File | Description |
|---|----------|------|-------------|
| 1 | Medium | `pyproject.toml` / dev workflow | `pytest-asyncio` only installed with `--extra dev`; bare `uv run pytest` silently fails 5 tests. Needs documentation or a script. |
| 2 | Low | `massive_client.py:147` | Redundant inline `import time as _time` — `time` is already imported at the module level. Use `time.sleep(wait)`. |
| 3 | Low | `massive_client.py:143` | Comment "unreachable" is wrong — `return {}` is reachable when all 3 retry attempts return 429. The silent behavior (no log, stale cache) is acceptable but should be documented. |
| 4 | Negligible | `massive_client.py:112` | `or` operator treats `0.0` change_pct as falsy; numerically harmless for this application. |

---

## 6. Verdict

**The implementation is correct and complete for its stated scope.** All 23 tests pass. The code faithfully implements the design in `MARKET_DATA_DESIGN.md`, makes sensible improvements where the design left room (upfront poll in `start()`, `MASSIVE_POLL_INTERVAL` env var), and correctly resolves the two spec conflicts between `MARKET_SIMULATOR.md` and `MARKET_DATA_DESIGN.md` in favour of the authoritative document.

The module is ready for integration. The one action item before merging is to document or automate the dev dependency installation so the test suite runs correctly without manual intervention (Issue #1). The two remaining code issues (#2 and #3) are low-priority cleanup items.
