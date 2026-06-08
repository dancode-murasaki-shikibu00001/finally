'use client';

import type { ConnectionStatus } from '@/types';

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  status: ConnectionStatus;
}

const STATUS_CONFIG = {
  connected: { color: '#3fb950', label: 'LIVE' },
  reconnecting: { color: '#ecad0a', label: 'RECONNECTING' },
  disconnected: { color: '#f85149', label: 'DISCONNECTED' },
} as const;

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function Header({ totalValue, cashBalance, status }: HeaderProps) {
  const { color, label } = STATUS_CONFIG[status];

  return (
    <header className="h-14 flex items-center justify-between px-4 border-b border-border bg-bg-secondary shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-accent-yellow font-bold text-lg tracking-widest">FIN</span>
        <span className="text-accent-blue font-bold text-lg tracking-widest">ALLY</span>
        <span className="text-text-muted text-xs ml-2 hidden sm:block">AI TRADING WORKSTATION</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right hidden sm:block">
          <div className="text-text-secondary text-xs uppercase tracking-wider">Portfolio</div>
          <div className="text-text-primary font-bold text-base">${fmt(totalValue)}</div>
        </div>
        <div className="text-right hidden sm:block">
          <div className="text-text-secondary text-xs uppercase tracking-wider">Cash</div>
          <div className="text-accent-yellow font-semibold text-base">${fmt(cashBalance)}</div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }}
          />
          <span className="text-xs tracking-wider" style={{ color }}>
            {label}
          </span>
        </div>
      </div>
    </header>
  );
}
