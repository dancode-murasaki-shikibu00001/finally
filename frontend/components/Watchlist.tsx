'use client'

import { useState, useCallback } from 'react'
import type { WatchlistItem } from '../types'
import Sparkline from './Sparkline'

interface WatchlistProps {
  watchlist: WatchlistItem[]
  flashState: Record<string, 'up' | 'down' | null>
  priceHistory: Record<string, number[]>
  selectedTicker: string | null
  onSelectTicker: (ticker: string) => void
  onAddTicker: (ticker: string) => Promise<{ ok: boolean; error?: string }>
  onRemoveTicker: (ticker: string) => Promise<{ ok: boolean; error?: string }>
  loading: boolean
}

function formatPrice(price: number): string {
  return price.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export default function Watchlist({
  watchlist,
  flashState,
  priceHistory,
  selectedTicker,
  onSelectTicker,
  onAddTicker,
  onRemoveTicker,
  loading,
}: WatchlistProps) {
  const [addInput, setAddInput] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [addLoading, setAddLoading] = useState(false)
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null)

  const handleAdd = useCallback(async () => {
    const ticker = addInput.trim().toUpperCase()
    if (!ticker) return

    setAddLoading(true)
    setAddError(null)

    const result = await onAddTicker(ticker)
    if (result.ok) {
      setAddInput('')
    } else {
      setAddError(result.error ?? 'Failed to add ticker')
    }
    setAddLoading(false)
  }, [addInput, onAddTicker])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleAdd()
  }

  return (
    <div
      data-testid="watchlist"
      style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#161b22', borderRight: '1px solid #21262d' }}
    >
      {/* Header */}
      <div
        style={{
          padding: '8px 12px',
          borderBottom: '1px solid #21262d',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: '10px', fontWeight: 700, color: '#8b949e', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          Watchlist
        </span>
        <span style={{ fontSize: '10px', color: '#8b949e' }}>
          {watchlist.length} tickers
        </span>
      </div>

      {/* Column headers */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '56px 80px 68px 76px',
          padding: '4px 8px',
          borderBottom: '1px solid #21262d',
          gap: '4px',
        }}
      >
        {['SYMBOL', 'CHART', 'PRICE', 'CHG%'].map(h => (
          <div key={h} style={{ fontSize: '9px', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '0.08em', textAlign: h === 'SYMBOL' ? 'left' : 'right' }}>
            {h}
          </div>
        ))}
      </div>

      {/* Ticker rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && watchlist.length === 0 ? (
          <div style={{ padding: '16px', color: '#8b949e', fontSize: '12px', textAlign: 'center' }}>
            Loading...
          </div>
        ) : watchlist.length === 0 ? (
          <div style={{ padding: '16px', color: '#8b949e', fontSize: '12px', textAlign: 'center' }}>
            No tickers in watchlist
          </div>
        ) : (
          watchlist.map(item => {
            const flash = flashState[item.ticker]
            const history = priceHistory[item.ticker] ?? []
            const isSelected = selectedTicker === item.ticker
            const isHovered = hoveredTicker === item.ticker
            const isPositive = item.change_pct >= 0

            let rowBg = 'transparent'
            if (flash === 'up') rowBg = 'rgba(63, 185, 80, 0.15)'
            else if (flash === 'down') rowBg = 'rgba(248, 81, 73, 0.15)'
            else if (isSelected) rowBg = 'rgba(32, 157, 215, 0.12)'
            else if (isHovered) rowBg = 'rgba(255,255,255,0.04)'

            return (
              <div
                key={item.ticker}
                onClick={() => onSelectTicker(item.ticker)}
                onMouseEnter={() => setHoveredTicker(item.ticker)}
                onMouseLeave={() => setHoveredTicker(null)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '56px 80px 68px 76px',
                  padding: '5px 8px',
                  gap: '4px',
                  cursor: 'pointer',
                  background: rowBg,
                  borderLeft: isSelected ? '2px solid #209dd7' : '2px solid transparent',
                  borderBottom: '1px solid rgba(33,38,45,0.5)',
                  transition: 'background 0.1s ease',
                  alignItems: 'center',
                }}
              >
                {/* Symbol + remove */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', overflow: 'hidden' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: '#e6edf3', letterSpacing: '0.03em' }}>
                    {item.ticker}
                  </span>
                  {isHovered && (
                    <button
                      data-testid={`remove-ticker-${item.ticker}`}
                      onClick={async (e) => {
                        e.stopPropagation()
                        await onRemoveTicker(item.ticker)
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#f85149',
                        cursor: 'pointer',
                        padding: '0 2px',
                        fontSize: '12px',
                        lineHeight: 1,
                        flexShrink: 0,
                      }}
                      title="Remove from watchlist"
                    >
                      ×
                    </button>
                  )}
                </div>

                {/* Sparkline */}
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Sparkline data={history} width={72} height={24} />
                </div>

                {/* Price */}
                <div
                  data-testid="ticker-price"
                  className={flash === 'up' ? 'price-flash-up' : flash === 'down' ? 'price-flash-down' : ''}
                  style={{
                    fontSize: '12px',
                    fontWeight: 600,
                    color: '#e6edf3',
                    textAlign: 'right',
                  }}
                >
                  {formatPrice(item.price)}
                </div>

                {/* Change % */}
                <div
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: isPositive ? '#3fb950' : '#f85149',
                    textAlign: 'right',
                  }}
                >
                  {isPositive ? '+' : ''}{item.change_pct.toFixed(2)}%
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Add ticker input */}
      <div
        style={{
          padding: '8px',
          borderTop: '1px solid #21262d',
          background: '#0d1117',
        }}
      >
        <div style={{ display: 'flex', gap: '4px' }}>
          <input
            type="text"
            data-testid="add-ticker-input"
            value={addInput}
            onChange={e => { setAddInput(e.target.value.toUpperCase()); setAddError(null) }}
            onKeyDown={handleKeyDown}
            placeholder="Add ticker..."
            maxLength={10}
            style={{
              flex: 1,
              background: '#161b22',
              border: '1px solid #21262d',
              borderRadius: '4px',
              color: '#e6edf3',
              padding: '5px 8px',
              fontSize: '12px',
              fontFamily: 'inherit',
              outline: 'none',
            }}
          />
          <button
            onClick={handleAdd}
            disabled={addLoading || !addInput.trim()}
            style={{
              background: addLoading || !addInput.trim() ? '#21262d' : '#209dd7',
              border: 'none',
              borderRadius: '4px',
              color: '#fff',
              padding: '5px 10px',
              fontSize: '12px',
              fontFamily: 'inherit',
              cursor: addLoading || !addInput.trim() ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              transition: 'background 0.15s',
            }}
          >
            {addLoading ? '...' : '+ADD'}
          </button>
        </div>
        {addError && (
          <div style={{ fontSize: '11px', color: '#f85149', marginTop: '4px' }}>
            {addError}
          </div>
        )}
      </div>
    </div>
  )
}
