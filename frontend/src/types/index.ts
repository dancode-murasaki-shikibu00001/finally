export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent: number;
  direction: 'up' | 'down' | 'flat';
}

export interface WatchlistItem {
  ticker: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: string | null;
  added_at: string;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
}

export interface PortfolioData {
  cash_balance: number;
  positions_value: number;
  total_value: number;
  positions: Position[];
}

export interface SnapshotItem {
  total_value: number;
  recorded_at: string;
}

export interface TradeResult {
  ticker: string;
  side: string;
  quantity: number;
  price?: number;
  status: 'ok' | 'error';
  error?: string;
}

export interface WatchlistChangeResult {
  ticker: string;
  action: string;
  status: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  trades?: TradeResult[];
  watchlist_changes?: WatchlistChangeResult[];
  created_at?: string;
  pending?: boolean;
  error?: string;
}

export type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected';
