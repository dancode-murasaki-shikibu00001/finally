'use client'

import { useState, useCallback } from 'react'
import { useSSE } from '../hooks/useSSE'
import { usePortfolio } from '../hooks/usePortfolio'
import { useWatchlist } from '../hooks/useWatchlist'
import Header from '../components/Header'
import Watchlist from '../components/Watchlist'
import MainChart from '../components/MainChart'
import TradeBar from '../components/TradeBar'
import PortfolioHeatmap from '../components/PortfolioHeatmap'
import PnLChart from '../components/PnLChart'
import PositionsTable from '../components/PositionsTable'
import ChatPanel from '../components/ChatPanel'

type BottomTab = 'heatmap' | 'pnl' | 'positions'

export default function TradingDashboard() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)
  const [bottomTab, setBottomTab] = useState<BottomTab>('positions')

  const { prices, priceHistory, flashState, connectionStatus } = useSSE()
  const { portfolio, history, refetch: refetchPortfolio } = usePortfolio()
  const {
    watchlist,
    loading: watchlistLoading,
    addTicker,
    removeTicker,
    refetch: refetchWatchlist,
  } = useWatchlist(prices)

  const handleActionComplete = useCallback(async () => {
    await Promise.all([refetchPortfolio(), refetchWatchlist()])
  }, [refetchPortfolio, refetchWatchlist])

  const currentPrice = selectedTicker && prices[selectedTicker]
    ? prices[selectedTicker].price
    : null

  const tabs: { id: BottomTab; label: string }[] = [
    { id: 'positions', label: 'POSITIONS' },
    { id: 'heatmap', label: 'HEATMAP' },
    { id: 'pnl', label: 'P&L CHART' },
  ]

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        background: '#0d1117',
      }}
    >
      {/* Header */}
      <Header portfolio={portfolio} connectionStatus={connectionStatus} />

      {/* Main layout */}
      <div
        style={{
          display: 'flex',
          flex: 1,
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        {/* Left: Watchlist panel */}
        <div
          style={{
            width: '320px',
            minWidth: '260px',
            flexShrink: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Watchlist
            watchlist={watchlist}
            flashState={flashState}
            priceHistory={priceHistory}
            selectedTicker={selectedTicker}
            onSelectTicker={setSelectedTicker}
            onAddTicker={addTicker}
            onRemoveTicker={removeTicker}
            loading={watchlistLoading}
          />
        </div>

        {/* Center: main chart + trade bar + bottom panels */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
            overflow: 'hidden',
            borderRight: '1px solid #21262d',
          }}
        >
          {/* Chart area — takes top half */}
          <div
            style={{
              flex: '0 0 55%',
              minHeight: 0,
              borderBottom: '1px solid #21262d',
            }}
          >
            <MainChart
              selectedTicker={selectedTicker}
              priceHistory={priceHistory}
              priceData={prices}
            />
          </div>

          {/* Trade bar */}
          <TradeBar
            selectedTicker={selectedTicker}
            currentPrice={currentPrice}
            cashBalance={portfolio?.cash_balance ?? 10000}
            onTradeComplete={refetchPortfolio}
          />

          {/* Bottom panel tabs */}
          <div
            style={{
              flex: '0 0 45%',
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Tab bar */}
            <div
              style={{
                display: 'flex',
                borderBottom: '1px solid #21262d',
                background: '#161b22',
                flexShrink: 0,
              }}
            >
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setBottomTab(tab.id)}
                  style={{
                    padding: '6px 16px',
                    background: bottomTab === tab.id ? '#0d1117' : 'transparent',
                    border: 'none',
                    borderBottom: bottomTab === tab.id ? '2px solid #209dd7' : '2px solid transparent',
                    color: bottomTab === tab.id ? '#e6edf3' : '#8b949e',
                    fontSize: '10px',
                    fontFamily: 'inherit',
                    fontWeight: 700,
                    cursor: 'pointer',
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    transition: 'all 0.15s',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
              {bottomTab === 'positions' && (
                <PositionsTable positions={portfolio?.positions ?? []} />
              )}
              {bottomTab === 'heatmap' && (
                <PortfolioHeatmap
                  positions={portfolio?.positions ?? []}
                  totalValue={portfolio?.total_value ?? 10000}
                />
              )}
              {bottomTab === 'pnl' && (
                <PnLChart history={history} />
              )}
            </div>
          </div>
        </div>

        {/* Right: Chat panel */}
        <div
          style={{
            width: '340px',
            minWidth: '280px',
            flexShrink: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <ChatPanel onActionComplete={handleActionComplete} />
        </div>
      </div>
    </div>
  )
}
