'use client';

import type { Position } from '@/types';

interface PositionsTableProps {
  positions: Position[];
  onSelect?: (ticker: string) => void;
}

function fmt(n: number, decimals = 2) {
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export default function PositionsTable({ positions, onSelect }: PositionsTableProps) {
  const active = positions.filter((p) => p.quantity > 0);

  return (
    <div className="flex flex-col h-full bg-bg-secondary">
      <div className="px-3 py-1.5 border-b border-border shrink-0">
        <span className="text-text-secondary text-xs uppercase tracking-wider">
          Positions ({active.length})
        </span>
      </div>
      <div className="flex-1 overflow-auto">
        {active.length === 0 ? (
          <div className="flex items-center justify-center h-full text-text-muted text-xs">
            No open positions
          </div>
        ) : (
          <table className="w-full text-xs font-mono">
            <thead className="sticky top-0 bg-bg-tertiary">
              <tr>
                <th className="px-3 py-1.5 text-left text-text-secondary font-normal uppercase tracking-wider">Ticker</th>
                <th className="px-3 py-1.5 text-right text-text-secondary font-normal uppercase tracking-wider">Qty</th>
                <th className="px-3 py-1.5 text-right text-text-secondary font-normal uppercase tracking-wider">Avg Cost</th>
                <th className="px-3 py-1.5 text-right text-text-secondary font-normal uppercase tracking-wider">Price</th>
                <th className="px-3 py-1.5 text-right text-text-secondary font-normal uppercase tracking-wider">P&amp;L</th>
                <th className="px-3 py-1.5 text-right text-text-secondary font-normal uppercase tracking-wider">%</th>
              </tr>
            </thead>
            <tbody>
              {active.map((p) => {
                const pnl = p.unrealized_pnl;
                const pnlPct = p.unrealized_pnl_pct;
                const color = pnl === null ? '#7d8590' : pnl >= 0 ? '#3fb950' : '#f85149';

                return (
                  <tr
                    key={p.ticker}
                    onClick={() => onSelect?.(p.ticker)}
                    className="border-b border-border/50 hover:bg-bg-tertiary cursor-pointer transition-colors"
                  >
                    <td className="px-3 py-1.5 text-text-primary font-bold">{p.ticker}</td>
                    <td className="px-3 py-1.5 text-right text-text-primary">{fmt(p.quantity, 4)}</td>
                    <td className="px-3 py-1.5 text-right text-text-secondary">${fmt(p.avg_cost)}</td>
                    <td className="px-3 py-1.5 text-right text-text-primary">
                      {p.current_price !== null ? `$${fmt(p.current_price)}` : '—'}
                    </td>
                    <td className="px-3 py-1.5 text-right font-semibold" style={{ color }}>
                      {pnl !== null ? `${pnl >= 0 ? '+' : ''}$${fmt(Math.abs(pnl))}` : '—'}
                    </td>
                    <td className="px-3 py-1.5 text-right font-semibold" style={{ color }}>
                      {pnlPct !== null
                        ? `${pnlPct >= 0 ? '+' : ''}${Math.abs(pnlPct).toFixed(2)}%`
                        : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
