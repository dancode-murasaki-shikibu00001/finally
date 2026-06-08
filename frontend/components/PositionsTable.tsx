'use client'

import { useMemo } from 'react'
import type { Position } from '../types'

interface PositionsTableProps {
  positions: Position[]
}

function fmt2(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPnL(n: number): string {
  const sign = n >= 0 ? '+' : ''
  return `${sign}$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtPct(n: number): string {
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

export default function PositionsTable({ positions }: PositionsTableProps) {
  const sorted = useMemo(() => {
    if (!positions) return []
    return [...positions].sort((a, b) => b.unrealized_pnl - a.unrealized_pnl)
  }, [positions])

  return (
    <div data-testid="positions-table" style={{ height: '100%', overflowY: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '12px',
        }}
      >
        <thead>
          <tr
            style={{
              background: '#161b22',
              position: 'sticky',
              top: 0,
              zIndex: 1,
            }}
          >
            {['TICKER', 'QTY', 'AVG COST', 'CUR PRICE', 'UNRLZD P&L', '% CHG'].map((col, i) => (
              <th
                key={col}
                style={{
                  padding: '5px 8px',
                  textAlign: i === 0 ? 'left' : 'right',
                  fontSize: '10px',
                  fontWeight: 700,
                  color: '#8b949e',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  borderBottom: '1px solid #21262d',
                  whiteSpace: 'nowrap',
                  fontFamily: 'ui-monospace, monospace',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td
                colSpan={6}
                style={{
                  padding: '16px',
                  textAlign: 'center',
                  color: '#8b949e',
                  fontSize: '12px',
                }}
              >
                No open positions
              </td>
            </tr>
          ) : (
            sorted.map(pos => {
              const isPositive = pos.unrealized_pnl >= 0
              const pnlColor = isPositive ? '#3fb950' : '#f85149'

              return (
                <tr
                  key={pos.ticker}
                  style={{
                    borderBottom: '1px solid rgba(33,38,45,0.6)',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLTableRowElement).style.background = '#1c2128'
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLTableRowElement).style.background = 'transparent'
                  }}
                >
                  <td
                    style={{
                      padding: '5px 8px',
                      textAlign: 'left',
                      fontWeight: 700,
                      color: '#ecad0a',
                      letterSpacing: '0.03em',
                    }}
                  >
                    {pos.ticker}
                  </td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: '#e6edf3' }}>
                    {pos.quantity % 1 === 0 ? pos.quantity.toFixed(0) : pos.quantity.toFixed(4)}
                  </td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: '#8b949e' }}>
                    ${fmt2(pos.avg_cost)}
                  </td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: '#e6edf3', fontWeight: 600 }}>
                    ${fmt2(pos.current_price)}
                  </td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: pnlColor, fontWeight: 600 }}>
                    {fmtPnL(pos.unrealized_pnl)}
                  </td>
                  <td
                    style={{
                      padding: '5px 8px',
                      textAlign: 'right',
                      color: pnlColor,
                      fontWeight: 600,
                    }}
                  >
                    {fmtPct(pos.pnl_pct)}
                  </td>
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </div>
  )
}
