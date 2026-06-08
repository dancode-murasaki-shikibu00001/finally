'use client';

import { useEffect, useRef } from 'react';
import type { IChartApi, ISeriesApi, LineType, UTCTimestamp } from 'lightweight-charts';
import type { PriceUpdate } from '@/types';

interface MainChartProps {
  ticker: string | null;
  priceHistory: Array<{ time: number; value: number }>;
  currentPrice: PriceUpdate | null;
}

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function MainChart({ ticker, priceHistory, currentPrice }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // AreaSeries is a SeriesApi with "Area" type; use the base interface
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cleanupRo: (() => void) | undefined;

    async function init() {
      if (!containerRef.current) return;
      const { createChart, ColorType, LineType: LT } = await import('lightweight-charts');

      chartRef.current = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
        layout: {
          background: { type: ColorType.Solid, color: '#161b22' },
          textColor: '#7d8590',
        },
        grid: {
          vertLines: { color: '#21262d' },
          horzLines: { color: '#21262d' },
        },
        crosshair: {
          vertLine: { color: '#30363d', labelBackgroundColor: '#21262d' },
          horzLine: { color: '#30363d', labelBackgroundColor: '#21262d' },
        },
        rightPriceScale: { borderColor: '#30363d' },
        timeScale: {
          borderColor: '#30363d',
          timeVisible: true,
          secondsVisible: false,
        },
        handleScale: true,
        handleScroll: true,
      });

      seriesRef.current = chartRef.current.addAreaSeries({
        lineColor: '#209dd7',
        topColor: 'rgba(32, 157, 215, 0.2)',
        bottomColor: 'rgba(32, 157, 215, 0.02)',
        lineWidth: 2,
        lineType: LT.Curved as LineType,
        priceLineVisible: true,
        priceLineColor: '#209dd7',
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: '#209dd7',
        crosshairMarkerBackgroundColor: '#161b22',
      });

      if (priceHistory.length > 0) {
        seriesRef.current.setData(
          priceHistory.map((d) => ({ time: d.time as UTCTimestamp, value: d.value }))
        );
        chartRef.current.timeScale().fitContent();
      }

      const ro = new ResizeObserver(() => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
          });
        }
      });
      ro.observe(containerRef.current);
      cleanupRo = () => ro.disconnect();
    }

    init();

    return () => {
      cleanupRo?.();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
    // Intentionally re-init chart when ticker changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  useEffect(() => {
    if (!seriesRef.current || priceHistory.length === 0) return;
    seriesRef.current.setData(
      priceHistory.map((d) => ({ time: d.time as UTCTimestamp, value: d.value }))
    );
    chartRef.current?.timeScale().fitContent();
  }, [priceHistory]);

  if (!ticker) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-bg-secondary text-text-muted">
        <div className="text-4xl mb-3 opacity-30">◈</div>
        <div className="text-sm">Select a ticker from the watchlist</div>
      </div>
    );
  }

  const change = currentPrice?.change ?? 0;
  const changePct = currentPrice?.change_percent ?? 0;
  const price = currentPrice?.price;

  return (
    <div className="flex flex-col h-full bg-bg-secondary">
      <div className="flex items-center gap-4 px-4 py-2 border-b border-border shrink-0">
        <span className="text-text-primary font-bold text-lg tracking-wide">{ticker}</span>
        {price !== undefined && (
          <span className="text-text-primary font-mono text-base">${fmt(price)}</span>
        )}
        {currentPrice && (
          <span
            className="text-sm font-mono"
            style={{ color: change >= 0 ? '#3fb950' : '#f85149' }}
          >
            {change >= 0 ? '+' : ''}{fmt(change)} ({changePct >= 0 ? '+' : ''}{changePct.toFixed(4)}%)
          </span>
        )}
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
