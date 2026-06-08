"""
Portfolio endpoints:
  GET  /api/portfolio         — positions, cash balance, total value, unrealized P&L
  POST /api/portfolio/trade   — execute a buy or sell market order
  GET  /api/portfolio/history — portfolio value snapshots over time
"""

from fastapi import APIRouter, HTTPException

from db.init_db import get_connection
from db import queries as db
from market.factory import get_provider
from models import (
    PortfolioPosition,
    PortfolioResponse,
    HistoryPoint,
    TradeRequest,
)

router = APIRouter()
USER_ID = "default"


def _build_portfolio_response(conn, provider) -> PortfolioResponse:
    """Build a PortfolioResponse from the DB and current prices."""
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
        current_price = quote.price if quote else avg_cost  # fallback to avg_cost if no quote

        unrealized_pnl = (current_price - avg_cost) * qty
        pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0
        invested_value += current_price * qty

        positions.append(
            PortfolioPosition(
                ticker=ticker,
                quantity=qty,
                avg_cost=avg_cost,
                current_price=current_price,
                unrealized_pnl=round(unrealized_pnl, 4),
                pnl_pct=round(pnl_pct, 4),
            )
        )

    total_value = cash_balance + invested_value
    return PortfolioResponse(
        positions=positions,
        cash_balance=round(cash_balance, 4),
        total_value=round(total_value, 4),
    )


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio():
    """Return current positions enriched with live prices, cash, and total value."""
    provider = get_provider()
    with get_connection() as conn:
        return _build_portfolio_response(conn, provider)


@router.post("/portfolio/trade")
def execute_trade(body: TradeRequest):
    """
    Execute a market order (buy or sell).

    BUY:  requires cash_balance >= quantity * current_price
    SELL: requires owned quantity >= requested quantity
    """
    ticker = body.ticker
    quantity = body.quantity
    side = body.side

    provider = get_provider()
    quote = provider.get_price(ticker)
    if quote is None:
        raise HTTPException(
            status_code=400,
            detail=f"No price available for {ticker}. Add it to the watchlist first.",
        )
    current_price = quote.price

    with get_connection() as conn:
        profile = db.get_user_profile(conn, USER_ID)
        cash_balance = profile["cash_balance"]

        if side == "buy":
            total_cost = quantity * current_price
            if cash_balance < total_cost:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient cash. Need ${total_cost:.2f}, "
                        f"have ${cash_balance:.2f}."
                    ),
                )

            # Update or create the position with weighted average cost
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
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient shares. Trying to sell {quantity}, "
                        f"but only holding {owned_qty} shares of {ticker}."
                    ),
                )

            new_qty = owned_qty - quantity
            new_cash = cash_balance + (quantity * current_price)

            with conn:
                if new_qty <= 0:
                    db.delete_position(conn, USER_ID, ticker)
                else:
                    db.upsert_position(
                        conn, USER_ID, ticker, new_qty, existing["avg_cost"]
                    )
                db.update_cash_balance(conn, USER_ID, round(new_cash, 6))
                db.record_trade(conn, USER_ID, ticker, "sell", quantity, current_price)

        # Record a portfolio snapshot immediately after the trade
        portfolio = _build_portfolio_response(conn, provider)
        db.record_portfolio_snapshot(conn, USER_ID, portfolio.total_value)

    return {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": current_price,
        "total": round(quantity * current_price, 4),
    }


@router.get("/portfolio/history", response_model=list[HistoryPoint])
def get_portfolio_history():
    """Return portfolio value snapshots ordered oldest-first (for P&L chart)."""
    with get_connection() as conn:
        snapshots = db.get_portfolio_snapshots(conn, USER_ID)
    return [
        HistoryPoint(total_value=s["total_value"], recorded_at=s["recorded_at"])
        for s in snapshots
    ]
