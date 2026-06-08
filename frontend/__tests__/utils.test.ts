/**
 * Unit tests for pure calculation functions used in the FinAlly frontend.
 */

// ─────────────────────────────────────────────
// P&L Calculation
// ─────────────────────────────────────────────

function calculateUnrealizedPnL(
  quantity: number,
  avgCost: number,
  currentPrice: number
): { pnl: number; pnlPct: number } {
  const pnl = (currentPrice - avgCost) * quantity
  const pnlPct = ((currentPrice - avgCost) / avgCost) * 100
  return { pnl, pnlPct }
}

describe('calculateUnrealizedPnL', () => {
  test('calculates profit correctly', () => {
    const { pnl, pnlPct } = calculateUnrealizedPnL(10, 100, 110)
    expect(pnl).toBeCloseTo(100)
    expect(pnlPct).toBeCloseTo(10)
  })

  test('calculates loss correctly', () => {
    const { pnl, pnlPct } = calculateUnrealizedPnL(10, 100, 90)
    expect(pnl).toBeCloseTo(-100)
    expect(pnlPct).toBeCloseTo(-10)
  })

  test('returns zero when price equals cost', () => {
    const { pnl, pnlPct } = calculateUnrealizedPnL(5, 150, 150)
    expect(pnl).toBe(0)
    expect(pnlPct).toBe(0)
  })

  test('handles fractional shares', () => {
    const { pnl } = calculateUnrealizedPnL(0.5, 200, 220)
    expect(pnl).toBeCloseTo(10)
  })

  test('handles high-value stock', () => {
    const { pnl, pnlPct } = calculateUnrealizedPnL(2, 3000, 3300)
    expect(pnl).toBeCloseTo(600)
    expect(pnlPct).toBeCloseTo(10)
  })
})

// ─────────────────────────────────────────────
// Price Direction Logic
// ─────────────────────────────────────────────

function getPriceDirection(
  price: number,
  prevPrice: number
): 'up' | 'down' | 'unchanged' {
  if (price > prevPrice) return 'up'
  if (price < prevPrice) return 'down'
  return 'unchanged'
}

describe('getPriceDirection', () => {
  test('detects uptick', () => {
    expect(getPriceDirection(101, 100)).toBe('up')
  })

  test('detects downtick', () => {
    expect(getPriceDirection(99, 100)).toBe('down')
  })

  test('detects unchanged price', () => {
    expect(getPriceDirection(100, 100)).toBe('unchanged')
  })

  test('handles very small differences', () => {
    expect(getPriceDirection(100.001, 100)).toBe('up')
    expect(getPriceDirection(99.999, 100)).toBe('down')
  })
})

// ─────────────────────────────────────────────
// Sparkline Normalization
// ─────────────────────────────────────────────

function normalizeSparkline(
  data: number[],
  targetMin: number,
  targetMax: number
): number[] {
  if (data.length === 0) return []
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min

  if (range === 0) {
    // All values are the same — map to midpoint
    const mid = (targetMin + targetMax) / 2
    return data.map(() => mid)
  }

  return data.map(v => targetMin + ((v - min) / range) * (targetMax - targetMin))
}

describe('normalizeSparkline', () => {
  test('normalizes data to target range', () => {
    const result = normalizeSparkline([0, 50, 100], 0, 1)
    expect(result[0]).toBeCloseTo(0)
    expect(result[1]).toBeCloseTo(0.5)
    expect(result[2]).toBeCloseTo(1)
  })

  test('handles flat data (all same values)', () => {
    const result = normalizeSparkline([42, 42, 42], 0, 10)
    expect(result.every(v => v === 5)).toBe(true)
  })

  test('returns empty array for empty input', () => {
    expect(normalizeSparkline([], 0, 1)).toEqual([])
  })

  test('maps to pixel range correctly', () => {
    const result = normalizeSparkline([100, 110, 105], 0, 28)
    expect(result[0]).toBe(0)    // min → 0
    expect(result[1]).toBe(28)   // max → 28
    expect(result[2]).toBeCloseTo(14) // midpoint
  })

  test('preserves order of values', () => {
    const input = [10, 5, 8, 3, 9]
    const result = normalizeSparkline(input, 0, 100)
    for (let i = 1; i < input.length; i++) {
      if (input[i] > input[i - 1]) {
        expect(result[i]).toBeGreaterThan(result[i - 1])
      } else if (input[i] < input[i - 1]) {
        expect(result[i]).toBeLessThan(result[i - 1])
      }
    }
  })
})

// ─────────────────────────────────────────────
// Currency Formatting
// ─────────────────────────────────────────────

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

describe('formatCurrency', () => {
  test('formats positive dollar value', () => {
    expect(formatCurrency(10000)).toBe('$10,000.00')
  })

  test('formats negative dollar value', () => {
    expect(formatCurrency(-500.5)).toBe('-$500.50')
  })

  test('formats value with decimal places', () => {
    expect(formatCurrency(185.67)).toBe('$185.67')
  })
})

describe('formatPnL', () => {
  test('adds plus sign for positive values', () => {
    expect(formatPnL(250.00)).toBe('+$250.00')
  })

  test('shows minus sign for negative values without double sign', () => {
    expect(formatPnL(-100.50)).toBe('-$100.50')
  })

  test('adds plus sign for zero', () => {
    expect(formatPnL(0)).toBe('+$0.00')
  })
})

// ─────────────────────────────────────────────
// Portfolio Weight Calculation
// ─────────────────────────────────────────────

interface SimplePosition {
  ticker: string
  quantity: number
  current_price: number
}

function calculatePortfolioWeights(
  positions: SimplePosition[],
  cashBalance: number
): Record<string, number> {
  const positionValues = positions.map(p => p.quantity * p.current_price)
  const totalValue = positionValues.reduce((sum, v) => sum + v, 0) + cashBalance

  if (totalValue === 0) return {}

  const weights: Record<string, number> = {}
  positions.forEach((p, i) => {
    weights[p.ticker] = positionValues[i] / totalValue
  })
  weights['CASH'] = cashBalance / totalValue

  return weights
}

describe('calculatePortfolioWeights', () => {
  test('weights sum to 1', () => {
    const positions = [
      { ticker: 'AAPL', quantity: 10, current_price: 190 },
      { ticker: 'TSLA', quantity: 5, current_price: 200 },
    ]
    const weights = calculatePortfolioWeights(positions, 500)
    const total = Object.values(weights).reduce((s, w) => s + w, 0)
    expect(total).toBeCloseTo(1)
  })

  test('cash-only portfolio gives 100% to cash', () => {
    const weights = calculatePortfolioWeights([], 10000)
    expect(weights['CASH']).toBeCloseTo(1)
  })

  test('handles equal-weight positions', () => {
    const positions = [
      { ticker: 'A', quantity: 1, current_price: 100 },
      { ticker: 'B', quantity: 1, current_price: 100 },
    ]
    const weights = calculatePortfolioWeights(positions, 0)
    expect(weights['A']).toBeCloseTo(0.5)
    expect(weights['B']).toBeCloseTo(0.5)
  })

  test('returns empty object for zero total value', () => {
    const weights = calculatePortfolioWeights([], 0)
    expect(Object.keys(weights).length).toBe(0)
  })
})
