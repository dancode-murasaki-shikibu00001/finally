'use client';

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import type { SnapshotItem } from '@/types';

interface PnLChartProps {
  snapshots: SnapshotItem[];
}

interface TooltipPayloadItem {
  value: number;
  payload: { total_value: number; recorded_at: string };
}

interface TooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return iso;
  }
}

function fmt(n: number) {
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function CustomTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const v = payload[0].value;
  const t = payload[0].payload.recorded_at;
  return (
    <div className="bg-bg-tertiary border border-border rounded px-2 py-1 text-xs font-mono">
      <div className="text-text-secondary">{formatTime(t)}</div>
      <div className="text-accent-blue font-semibold">{fmt(v)}</div>
    </div>
  );
}

export default function PnLChart({ snapshots }: PnLChartProps) {
  const data = snapshots.map((s) => ({
    total_value: s.total_value,
    recorded_at: s.recorded_at,
  }));

  const baseline = 10000;
  const hasData = data.length > 0;
  const current = hasData ? data[data.length - 1].total_value : baseline;
  const pnl = current - baseline;
  const pnlColor = pnl >= 0 ? '#3fb950' : '#f85149';

  return (
    <div className="flex flex-col h-full bg-bg-secondary">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border shrink-0">
        <span className="text-text-secondary text-xs uppercase tracking-wider">P&amp;L Chart</span>
        {hasData && (
          <span className="text-xs font-mono font-semibold" style={{ color: pnlColor }}>
            {pnl >= 0 ? '+' : ''}{fmt(pnl)}
          </span>
        )}
      </div>
      <div className="flex-1 min-h-0">
        {!hasData ? (
          <div className="flex items-center justify-center h-full text-text-muted text-xs">
            No data yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
              <XAxis
                dataKey="recorded_at"
                tickFormatter={formatTime}
                tick={{ fill: '#7d8590', fontSize: 10, fontFamily: 'monospace' }}
                axisLine={{ stroke: '#30363d' }}
                tickLine={false}
                interval="preserveStartEnd"
                minTickGap={60}
              />
              <YAxis
                domain={['auto', 'auto']}
                tick={{ fill: '#7d8590', fontSize: 10, fontFamily: 'monospace' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
                width={48}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={baseline} stroke="#30363d" strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="total_value"
                stroke="#209dd7"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: '#209dd7', strokeWidth: 0 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
