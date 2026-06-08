'use client'

import { useMemo } from 'react'
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts'
import type { Position } from '../types'

interface PortfolioHeatmapProps {
  positions: Position[]
  totalValue: number
}

function pnlToColor(pnlPct: number): string {
  // Clamp to [-10, +10] range for color gradient
  const clamped = Math.max(-10, Math.min(10, pnlPct))
  if (clamped >= 0) {
    // 0% = #1c2128, +10% = #3fb950
    const t = clamped / 10
    const r = Math.round(28 + t * (63 - 28))
    const g = Math.round(33 + t * (185 - 33))
    const b = Math.round(40 + t * (80 - 40))
    return `rgb(${r},${g},${b})`
  } else {
    // 0% = #1c2128, -10% = #f85149
    const t = -clamped / 10
    const r = Math.round(28 + t * (248 - 28))
    const g = Math.round(33 + t * (81 - 33))
    const b = Math.round(40 + t * (73 - 40))
    return `rgb(${r},${g},${b})`
  }
}

interface TreemapNode {
  name: string
  size: number
  pnlPct: number
  pnl: number
  currentPrice: number
}

interface CustomContentProps {
  x?: number
  y?: number
  width?: number
  height?: number
  name?: string
  pnlPct?: number
  pnl?: number
}

function CustomContent(props: CustomContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, name = '', pnlPct = 0, pnl = 0 } = props
  const color = pnlToColor(pnlPct)
  const isPositive = pnl >= 0

  if (width < 30 || height < 20) return null

  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={width - 2}
        height={height - 2}
        style={{
          fill: color,
          stroke: '#0d1117',
          strokeWidth: 2,
        }}
        rx={2}
      />
      {height > 30 && width > 40 && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - (height > 50 ? 8 : 0)}
            textAnchor="middle"
            dominantBaseline="middle"
            style={{
              fontSize: Math.max(10, Math.min(14, width / 5)),
              fontWeight: 700,
              fill: '#e6edf3',
              fontFamily: 'ui-monospace, monospace',
            }}
          >
            {name}
          </text>
          {height > 50 && (
            <text
              x={x + width / 2}
              y={y + height / 2 + 10}
              textAnchor="middle"
              dominantBaseline="middle"
              style={{
                fontSize: Math.max(9, Math.min(12, width / 6)),
                fill: isPositive ? '#3fb950' : '#f85149',
                fontFamily: 'ui-monospace, monospace',
              }}
            >
              {isPositive ? '+' : ''}{pnlPct.toFixed(1)}%
            </text>
          )}
        </>
      )}
    </g>
  )
}

interface TooltipPayloadItem {
  payload?: TreemapNode
}

function HeatmapTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadItem[] }) {
  if (!active || !payload || !payload[0]?.payload) return null
  const data = payload[0].payload
  const isPositive = data.pnl >= 0
  return (
    <div
      style={{
        background: '#161b22',
        border: '1px solid #21262d',
        borderRadius: '4px',
        padding: '8px 12px',
        fontSize: '12px',
        color: '#e6edf3',
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: '4px', color: '#ecad0a' }}>{data.name}</div>
      <div>Price: ${data.currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
      <div style={{ color: isPositive ? '#3fb950' : '#f85149' }}>
        P&amp;L: {isPositive ? '+' : ''}${Math.abs(data.pnl).toFixed(2)} ({isPositive ? '+' : ''}{data.pnlPct.toFixed(2)}%)
      </div>
    </div>
  )
}

export default function PortfolioHeatmap({ positions, totalValue }: PortfolioHeatmapProps) {
  const treeData = useMemo(() => {
    if (!positions || positions.length === 0) return []
    const portfolioTotal = totalValue > 0 ? totalValue : 1

    return positions.map(p => ({
      name: p.ticker,
      size: Math.max(1, (p.current_price * p.quantity) / portfolioTotal * 100),
      pnlPct: p.pnl_pct,
      pnl: p.unrealized_pnl,
      currentPrice: p.current_price,
    }))
  }, [positions, totalValue])

  if (!positions || positions.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          flexDirection: 'column',
          gap: '8px',
          color: '#8b949e',
        }}
      >
        <div style={{ fontSize: '28px', opacity: 0.3 }}>▦</div>
        <div style={{ fontSize: '12px' }}>No positions yet — start trading!</div>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <Treemap
        data={treeData}
        dataKey="size"
        aspectRatio={4 / 3}
        content={<CustomContent />}
      >
        <Tooltip content={<HeatmapTooltip />} />
      </Treemap>
    </ResponsiveContainer>
  )
}
