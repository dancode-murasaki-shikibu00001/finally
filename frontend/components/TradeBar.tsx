'use client'

import { useState, useCallback } from 'react'

interface TradeBarProps {
  selectedTicker: string | null
  currentPrice: number | null
  cashBalance: number
  onTradeComplete: () => void
}

export default function TradeBar({ selectedTicker, currentPrice, cashBalance, onTradeComplete }: TradeBarProps) {
  const [quantity, setQuantity] = useState('1')
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null)
  const [loading, setLoading] = useState(false)

  const estimatedCost = currentPrice && parseFloat(quantity) > 0
    ? currentPrice * parseFloat(quantity)
    : null

  const executeTrade = useCallback(async (side: 'buy' | 'sell') => {
    if (!selectedTicker) return
    const qty = parseFloat(quantity)
    if (!qty || qty <= 0) {
      setStatus({ ok: false, message: 'Enter a valid quantity' })
      return
    }

    setLoading(true)
    setStatus(null)

    try {
      const res = await fetch('/api/portfolio/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: selectedTicker, quantity: qty, side }),
      })

      const body = await res.json()

      if (res.ok) {
        const price = body.price ?? currentPrice ?? 0
        setStatus({
          ok: true,
          message: `${side.toUpperCase()} ${qty} ${selectedTicker} @ $${price.toFixed(2)}`,
        })
        onTradeComplete()
      } else {
        setStatus({ ok: false, message: body.detail ?? `Trade failed (${res.status})` })
      }
    } catch (err) {
      setStatus({ ok: false, message: err instanceof Error ? err.message : 'Network error' })
    } finally {
      setLoading(false)
    }
  }, [selectedTicker, quantity, currentPrice, onTradeComplete])

  const disabled = !selectedTicker || loading

  return (
    <div
      data-testid="trade-bar"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px',
        background: '#161b22',
        borderTop: '1px solid #21262d',
        flexShrink: 0,
      }}
    >
      {/* Ticker badge */}
      <div
        style={{
          minWidth: '72px',
          padding: '4px 8px',
          background: selectedTicker ? '#0d1117' : '#0d1117',
          border: '1px solid #21262d',
          borderRadius: '4px',
          fontSize: '13px',
          fontWeight: 700,
          color: selectedTicker ? '#ecad0a' : '#8b949e',
          textAlign: 'center',
          letterSpacing: '0.05em',
        }}
      >
        {selectedTicker ?? 'N/A'}
      </div>

      {/* Price display */}
      <div
        style={{
          minWidth: '90px',
          fontSize: '13px',
          color: '#e6edf3',
          fontWeight: 600,
        }}
      >
        {currentPrice != null
          ? `$${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
          : '—'
        }
      </div>

      {/* Qty label */}
      <span style={{ fontSize: '11px', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Qty
      </span>

      {/* Quantity input */}
      <input
        type="number"
        data-testid="trade-quantity"
        value={quantity}
        onChange={e => setQuantity(e.target.value)}
        min="0.01"
        step="1"
        style={{
          width: '80px',
          background: '#0d1117',
          border: '1px solid #21262d',
          borderRadius: '4px',
          color: '#e6edf3',
          padding: '5px 8px',
          fontSize: '13px',
          fontFamily: 'inherit',
          outline: 'none',
          textAlign: 'right',
        }}
      />

      {/* Estimated cost */}
      {estimatedCost != null && (
        <span style={{ fontSize: '11px', color: '#8b949e', minWidth: '80px' }}>
          ≈ ${estimatedCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      )}

      <div style={{ flex: 1 }} />

      {/* Buy button */}
      <button
        data-testid="buy-button"
        onClick={() => executeTrade('buy')}
        disabled={disabled}
        style={{
          background: disabled ? '#21262d' : '#3fb950',
          border: 'none',
          borderRadius: '4px',
          color: '#fff',
          padding: '6px 20px',
          fontSize: '13px',
          fontFamily: 'inherit',
          fontWeight: 700,
          cursor: disabled ? 'not-allowed' : 'pointer',
          letterSpacing: '0.05em',
          transition: 'background 0.15s',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {loading ? '...' : 'BUY'}
      </button>

      {/* Sell button */}
      <button
        data-testid="sell-button"
        onClick={() => executeTrade('sell')}
        disabled={disabled}
        style={{
          background: disabled ? '#21262d' : '#f85149',
          border: 'none',
          borderRadius: '4px',
          color: '#fff',
          padding: '6px 20px',
          fontSize: '13px',
          fontFamily: 'inherit',
          fontWeight: 700,
          cursor: disabled ? 'not-allowed' : 'pointer',
          letterSpacing: '0.05em',
          transition: 'background 0.15s',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {loading ? '...' : 'SELL'}
      </button>

      {/* Status message */}
      {status && (
        <div
          data-testid="trade-status"
          style={{
            fontSize: '12px',
            color: status.ok ? '#3fb950' : '#f85149',
            maxWidth: '300px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {status.ok ? '✓ ' : '✗ '}{status.message}
        </div>
      )}

      {/* Cash display */}
      <div style={{ fontSize: '11px', color: '#8b949e', marginLeft: '8px', whiteSpace: 'nowrap' }}>
        Cash: ${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
    </div>
  )
}
