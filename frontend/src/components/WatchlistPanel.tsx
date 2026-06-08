'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import type { PriceUpdate, WatchlistItem } from '@/types';
import Sparkline from './Sparkline';

interface WatchlistPanelProps {
  items: WatchlistItem[];
  prices: Record<string, PriceUpdate>;
  sparklines: Record<string, number[]>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function PriceCell({
  ticker,
  price,
  direction,
}: {
  ticker: string;
  price: number | null;
  direction: string | null;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const prevPriceRef = useRef<number | null>(price);

  useEffect(() => {
    if (price === null || prevPriceRef.current === price) return;
    const el = ref.current;
    if (!el) return;

    el.classList.remove('flash-up', 'flash-down');
    void el.offsetWidth; // reflow to restart animation
    if (direction === 'up') el.classList.add('flash-up');
    else if (direction === 'down') el.classList.add('flash-down');

    const timer = setTimeout(() => {
      el.classList.remove('flash-up', 'flash-down');
    }, 650);

    prevPriceRef.current = price;
    return () => clearTimeout(timer);
  }, [price, direction]);

  return (
    <span
      ref={ref}
      className="font-mono text-sm font-semibold tabular-nums px-1 rounded"
      style={{ color: direction === 'up' ? '#3fb950' : direction === 'down' ? '#f85149' : '#e6edf3' }}
    >
      {price !== null ? `$${fmt(price)}` : '—'}
    </span>
  );
}

export default function WatchlistPanel({
  items,
  prices,
  sparklines,
  selectedTicker,
  onSelect,
  onAdd,
  onRemove,
}: WatchlistPanelProps) {
  const [addTicker, setAddTicker] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  const handleAdd = useCallback(async () => {
    const t = addTicker.trim().toUpperCase();
    if (!t) return;
    setAdding(true);
    setError('');
    try {
      await onAdd(t);
      setAddTicker('');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to add ticker');
    } finally {
      setAdding(false);
    }
  }, [addTicker, onAdd]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleAdd();
    },
    [handleAdd]
  );

  return (
    <div className="flex flex-col h-full bg-bg-secondary">
      <div className="px-3 py-2 border-b border-border shrink-0">
        <div className="text-text-secondary text-xs uppercase tracking-wider mb-2">Watchlist</div>
        <div className="flex gap-1">
          <input
            type="text"
            value={addTicker}
            onChange={(e) => setAddTicker(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            placeholder="Add ticker…"
            maxLength={10}
            className="flex-1 bg-bg-tertiary border border-border text-text-primary text-xs px-2 py-1 rounded outline-none focus:border-accent-blue placeholder:text-text-muted font-mono uppercase"
          />
          <button
            onClick={handleAdd}
            disabled={adding || !addTicker.trim()}
            className="px-2 py-1 bg-accent-blue text-white text-xs rounded hover:opacity-80 disabled:opacity-40 font-semibold"
          >
            +
          </button>
        </div>
        {error && <div className="text-price-down text-xs mt-1">{error}</div>}
      </div>

      <div className="flex-1 overflow-y-auto">
        {items.length === 0 && (
          <div className="text-text-muted text-xs text-center mt-8 px-4">
            Add tickers to your watchlist
          </div>
        )}
        {items.map((item) => {
          const live = prices[item.ticker];
          const price = live?.price ?? item.price;
          const direction = live?.direction ?? item.direction;
          const changePct = live?.change_percent ?? item.change_percent;
          const sl = sparklines[item.ticker] || [];
          const isSelected = selectedTicker === item.ticker;

          return (
            <div
              key={item.ticker}
              onClick={() => onSelect(item.ticker)}
              className={`group flex items-center justify-between px-3 py-2 cursor-pointer border-b border-border/50 hover:bg-bg-tertiary transition-colors ${
                isSelected ? 'bg-bg-tertiary border-l-2 border-l-accent-blue' : ''
              }`}
            >
              <div className="flex flex-col gap-0.5 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-text-primary text-sm font-bold tracking-wide">{item.ticker}</span>
                  {changePct !== null && (
                    <span
                      className="text-xs font-mono"
                      style={{ color: changePct >= 0 ? '#3fb950' : '#f85149' }}
                    >
                      {changePct >= 0 ? '+' : ''}
                      {changePct.toFixed(2)}%
                    </span>
                  )}
                </div>
                <PriceCell ticker={item.ticker} price={price} direction={direction} />
              </div>
              <div className="flex items-center gap-2">
                {sl.length > 1 && <Sparkline prices={sl} />}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(item.ticker);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-price-down text-xs transition-opacity px-1"
                  title="Remove"
                >
                  ×
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
