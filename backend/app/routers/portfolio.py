"""Portfolio REST endpoints: positions, trades, and history."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.db import DEFAULT_USER_ID, DbDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    side: str
    quantity: float


class Position(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None


class PortfolioResponse(BaseModel):
    cash_balance: float
    positions_value: float
    total_value: float
    positions: list[Position]


class TradeResponse(BaseModel):
    ok: bool
    trade_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    cash_balance: float


@dataclass
class TradeResult:
    trade_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    cash_balance: float


class TradeError(ValueError):
    """Raised by execute_trade_logic when a trade cannot be completed."""


def execute_trade_logic(
    conn: sqlite3.Connection,
    cache,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER_ID,
) -> TradeResult:
    """Execute a market-order trade and persist all DB changes atomically.

    Raises TradeError with a human-readable message on any validation failure.
    The caller is responsible for wrapping this in a DB transaction if needed
    (this function opens its own ``with conn:`` block).
    """
    ticker = ticker.upper()
    side = side.lower()

    if side not in ("buy", "sell"):
        raise TradeError("side must be 'buy' or 'sell'")
    if quantity <= 0:
        raise TradeError("quantity must be positive")

    current_price = cache.get_price(ticker)
    if current_price is None:
        raise TradeError(f"No price available for {ticker}")

    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    cash_balance = row["cash_balance"] if row else 10000.0

    pos_row = conn.execute(
        "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    current_quantity = pos_row["quantity"] if pos_row else 0.0
    current_avg_cost = pos_row["avg_cost"] if pos_row else 0.0

    if side == "buy":
        cost = quantity * current_price
        if cost > cash_balance:
            raise TradeError(
                f"Insufficient funds: need ${cost:.2f}, have ${cash_balance:.2f}"
            )
        new_cash = cash_balance - cost
        new_quantity = current_quantity + quantity
        new_avg_cost = (
            (current_quantity * current_avg_cost + quantity * current_price) / new_quantity
        )
    else:
        if quantity > current_quantity:
            raise TradeError(
                f"Insufficient shares: need {quantity}, have {current_quantity}"
            )
        new_cash = cash_balance + quantity * current_price
        new_quantity = current_quantity - quantity
        new_avg_cost = current_avg_cost

    now = datetime.now(timezone.utc).isoformat()
    trade_id = str(uuid.uuid4())

    with conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_cash, user_id),
        )
        if new_quantity > 0:
            conn.execute(
                """
                INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, ticker) DO UPDATE SET
                    quantity = excluded.quantity,
                    avg_cost = excluded.avg_cost,
                    updated_at = excluded.updated_at
                """,
                (str(uuid.uuid4()), user_id, ticker, new_quantity, new_avg_cost, now),
            )
        else:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, user_id, ticker, side, quantity, current_price, now),
        )
        _record_snapshot(conn, user_id, new_cash, now, cache)

    return TradeResult(
        trade_id=trade_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=current_price,
        cash_balance=round(new_cash, 2),
    )


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(request: Request, db: DbDep) -> PortfolioResponse:
    cache = request.app.state.price_cache
    user_id = DEFAULT_USER_ID

    row = db.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    cash_balance = row["cash_balance"] if row else 10000.0

    pos_rows = db.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND quantity > 0",
        (user_id,),
    ).fetchall()

    positions: list[Position] = []
    positions_value = 0.0
    for r in pos_rows:
        ticker = r["ticker"]
        quantity = r["quantity"]
        avg_cost = r["avg_cost"]
        current_price = cache.get_price(ticker)

        if current_price is not None:
            unrealized_pnl = round((current_price - avg_cost) * quantity, 2)
            unrealized_pnl_pct = round(
                ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0, 4
            )
            positions_value += current_price * quantity
        else:
            unrealized_pnl = None
            unrealized_pnl_pct = None

        positions.append(
            Position(
                ticker=ticker,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
            )
        )

    return PortfolioResponse(
        cash_balance=round(cash_balance, 2),
        positions_value=round(positions_value, 2),
        total_value=round(cash_balance + positions_value, 2),
        positions=positions,
    )


@router.post("/trade", status_code=status.HTTP_201_CREATED, response_model=TradeResponse)
async def execute_trade(trade: TradeRequest, request: Request, db: DbDep) -> TradeResponse:
    try:
        result = execute_trade_logic(
            conn=db,
            cache=request.app.state.price_cache,
            ticker=trade.ticker,
            side=trade.side,
            quantity=trade.quantity,
        )
    except TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TradeResponse(
        ok=True,
        trade_id=result.trade_id,
        ticker=result.ticker,
        side=result.side,
        quantity=result.quantity,
        price=result.price,
        cash_balance=result.cash_balance,
    )


@router.get("/history")
async def get_portfolio_history(db: DbDep) -> dict:
    user_id = DEFAULT_USER_ID
    rows = db.execute(
        "SELECT total_value, recorded_at FROM portfolio_snapshots"
        " WHERE user_id = ? ORDER BY recorded_at ASC",
        (user_id,),
    ).fetchall()
    return {
        "snapshots": [
            {"total_value": r["total_value"], "recorded_at": r["recorded_at"]} for r in rows
        ]
    }


def _record_snapshot(
    conn: sqlite3.Connection,
    user_id: str,
    cash_balance: float,
    now: str,
    cache,
) -> None:
    """Insert one portfolio_snapshots row; called inside an open transaction."""
    pos_rows = conn.execute(
        "SELECT ticker, quantity FROM positions WHERE user_id = ? AND quantity > 0",
        (user_id,),
    ).fetchall()
    positions_value = sum(
        (cache.get_price(r["ticker"]) or 0.0) * r["quantity"] for r in pos_rows
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, cash_balance + positions_value, now),
    )
