'use client'

import { useEffect, useRef, useState } from 'react'
import type { PriceUpdate } from '../types'

interface MainChartProps {
  selectedTicker: string | null
  priceHistory: Record<string, number[]>
  priceData: Record<string, PriceUpdate>
}

interface ChartAPI {
  chart: {
    applyOptions: (opts: Record<string, unknown>) => void
    timeScale: () => { fitContent: () => void; scrollToRealTime: () => void }
    resize: (w: number, h: number) => void
    remove: () => void
  }
  series: {
    setData: (data: Array<{ time: number; value: number }>) => void
    update: (point: { time: number; value: number }) => void
    applyOptions: (opts: Record<string, unknown>) => void
  }
}

export default function MainChart({ selectedTicker, priceHistory, priceData }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartApiRef = useRef<ChartAPI | null>(null)
  const lastTickerRef = useRef<string | null>(null)
  const [chartError, setChartError] = useState<string | null>(null)
  const [chartReady, setChartReady] = useState(false)

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return

    let chart: ChartAPI | null = null

    const initChart = async () => {
      try {
        const lwc = await import('lightweight-charts')
        const { createChart, ColorType, LineStyle } = lwc

        if (!containerRef.current) return

        const c = createChart(containerRef.current, {
          layout: {
            background: { type: ColorType.Solid, color: '#0d1117' },
            textColor: '#8b949e',
            fontFamily: 'ui-monospace, monospace',
            fontSize: 11,
          },
          grid: {
            vertLines: { color: '#21262d', style: LineStyle.Dotted },
            horzLines: { color: '#21262d', style: LineStyle.Dotted },
          },
          crosshair: {
            vertLine: { color: '#8b949e', width: 1, style: LineStyle.Dashed },
            horzLine: { color: '#8b949e', width: 1, style: LineStyle.Dashed },
          },
          rightPriceScale: {
            borderColor: '#21262d',
            textColor: '#8b949e',
          },
          timeScale: {
            borderColor: '#21262d',
            timeVisible: true,
            secondsVisible: false,
          },
          handleScroll: true,
          handleScale: true,
        })

        const lineSeries = c.addLineSeries({
          color: '#209dd7',
          lineWidth: 2,
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 4,
          crosshairMarkerBorderColor: '#209dd7',
          crosshairMarkerBackgroundColor: '#0d1117',
          priceLineVisible: false,
          lastValueVisible: true,
        })

        chart = {
          chart: c as unknown as ChartAPI['chart'],
          series: lineSeries as unknown as ChartAPI['series'],
        }
        chartApiRef.current = chart
        setChartReady(true)

        // Resize observer
        const ro = new ResizeObserver(entries => {
          for (const entry of entries) {
            const { width, height } = entry.contentRect
            if (chartApiRef.current) {
              chartApiRef.current.chart.resize(width, height)
            }
          }
        })
        ro.observe(containerRef.current)

        return () => {
          ro.disconnect()
          c.remove()
          chartApiRef.current = null
        }
      } catch (err) {
        setChartError('Failed to load chart library')
        console.error(err)
        return () => {}
      }
    }

    let cleanup: (() => void) | undefined
    initChart().then(fn => { cleanup = fn })

    return () => {
      cleanup?.()
    }
  }, [])

  // Update chart data when ticker changes or history grows
  useEffect(() => {
    if (!chartApiRef.current || !selectedTicker || !chartReady) return

    const history = priceHistory[selectedTicker]
    if (!history || history.length === 0) return

    // Build time series: use current time and work backwards
    const now = Math.floor(Date.now() / 1000)
    const intervalSeconds = 1 // ~1s between SSE updates

    const data = history.map((price, i) => ({
      time: now - (history.length - 1 - i) * intervalSeconds,
      value: price,
    }))

    // Deduplicate by time (lightweight-charts requires strictly increasing)
    const seen = new Set<number>()
    const deduped: Array<{ time: number; value: number }> = []
    for (const point of data) {
      if (!seen.has(point.time)) {
        seen.add(point.time)
        deduped.push(point)
      }
    }

    if (deduped.length === 0) return

    if (lastTickerRef.current !== selectedTicker) {
      // Ticker changed: replace entire dataset
      chartApiRef.current.series.setData(deduped)
      chartApiRef.current.chart.timeScale().fitContent()
      lastTickerRef.current = selectedTicker

      // Set color based on trend
      const firstPrice = deduped[0].value
      const lastPrice = deduped[deduped.length - 1].value
      chartApiRef.current.series.applyOptions({
        color: lastPrice >= firstPrice ? '#3fb950' : '#f85149',
      })
    } else {
      // Same ticker: just update last point
      const lastPoint = deduped[deduped.length - 1]
      try {
        chartApiRef.current.series.update(lastPoint)
        chartApiRef.current.chart.timeScale().scrollToRealTime()
      } catch {
        // If update fails (e.g., time going backwards), reset data
        chartApiRef.current.series.setData(deduped)
      }
    }
  }, [selectedTicker, priceHistory, chartReady])

  const currentPrice = selectedTicker ? priceData[selectedTicker] : null

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#0d1117',
        position: 'relative',
      }}
    >
      {/* Chart header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          borderBottom: '1px solid #21262d',
          background: '#161b22',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '14px', fontWeight: 700, color: '#ecad0a', letterSpacing: '0.05em' }}>
            {selectedTicker ?? '—'}
          </span>
          {currentPrice && (
            <>
              <span style={{ fontSize: '18px', fontWeight: 700, color: '#e6edf3' }}>
                ${currentPrice.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: currentPrice.direction === 'up' ? '#3fb950' : currentPrice.direction === 'down' ? '#f85149' : '#8b949e',
                }}
              >
                {currentPrice.change_pct >= 0 ? '+' : ''}{currentPrice.change_pct.toFixed(2)}%
              </span>
            </>
          )}
        </div>
        <div style={{ fontSize: '10px', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Session Chart · Live
        </div>
      </div>

      {/* Chart body */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {!selectedTicker ? (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#8b949e',
              gap: '8px',
            }}
          >
            <div style={{ fontSize: '32px', opacity: 0.3 }}>📈</div>
            <div style={{ fontSize: '13px' }}>Select a ticker from the watchlist</div>
          </div>
        ) : chartError ? (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#f85149',
              fontSize: '12px',
            }}
          >
            {chartError}
          </div>
        ) : null}
        <div
          ref={containerRef}
          style={{
            width: '100%',
            height: '100%',
            opacity: selectedTicker ? 1 : 0,
          }}
        />
      </div>
    </div>
  )
}
