'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import type { PriceUpdate, ConnectionStatus } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';
const SPARKLINE_MAX_POINTS = 60;

export function usePriceStream() {
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({});
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({});
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }

    setStatus('reconnecting');
    const es = new EventSource(`${API_BASE}/api/stream/prices`);
    esRef.current = es;

    es.onopen = () => {
      setStatus('connected');
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as Record<string, PriceUpdate>;
        setPrices((prev) => ({ ...prev, ...payload }));
        setSparklines((prev) => {
          const next = { ...prev };
          for (const [ticker, update] of Object.entries(payload)) {
            const history = prev[ticker] || [];
            const trimmed = history.length >= SPARKLINE_MAX_POINTS
              ? history.slice(-(SPARKLINE_MAX_POINTS - 1))
              : history;
            next[ticker] = [...trimmed, update.price];
          }
          return next;
        });
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setStatus('reconnecting');
      es.close();
      esRef.current = null;
      reconnectTimer.current = setTimeout(connect, 2000);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  return { prices, sparklines, status };
}
