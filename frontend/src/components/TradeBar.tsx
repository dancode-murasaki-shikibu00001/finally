'use client';

import { useState, useCallback } from 'react';
import type { PriceUpdate } from '@/types';

interface TradeBarProps {
  prices: Record<string, PriceUpdate>;
  cashBalance: number;
  selectedTicker: string | null;
  onTrade: (ticker: string, side: 'buy' | 'sell', quantity: number) => Promise<void>;
}

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function TradeBar({ prices, cashBalance, selectedTicker, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState('');
  const [quantity, setQuantity] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const effectiveTicker = selectedTicker && !ticker ? selectedTicker : ticker.toUpperCase();
  const price = prices[effectiveTicker]?.price;
  const cost = price && quantity ? price * parseFloat(quantity || '0') : null;

  const flash = useCallback((text: string, ok: boolean) => {
    setMessage({ text, ok });
    setTimeout(() => setMessage(null), 3000);
  }, []);

  const submit = useCallback(
    async (side: 'buy' | 'sell') => {
      const t = effectiveTicker.trim().toUpperCase();
      const q = parseFloat(quantity);
      if (!t || !q || q <= 0) {
        flash('Enter a valid ticker and quantity', false);
        return;
      }
      setLoading(true);
      try {
        await onTrade(t, side, q);
        flash(`${side.toUpperCase()} ${q} ${t} @ $${fmt(prices[t]?.price ?? 0)}`, true);
        setQuantity('');
      } catch (e: unknown) {
        flash(e instanceof Error ? e.message : 'Trade failed', false);
      } finally {
        setLoading(false);
      }
    },
    [effectiveTicker, quantity, onTrade, prices, flash]
  );

  return (
    <div className="flex items-center gap-2 px-4 h-16 bg-bg-secondary border-t border-border shrink-0">
      <input
        type="text"
        value={ticker || (selectedTicker ?? '')}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        placeholder="Ticker"
        maxLength={10}
        className="w-24 bg-bg-tertiary border border-border text-text-primary text-sm px-2 py-1.5 rounded outline-none focus:border-accent-blue font-mono uppercase placeholder:text-text-muted"
      />
      <input
        type="number"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Qty"
        min="0"
        step="1"
        className="w-24 bg-bg-tertiary border border-border text-text-primary text-sm px-2 py-1.5 rounded outline-none focus:border-accent-blue font-mono placeholder:text-text-muted"
      />
      {cost !== null && (
        <span className="text-text-secondary text-xs font-mono hidden sm:block">
          ≈ ${fmt(cost)}
        </span>
      )}
      {message ? (
        <span
          className="text-xs font-mono flex-1"
          style={{ color: message.ok ? '#3fb950' : '#f85149' }}
        >
          {message.text}
        </span>
      ) : (
        <span className="text-text-muted text-xs hidden sm:block flex-1">
          Cash: ${fmt(cashBalance)}
        </span>
      )}
      <button
        onClick={() => submit('buy')}
        disabled={loading}
        className="px-4 py-1.5 bg-price-up text-white text-sm font-bold rounded hover:opacity-80 disabled:opacity-40 tracking-wider"
      >
        BUY
      </button>
      <button
        onClick={() => submit('sell')}
        disabled={loading}
        className="px-4 py-1.5 bg-price-down text-white text-sm font-bold rounded hover:opacity-80 disabled:opacity-40 tracking-wider"
      >
        SELL
      </button>
    </div>
  );
}
