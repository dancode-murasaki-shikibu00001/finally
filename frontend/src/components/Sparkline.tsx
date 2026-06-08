'use client';

interface SparklineProps {
  prices: number[];
  width?: number;
  height?: number;
}

export default function Sparkline({ prices, width = 72, height = 28 }: SparklineProps) {
  if (prices.length < 2) {
    return <svg width={width} height={height} />;
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const pad = 2;

  const points = prices.map((p, i) => ({
    x: pad + (i / (prices.length - 1)) * (width - pad * 2),
    y: pad + (1 - (p - min) / range) * (height - pad * 2),
  }));

  const d = points.map((pt, i) => `${i === 0 ? 'M' : 'L'}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ');
  const isUp = prices[prices.length - 1] >= prices[0];
  const color = isUp ? '#3fb950' : '#f85149';

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
