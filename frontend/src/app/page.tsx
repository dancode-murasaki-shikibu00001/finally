'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { usePriceStream } from '@/hooks/usePriceStream';
import Header from '@/components/Header';
import WatchlistPanel from '@/components/WatchlistPanel';
import MainChart from '@/components/MainChart';
import PnLChart from '@/components/PnLChart';
import PortfolioHeatmap from '@/components/PortfolioHeatmap';
import PositionsTable from '@/components/PositionsTable';
import TradeBar from '@/components/TradeBar';
import ChatPanel from '@/components/ChatPanel';
import type {
  WatchlistItem,
  PortfolioData,
  SnapshotItem,
  ChatMessage,
} from '@/types';
import {
  fetchWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  fetchPortfolio,
  fetchPortfolioHistory,
  executeTrade,
  sendChatMessage,
} from '@/lib/api';

// Max chart data points accumulated from SSE
const CHART_MAX_POINTS = 300;

export default function TradingWorkstation() {
  const { prices, sparklines, status } = usePriceStream();

  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [history, setHistory] = useState<SnapshotItem[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatOpen, setChatOpen] = useState(true);

  // Price history for main chart (accumulated from SSE per ticker)
  const chartHistoryRef = useRef<Record<string, Array<{ time: number; value: number }>>>({});
  const [chartData, setChartData] = useState<Array<{ time: number; value: number }>>([]);

  // Accumulate main chart data from SSE prices
  useEffect(() => {
    if (!selectedTicker || !prices[selectedTicker]) return;
    const update = prices[selectedTicker];
    const history = chartHistoryRef.current[selectedTicker] || [];
    const lastEntry = history[history.length - 1];
    const t = Math.floor(update.timestamp);
    if (lastEntry && lastEntry.time === t) return; // same second, skip
    const trimmed = history.length >= CHART_MAX_POINTS ? history.slice(-CHART_MAX_POINTS + 1) : history;
    const next = [...trimmed, { time: t, value: update.price }];
    chartHistoryRef.current[selectedTicker] = next;
    setChartData(next);
  }, [prices, selectedTicker]);

  // Sync all tickers' history even when not selected (so switching is instant)
  useEffect(() => {
    for (const [ticker, update] of Object.entries(prices)) {
      const h = chartHistoryRef.current[ticker] || [];
      const t = Math.floor(update.timestamp);
      const last = h[h.length - 1];
      if (last && last.time === t) continue;
      const trimmed = h.length >= CHART_MAX_POINTS ? h.slice(-CHART_MAX_POINTS + 1) : h;
      chartHistoryRef.current[ticker] = [...trimmed, { time: t, value: update.price }];
    }
  }, [prices]);

  const handleSelectTicker = useCallback((ticker: string) => {
    setSelectedTicker(ticker);
    setChartData(chartHistoryRef.current[ticker] || []);
  }, []);

  // Initial data load
  const refreshWatchlist = useCallback(async () => {
    try {
      setWatchlist(await fetchWatchlist());
    } catch {
      // ignore
    }
  }, []);

  const refreshPortfolio = useCallback(async () => {
    try {
      setPortfolio(await fetchPortfolio());
    } catch {
      // ignore
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      setHistory(await fetchPortfolioHistory());
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    refreshWatchlist();
    refreshPortfolio();
    refreshHistory();
  }, [refreshWatchlist, refreshPortfolio, refreshHistory]);

  // Poll portfolio every 8 seconds; history every 30 seconds
  useEffect(() => {
    const pt = setInterval(refreshPortfolio, 8000);
    const ht = setInterval(refreshHistory, 30000);
    return () => {
      clearInterval(pt);
      clearInterval(ht);
    };
  }, [refreshPortfolio, refreshHistory]);

  // Watchlist handlers
  const handleAddWatchlist = useCallback(
    async (ticker: string) => {
      await addToWatchlist(ticker);
      await refreshWatchlist();
    },
    [refreshWatchlist]
  );

  const handleRemoveWatchlist = useCallback(
    async (ticker: string) => {
      try {
        await removeFromWatchlist(ticker);
        await refreshWatchlist();
      } catch {
        // ignore 404
      }
    },
    [refreshWatchlist]
  );

  // Trade handler
  const handleTrade = useCallback(
    async (ticker: string, side: 'buy' | 'sell', quantity: number) => {
      await executeTrade(ticker, side, quantity);
      await refreshPortfolio();
      await refreshHistory();
    },
    [refreshPortfolio, refreshHistory]
  );

  // Chat handler
  const handleChatSend = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: 'user',
        content: text,
      };
      const pendingMsg: ChatMessage = {
        id: `pending-${Date.now()}`,
        role: 'assistant',
        content: '',
        pending: true,
      };

      setChatMessages((prev) => [...prev, userMsg, pendingMsg]);

      try {
        const res = await sendChatMessage(text);
        const assistantMsg: ChatMessage = {
          id: res.id,
          role: 'assistant',
          content: res.message,
          trades: res.trades,
          watchlist_changes: res.watchlist_changes,
          created_at: res.created_at,
        };

        setChatMessages((prev) =>
          prev.map((m) => (m.pending ? assistantMsg : m))
        );

        // Refresh data after AI actions
        if (res.trades.length > 0) {
          await refreshPortfolio();
          await refreshHistory();
        }
        if (res.watchlist_changes.length > 0) {
          await refreshWatchlist();
        }
      } catch (e: unknown) {
        const errMsg: ChatMessage = {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: 'Sorry, something went wrong.',
          error: e instanceof Error ? e.message : 'Unknown error',
        };
        setChatMessages((prev) => prev.map((m) => (m.pending ? errMsg : m)));
      }
    },
    [refreshPortfolio, refreshHistory, refreshWatchlist]
  );

  // Build enriched positions for display (merge live prices)
  const enrichedPositions = (portfolio?.positions ?? []).map((p) => {
    const live = prices[p.ticker];
    if (live) {
      const current_price = live.price;
      const unrealized_pnl = parseFloat(((current_price - p.avg_cost) * p.quantity).toFixed(2));
      const unrealized_pnl_pct = parseFloat(
        p.avg_cost > 0 ? ((current_price - p.avg_cost) / p.avg_cost * 100).toFixed(4) : '0'
      );
      return { ...p, current_price, unrealized_pnl, unrealized_pnl_pct };
    }
    return p;
  });

  // Compute live total value
  const liveTotalValue = (() => {
    if (!portfolio) return 0;
    const positionsValue = enrichedPositions.reduce(
      (sum, p) => sum + (p.current_price ?? p.avg_cost) * p.quantity,
      0
    );
    return portfolio.cash_balance + positionsValue;
  })();

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg-primary">
      <Header
        totalValue={liveTotalValue}
        cashBalance={portfolio?.cash_balance ?? 0}
        status={status}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Watchlist */}
        <div className="w-64 shrink-0 border-r border-border overflow-hidden flex flex-col">
          <WatchlistPanel
            items={watchlist}
            prices={prices}
            sparklines={sparklines}
            selectedTicker={selectedTicker}
            onSelect={handleSelectTicker}
            onAdd={handleAddWatchlist}
            onRemove={handleRemoveWatchlist}
          />
        </div>

        {/* Center: Charts + Table + Trade Bar */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          {/* Main chart */}
          <div className="h-64 shrink-0 border-b border-border">
            <MainChart
              ticker={selectedTicker}
              priceHistory={chartData}
              currentPrice={selectedTicker ? (prices[selectedTicker] ?? null) : null}
            />
          </div>

          {/* P&L + Heatmap row */}
          <div className="flex h-48 shrink-0 border-b border-border min-h-0">
            <div className="flex-1 border-r border-border min-w-0">
              <PnLChart snapshots={history} />
            </div>
            <div className="w-72 shrink-0 min-w-0">
              <PortfolioHeatmap
                positions={enrichedPositions}
                onSelect={handleSelectTicker}
              />
            </div>
          </div>

          {/* Positions table */}
          <div className="flex-1 overflow-hidden min-h-0">
            <PositionsTable
              positions={enrichedPositions}
              onSelect={handleSelectTicker}
            />
          </div>

          {/* Trade bar */}
          <TradeBar
            prices={prices}
            cashBalance={portfolio?.cash_balance ?? 0}
            selectedTicker={selectedTicker}
            onTrade={handleTrade}
          />
        </div>

        {/* Right: Chat panel */}
        <ChatPanel
          messages={chatMessages}
          onSend={handleChatSend}
          isOpen={chatOpen}
          onToggle={() => setChatOpen((v) => !v)}
        />
      </div>
    </div>
  );
}
