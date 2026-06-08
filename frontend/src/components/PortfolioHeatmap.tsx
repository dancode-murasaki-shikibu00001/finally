'use client';

import { ResponsiveContainer, Treemap, Tooltip } from 'recharts';
import type { Position } from '@/types';

interface PortfolioHeatmapProps {
  positions: Position[];
  onSelect?: (ticker: string) => void;
}

interface HeatmapDataItem {
  name: string;
  size: number;
  pnl_pct: number | null;
  pnl: number | null;
  quantity: number;
  avg_cost: number;
}

interface ContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnl_pct?: number | null;
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: HeatmapDataItem }>;
}

function pnlColor(pct: number | null) {
  if (pct === null) return '#21262d';
  if (pct > 3) return '#238636';
  if (pct > 1) return '#2ea043';
  if (pct > 0) return '#3fb950';
  if (pct === 0) return '#30363d';
  if (pct > -1) return '#f85149';
  if (pct > -3) return '#da3633';
  return '#b91c1c';
}

function CustomContent({ x = 0, y = 0, width = 0, height = 0, name, pnl_pct }: ContentProps) {
  if (!width || !height || width < 10 || height < 10) return null;
  const bg = pnlColor(pnl_pct ?? null);
  const showText = width > 40 && height > 30;

  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={width - 2}
        height={height - 2}
        style={{ fill: bg, stroke: '#161b22', strokeWidth: 2 }}
        rx={2}
      />
      {showText && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - 6}
            textAnchor="middle"
            fill="#e6edf3"
            fontSize={Math.min(14, width / 4)}
            fontWeight="bold"
            fontFamily="monospace"
          >
            {name}
          </text>
          {pnl_pct !== null && pnl_pct !== undefined && (
            <text
              x={x + width / 2}
              y={y + height / 2 + 10}
              textAnchor="middle"
              fill="rgba(230,237,243,0.8)"
              fontSize={Math.min(11, width / 5)}
              fontFamily="monospace"
            >
              {pnl_pct >= 0 ? '+' : ''}{pnl_pct.toFixed(2)}%
            </text>
          )}
        </>
      )}
    </g>
  );
}

function HeatmapTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-mono">
      <div className="text-text-primary font-bold">{d.name}</div>
      <div className="text-text-secondary">{d.quantity} shares @ ${d.avg_cost?.toFixed(2)}</div>
      <div style={{ color: (d.pnl_pct ?? 0) >= 0 ? '#3fb950' : '#f85149' }}>
        {(d.pnl_pct ?? 0) >= 0 ? '+' : ''}{d.pnl_pct?.toFixed(2)}% (${d.pnl?.toFixed(2)})
      </div>
    </div>
  );
}

export default function PortfolioHeatmap({ positions, onSelect }: PortfolioHeatmapProps) {
  const data: HeatmapDataItem[] = positions
    .filter((p) => p.quantity > 0 && p.current_price !== null)
    .map((p) => ({
      name: p.ticker,
      size: (p.current_price ?? p.avg_cost) * p.quantity,
      pnl_pct: p.unrealized_pnl_pct,
      pnl: p.unrealized_pnl,
      quantity: p.quantity,
      avg_cost: p.avg_cost,
    }));

  return (
    <div className="flex flex-col h-full bg-bg-secondary">
      <div className="px-3 py-1.5 border-b border-border shrink-0">
        <span className="text-text-secondary text-xs uppercase tracking-wider">Positions Heatmap</span>
      </div>
      <div className="flex-1 min-h-0 p-1">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-full text-text-muted text-xs">
            No positions
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              aspectRatio={4 / 3}
              content={<CustomContent />}
              isAnimationActive={false}
              onClick={(d) => onSelect?.((d as unknown as HeatmapDataItem).name)}
            >
              <Tooltip content={<HeatmapTooltip />} />
            </Treemap>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
