"""
Chat endpoint: POST /api/chat

Sends a user message to the LLM, auto-executes any trades/watchlist changes
in the response, persists the exchange, and returns the full response.
"""

import json

from fastapi import APIRouter, HTTPException

from db.init_db import get_connection
from db import queries as db
from market.factory import get_provider
from models import ChatRequest, ChatResponseModel, ChatTradeResult, WatchlistChange

router = APIRouter()
USER_ID = "default"


def _build_portfolio_context(conn, provider) -> dict:
    """Assemble a portfolio context dict for the LLM system prompt."""
    profile = db.get_user_profile(conn, USER_ID)
    cash_balance = profile["cash_balance"]

    raw_positions = db.get_positions(conn, USER_ID)
    positions = []
    invested_value = 0.0

    for pos in raw_positions:
        ticker = pos["ticker"]
        qty = pos["quantity"]
        avg_cost = pos["avg_cost"]
        quote = provider.get_price(ticker)
        current_price = quote.price if quote else avg_cost
        unrealized_pnl = (current_price - avg_cost) * qty
        pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0
        invested_value += current_price * qty
        positions.append({
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": avg_cost,
            "current_price": current_price,
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    watchlist = db.get_watchlist(conn, USER_ID)
    watchlist_items = []
    for entry in watchlist:
        ticker = entry["ticker"]
        quote = provider.get_price(ticker)
        watchlist_items.append({
            "ticker": ticker,
            "price": quote.price if quote else None,
            "change_pct": quote.change_pct if quote else None,
        })

    total_value = cash_balance + invested_value
    return {
        "cash_balance": round(cash_balance, 2),
        "total_value": round(total_value, 2),
        "positions": positions,
        "watchlist": watchlist_items,
    }


def _execute_trade_internal(conn, provider, ticker: str, side: str, quantity: float):
    """
    Execute a single trade without raising HTTP exceptions.
    Returns a ChatTradeResult.
    """
    ticker = ticker.strip().upper()
    quote = provider.get_price(ticker)
    if quote is None:
        # Add to provider so future references work
        provider.add_ticker(ticker)
        quote = provider.get_price(ticker)

    if quote is None:
        return ChatTradeResult(
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=0.0,
            success=False,
            error=f"No price available for {ticker}",
        )

    current_price = quote.price

    try:
        profile = db.get_user_profile(conn, USER_ID)
        cash_balance = profile["cash_balance"]

        if side == "buy":
            total_cost = quantity * current_price
            if cash_balance < total_cost:
                return ChatTradeResult(
                    ticker=ticker,
                    side=side,
                    quantity=quantity,
                    price=current_price,
                    success=False,
                    error=f"Insufficient cash. Need ${total_cost:.2f}, have ${cash_balance:.2f}.",
                )
            existing = db.get_position(conn, USER_ID, ticker)
            if existing:
                old_qty = existing["quantity"]
                old_avg = existing["avg_cost"]
                new_qty = old_qty + quantity
                new_avg = (old_qty * old_avg + quantity * current_price) / new_qty
            else:
                new_qty = quantity
                new_avg = current_price
            new_cash = cash_balance - total_cost

            with conn:
                db.upsert_position(conn, USER_ID, ticker, new_qty, round(new_avg, 6))
                db.update_cash_balance(conn, USER_ID, round(new_cash, 6))
                db.record_trade(conn, USER_ID, ticker, "buy", quantity, current_price)

        else:  # sell
            existing = db.get_position(conn, USER_ID, ticker)
            owned_qty = existing["quantity"] if existing else 0.0
            if owned_qty < quantity:
                return ChatTradeResult(
                    ticker=ticker,
                    side=side,
                    quantity=quantity,
                    price=current_price,
                    success=False,
                    error=f"Insufficient shares. Have {owned_qty}, need {quantity}.",
                )
            new_qty = owned_qty - quantity
            new_cash = cash_balance + (quantity * current_price)
            with conn:
                if new_qty <= 0:
                    db.delete_position(conn, USER_ID, ticker)
                else:
                    db.upsert_position(conn, USER_ID, ticker, new_qty, existing["avg_cost"])
                db.update_cash_balance(conn, USER_ID, round(new_cash, 6))
                db.record_trade(conn, USER_ID, ticker, "sell", quantity, current_price)

        return ChatTradeResult(
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=current_price,
            success=True,
        )

    except Exception as exc:
        return ChatTradeResult(
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=current_price if quote else 0.0,
            success=False,
            error=str(exc),
        )


@router.post("/chat", response_model=ChatResponseModel)
def post_chat(body: ChatRequest):
    """
    Process a chat message:
    1. Build portfolio context
    2. Load chat history
    3. Call LLM via process_chat_message()
    4. Auto-execute trades and watchlist changes
    5. Persist messages
    6. Return structured response
    """
    # Import here so tests can mock without importing at module load time
    try:
        from llm.chat import process_chat_message
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="LLM module not available",
        )

    provider = get_provider()

    with get_connection() as conn:
        portfolio_context = _build_portfolio_context(conn, provider)
        raw_history = db.get_chat_messages(conn, USER_ID, limit=20)
        chat_history = [{"role": m["role"], "content": m["content"]} for m in raw_history]

    # Call LLM
    llm_response = process_chat_message(
        user_id=USER_ID,
        user_message=body.message,
        portfolio_context=portfolio_context,
        chat_history=chat_history,
    )

    # Auto-execute trades
    trade_results: list[ChatTradeResult] = []
    with get_connection() as conn:
        for trade in (llm_response.trades or []):
            result = _execute_trade_internal(
                conn, provider,
                ticker=trade.ticker,
                side=trade.side,
                quantity=trade.quantity,
            )
            trade_results.append(result)

        # Record portfolio snapshot after all AI trades
        if trade_results:
            from routers.portfolio import _build_portfolio_response
            portfolio = _build_portfolio_response(conn, provider)
            db.record_portfolio_snapshot(conn, USER_ID, portfolio.total_value)

        # Auto-execute watchlist changes
        watchlist_results: list[WatchlistChange] = []
        for change in (llm_response.watchlist_changes or []):
            ticker = change.ticker.strip().upper()
            action = change.action
            if action == "add":
                with get_connection() as wconn:
                    added = db.add_watchlist_ticker(wconn, USER_ID, ticker)
                if added:
                    provider.add_ticker(ticker)
            elif action == "remove":
                with get_connection() as wconn:
                    db.remove_watchlist_ticker(wconn, USER_ID, ticker)
                provider.remove_ticker(ticker)
            watchlist_results.append(WatchlistChange(ticker=ticker, action=action))

        # Persist user message
        actions_payload = {
            "trades": [t.model_dump() for t in trade_results],
            "watchlist_changes": [w.model_dump() for w in watchlist_results],
        }
        with get_connection() as mconn:
            db.add_chat_message(mconn, USER_ID, "user", body.message, actions=None)
            db.add_chat_message(
                mconn, USER_ID, "assistant", llm_response.message,
                actions=actions_payload,
            )

    return ChatResponseModel(
        message=llm_response.message,
        trades=trade_results,
        watchlist_changes=watchlist_results,
    )
