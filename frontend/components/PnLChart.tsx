'use client'

import { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { HistoryPoint } from '../types'

interface PnLChartProps {
  history: HistoryPoint[]
}

const STARTING_VALUE = 10000

function formatTime(isoString: string): string {
  try {
    const d = new Date(isoString)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return ''
  }
}

function formatCurrency(value: number): string {
  return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

interface TooltipProps {
  active?: boolean
  payload?: Array<{ value: number; payload: { recorded_at: string } }>
  label?: string
}

function CustomTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload || !payload[0]) return null
  const value = payload[0].value
  const time = payload[0].payload.recorded_at
  const pnl = value - STARTING_VALUE
  const isPositive = pnl >= 0

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
      <div style={{ color: '#8b949e', fontSize: '10px', marginBottom: '4px' }}>
        {formatTime(time)}
      </div>
      <div style={{ fontWeight: 700 }}>{formatCurrency(value)}</div>
      <div style={{ color: isPositive ? '#3fb950' : '#f85149' }}>
        {isPositive ? '+' : ''}{formatCurrency(pnl)}
      </div>
    </div>
  )
}

export default function PnLChart({ history }: PnLChartProps) {
  const data = useMemo(() => {
    if (!history || history.length === 0) return []
    // Sample down if too many points (keep last 200)
    const maxPoints = 200
    const slice = history.length > maxPoints
      ? history.slice(history.length - maxPoints)
      : history
    return slice.map(h => ({
      ...h,
      time: formatTime(h.recorded_at),
      value: h.total_value,
    }))
  }, [history])

  const minVal = data.length > 0 ? Math.min(...data.map(d => d.value)) : STARTING_VALUE - 1000
  const maxVal = data.length > 0 ? Math.max(...data.map(d => d.value)) : STARTING_VALUE + 1000
  const padding = (maxVal - minVal) * 0.1 || 500
  const yMin = Math.floor((minVal - padding) / 100) * 100
  const yMax = Math.ceil((maxVal + padding) / 100) * 100

  const latestValue = data.length > 0 ? data[data.length - 1].value : null
  const lineColor = latestValue != null
    ? (latestValue >= STARTING_VALUE ? '#3fb950' : '#f85149')
    : '#209dd7'

  if (data.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: '#8b949e',
          fontSize: '12px',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        <div style={{ fontSize: '24px', opacity: 0.3 }}>📊</div>
        <div>Waiting for portfolio data...</div>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart
        data={data}
        margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#21262d" vertical={false} />
        <XAxis
          dataKey="time"
          tick={{ fill: '#8b949e', fontSize: 9, fontFamily: 'ui-monospace, monospace' }}
          tickLine={false}
          axisLine={{ stroke: '#21262d' }}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[yMin, yMax]}
          tick={{ fill: '#8b949e', fontSize: 9, fontFamily: 'ui-monospace, monospace' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatCurrency}
          width={70}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          y={STARTING_VALUE}
          stroke="#ecad0a"
          strokeDasharray="4 4"
          strokeWidth={1}
          label={{
            value: '$10,000',
            fill: '#ecad0a',
            fontSize: 9,
            fontFamily: 'ui-monospace, monospace',
            position: 'insideTopRight',
          }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={lineColor}
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, fill: lineColor }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
