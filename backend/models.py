"""
Pydantic v2 models for all API request/response shapes.
"""

from typing import Literal, Optional
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Trade
# ---------------------------------------------------------------------------

class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

class WatchlistAddRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        stripped = v.strip().upper()
        if not stripped:
            raise ValueError("ticker must not be empty")
        return stripped


class WatchlistItem(BaseModel):
    ticker: str
    price: Optional[float] = None
    change_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class PortfolioPosition(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    pnl_pct: float


class PortfolioResponse(BaseModel):
    positions: list[PortfolioPosition]
    cash_balance: float
    total_value: float


class HistoryPoint(BaseModel):
    total_value: float
    recorded_at: str


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------

class PriceResponse(BaseModel):
    ticker: str
    price: float
    change_pct: float


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class ChatTradeResult(BaseModel):
    ticker: str
    side: str
    quantity: float
    price: float
    success: bool
    error: Optional[str] = None


class ChatResponseModel(BaseModel):
    message: str
    trades: list[ChatTradeResult] = []
    watchlist_changes: list[WatchlistChange] = []
