from pydantic import BaseModel
from typing import Literal


class TradeRequest(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    message: str
    trades: list[TradeRequest] = []
    watchlist_changes: list[WatchlistChange] = []
