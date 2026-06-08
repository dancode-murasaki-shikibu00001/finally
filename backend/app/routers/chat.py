"""Chat REST endpoint: LLM assistant with auto-execution of trades and watchlist changes."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import DEFAULT_USER_ID, DbDep
from app.llm import LLMResponse, call_llm
from app.routers.portfolio import TradeError, execute_trade_logic
from app.routers.watchlist import add_ticker_logic, remove_ticker_logic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

HISTORY_LIMIT = 20  # number of recent messages to include in context

SYSTEM_PROMPT_TEMPLATE = """\
You are FinAlly, an AI trading assistant for a simulated portfolio workstation.

CURRENT PORTFOLIO STATE:
{portfolio_context}

INSTRUCTIONS:
- Analyze portfolio composition, risk concentration, and P&L when relevant
- Suggest trades with clear reasoning based on the portfolio data
- Execute trades when the user explicitly asks or clearly agrees to a suggestion
- Manage the watchlist proactively — add tickers the user asks about
- Be concise and data-driven; reference specific numbers from the portfolio
- Respond ONLY with valid JSON matching the schema below

RESPONSE SCHEMA:
{{
  "message": "Your conversational response (required)",
  "trades": [{{"ticker": "AAPL", "side": "buy", "quantity": 10}}],
  "watchlist_changes": [{{"ticker": "PYPL", "action": "add"}}]
}}

The "trades" and "watchlist_changes" arrays must be present (empty if no actions needed).
For trades: side must be "buy" or "sell", quantity must be a positive number.
For watchlist_changes: action must be "add" or "remove".
"""


class ChatRequest(BaseModel):
    message: str


@router.post("")
async def chat(body: ChatRequest, request: Request, db: DbDep) -> dict:
    cache = request.app.state.price_cache
    market_source = request.app.state.market_source
    user_id = DEFAULT_USER_ID
    now = datetime.now(timezone.utc).isoformat()

    # 1. Build portfolio context string
    portfolio_context = _build_portfolio_context(db, cache, user_id)

    # 2. Load recent conversation history
    history = _load_history(db, user_id)

    # 3. Persist user message
    user_msg_id = str(uuid.uuid4())
    with db:
        db.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_msg_id, user_id, "user", body.message, None, now),
        )

    # 4. Call LLM
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(portfolio_context=portfolio_context)
    llm_response: LLMResponse = call_llm(system_prompt, history, body.message)

    # 5. Auto-execute trades
    trade_results = []
    for trade_action in llm_response.trades:
        try:
            result = execute_trade_logic(
                conn=db,
                cache=cache,
                ticker=trade_action.ticker,
                side=trade_action.side,
                quantity=trade_action.quantity,
                user_id=user_id,
            )
            trade_results.append(
                {
                    "ticker": result.ticker,
                    "side": result.side,
                    "quantity": result.quantity,
                    "price": result.price,
                    "status": "ok",
                }
            )
            logger.info(
                "LLM trade executed: %s %s x%s @ %.2f",
                result.side,
                result.ticker,
                result.quantity,
                result.price,
            )
        except TradeError as exc:
            trade_results.append(
                {
                    "ticker": trade_action.ticker.upper(),
                    "side": trade_action.side,
                    "quantity": trade_action.quantity,
                    "status": "error",
                    "error": str(exc),
                }
            )
            logger.warning("LLM trade failed: %s", exc)

    # 6. Auto-execute watchlist changes
    watchlist_results = []
    for change in llm_response.watchlist_changes:
        ticker = change.ticker.upper()
        action = change.action.lower()
        try:
            if action == "add":
                wl_result = await add_ticker_logic(db, market_source, ticker, user_id)
                watchlist_results.append({"ticker": ticker, "action": "add", "status": "ok"})
                logger.info("LLM watchlist add: %s (created=%s)", ticker, wl_result["created"])
            elif action == "remove":
                removed = await remove_ticker_logic(db, market_source, ticker, user_id)
                watchlist_results.append(
                    {
                        "ticker": ticker,
                        "action": "remove",
                        "status": "ok" if removed else "not_found",
                    }
                )
            else:
                watchlist_results.append(
                    {"ticker": ticker, "action": action, "status": "error", "error": "unknown action"}
                )
        except Exception as exc:
            watchlist_results.append(
                {"ticker": ticker, "action": action, "status": "error", "error": str(exc)}
            )
            logger.warning("LLM watchlist change failed: %s", exc)

    # 7. Persist assistant message with executed actions
    actions_json = json.dumps({"trades": trade_results, "watchlist_changes": watchlist_results})
    assistant_msg_id = str(uuid.uuid4())
    assistant_now = datetime.now(timezone.utc).isoformat()
    with db:
        db.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (assistant_msg_id, user_id, "assistant", llm_response.message, actions_json, assistant_now),
        )

    return {
        "id": assistant_msg_id,
        "message": llm_response.message,
        "trades": trade_results,
        "watchlist_changes": watchlist_results,
        "created_at": assistant_now,
    }


def _build_portfolio_context(db, cache, user_id: str) -> str:
    row = db.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    cash_balance = row["cash_balance"] if row else 10000.0

    pos_rows = db.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND quantity > 0",
        (user_id,),
    ).fetchall()

    positions_value = 0.0
    pos_lines = []
    for r in pos_rows:
        ticker = r["ticker"]
        quantity = r["quantity"]
        avg_cost = r["avg_cost"]
        current_price = cache.get_price(ticker)
        if current_price is not None:
            pnl = (current_price - avg_cost) * quantity
            pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0
            positions_value += current_price * quantity
            sign = "+" if pnl >= 0 else ""
            pos_lines.append(
                f"  {ticker}: {quantity} shares @ ${avg_cost:.2f} avg, "
                f"current ${current_price:.2f}, P&L: {sign}${pnl:.2f} ({sign}{pnl_pct:.1f}%)"
            )
        else:
            pos_lines.append(f"  {ticker}: {quantity} shares @ ${avg_cost:.2f} avg (price unavailable)")

    wl_rows = db.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC", (user_id,)
    ).fetchall()
    wl_items = []
    for r in wl_rows:
        price = cache.get_price(r["ticker"])
        wl_items.append(f"{r['ticker']} (${price:.2f})" if price else r["ticker"])

    total_value = cash_balance + positions_value
    lines = [
        f"Cash: ${cash_balance:,.2f}",
        f"Positions Value: ${positions_value:,.2f}",
        f"Total Value: ${total_value:,.2f}",
        "Positions:" if pos_lines else "Positions: none",
    ]
    lines.extend(pos_lines)
    lines.append(f"Watchlist: {', '.join(wl_items) if wl_items else 'empty'}")
    return "\n".join(lines)


def _load_history(db, user_id: str) -> list[dict]:
    rows = db.execute(
        "SELECT role, content FROM chat_messages WHERE user_id = ?"
        " ORDER BY created_at DESC LIMIT ?",
        (user_id, HISTORY_LIMIT),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
