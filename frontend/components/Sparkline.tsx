'use client'

interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
}

export default function Sparkline({ data, width = 80, height = 28, color }: SparklineProps) {
  if (!data || data.length < 2) {
    return (
      <svg width={width} height={height} style={{ display: 'block' }}>
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="#21262d"
          strokeWidth={1}
        />
      </svg>
    )
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const pad = 2
  const usableH = height - pad * 2
  const usableW = width - pad * 2

  const points = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * usableW
    const y = pad + (1 - (v - min) / range) * usableH
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const firstVal = data[0]
  const lastVal = data[data.length - 1]
  const lineColor = color ?? (lastVal >= firstVal ? '#3fb950' : '#f85149')

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={lineColor}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
