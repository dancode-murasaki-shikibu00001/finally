export interface PriceUpdate {
  ticker: string
  price: number
  prev_price: number
  change_pct: number
  direction: 'up' | 'down' | 'unchanged'
  timestamp_ms: number
}

export interface Position {
  ticker: string
  quantity: number
  avg_cost: number
  current_price: number
  unrealized_pnl: number
  pnl_pct: number
}

export interface Portfolio {
  positions: Position[]
  cash_balance: number
  total_value: number
}

export interface WatchlistItem {
  ticker: string
  price: number
  change_pct: number
}

export interface HistoryPoint {
  total_value: number
  recorded_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  trades?: TradeAction[]
  watchlist_changes?: WatchlistAction[]
}

export interface TradeAction {
  ticker: string
  side: 'buy' | 'sell'
  quantity: number
}

export interface WatchlistAction {
  ticker: string
  action: 'add' | 'remove'
}

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected'
