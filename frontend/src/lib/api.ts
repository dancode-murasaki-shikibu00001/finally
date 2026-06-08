import type { PortfolioData, WatchlistItem, SnapshotItem } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  const data = await request<{ tickers: WatchlistItem[] }>('/api/watchlist');
  return data.tickers;
}

export async function addToWatchlist(ticker: string): Promise<void> {
  await request('/api/watchlist', {
    method: 'POST',
    body: JSON.stringify({ ticker }),
  });
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await request(`/api/watchlist/${ticker}`, { method: 'DELETE' });
}

export async function fetchPortfolio(): Promise<PortfolioData> {
  return request<PortfolioData>('/api/portfolio');
}

export async function fetchPortfolioHistory(): Promise<SnapshotItem[]> {
  const data = await request<{ snapshots: SnapshotItem[] }>('/api/portfolio/history');
  return data.snapshots;
}

export async function executeTrade(
  ticker: string,
  side: 'buy' | 'sell',
  quantity: number
): Promise<{ ok: boolean; ticker: string; side: string; quantity: number; price: number; cash_balance: number }> {
  return request('/api/portfolio/trade', {
    method: 'POST',
    body: JSON.stringify({ ticker, side, quantity }),
  });
}

export async function sendChatMessage(message: string): Promise<{
  id: string;
  message: string;
  trades: Array<{ ticker: string; side: string; quantity: number; price?: number; status: 'ok' | 'error'; error?: string }>;
  watchlist_changes: Array<{ ticker: string; action: string; status: string }>;
  created_at: string;
}> {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
