'use client'

import type { ConnectionStatus, Portfolio } from '../types'

interface HeaderProps {
  portfolio: Portfolio | null
  connectionStatus: ConnectionStatus
}

const STARTING_VALUE = 10000

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function formatPnL(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${formatCurrency(value)}`
}

export default function Header({ portfolio, connectionStatus }: HeaderProps) {
  const totalValue = portfolio?.total_value ?? STARTING_VALUE
  const cashBalance = portfolio?.cash_balance ?? STARTING_VALUE
  const pnl = totalValue - STARTING_VALUE
  const pnlPct = ((totalValue - STARTING_VALUE) / STARTING_VALUE) * 100
  const isPositive = pnl >= 0

  const statusColor = {
    connected: '#3fb950',
    connecting: '#ecad0a',
    disconnected: '#f85149',
  }[connectionStatus]

  const statusLabel = {
    connected: 'LIVE',
    connecting: 'CONNECTING',
    disconnected: 'DISCONNECTED',
  }[connectionStatus]

  return (
    <header
      style={{ borderBottom: '1px solid #21262d', background: '#161b22' }}
      className="flex items-center justify-between px-4 py-2 shrink-0"
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div>
          <div
            style={{ color: '#ecad0a', letterSpacing: '0.1em' }}
            className="text-lg font-bold leading-none"
          >
            FIN<span style={{ color: '#209dd7' }}>ALLY</span>
          </div>
          <div style={{ color: '#8b949e', fontSize: '10px' }} className="uppercase tracking-widest">
            AI Trading Workstation
          </div>
        </div>
        <div
          style={{ width: '1px', height: '32px', background: '#21262d' }}
          className="mx-2"
        />
        {/* Connection status */}
        <div className="flex items-center gap-2" data-testid="connection-status">
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: statusColor,
              boxShadow: `0 0 6px ${statusColor}`,
              animation: connectionStatus === 'connected' ? 'pulseDot 2s ease-in-out infinite' : 'none',
            }}
          />
          <span style={{ color: statusColor, fontSize: '10px' }} className="font-bold tracking-widest">
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Portfolio value (center) */}
      <div className="flex flex-col items-center">
        <div style={{ color: '#8b949e', fontSize: '10px' }} className="uppercase tracking-widest mb-1">
          Portfolio Value
        </div>
        <div
          style={{
            fontSize: '22px',
            fontWeight: 700,
            color: isPositive ? '#3fb950' : '#f85149',
            letterSpacing: '-0.02em',
          }}
        >
          {formatCurrency(totalValue)}
        </div>
        <div
          style={{
            fontSize: '11px',
            color: isPositive ? '#3fb950' : '#f85149',
          }}
        >
          {formatPnL(pnl)} ({isPositive ? '+' : ''}{pnlPct.toFixed(2)}%)
        </div>
      </div>

      {/* Cash balance (right) */}
      <div className="flex items-center gap-6">
        <div className="text-right">
          <div style={{ color: '#8b949e', fontSize: '10px' }} className="uppercase tracking-widest mb-1">
            Cash Available
          </div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: '#e6edf3' }} data-testid="cash-balance">
            {formatCurrency(cashBalance)}
          </div>
        </div>
        <div
          style={{
            border: '1px solid #21262d',
            borderRadius: '4px',
            padding: '4px 10px',
            fontSize: '10px',
            color: '#8b949e',
            letterSpacing: '0.05em',
          }}
        >
          SIMULATED
        </div>
      </div>
    </header>
  )
}
