'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import type { WatchlistItem, PriceUpdate } from '../types'

export function useWatchlist(priceData: Record<string, PriceUpdate>) {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await fetch('/api/watchlist')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: WatchlistItem[] = await res.json()
      if (mountedRef.current) {
        setWatchlist(data)
        setError(null)
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch watchlist')
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    fetchWatchlist()
    return () => {
      mountedRef.current = false
    }
  }, [fetchWatchlist])

  // Enrich watchlist items with live prices from SSE
  const enrichedWatchlist: WatchlistItem[] = watchlist.map(item => {
    const live = priceData[item.ticker]
    if (live) {
      return {
        ...item,
        price: live.price,
        change_pct: live.change_pct,
      }
    }
    return item
  })

  const addTicker = useCallback(async (ticker: string): Promise<{ ok: boolean; error?: string }> => {
    const upperTicker = ticker.toUpperCase().trim()
    if (!upperTicker) return { ok: false, error: 'Ticker cannot be empty' }

    try {
      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: upperTicker }),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        return { ok: false, error: body.detail ?? `HTTP ${res.status}` }
      }

      await fetchWatchlist()
      return { ok: true }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : 'Network error' }
    }
  }, [fetchWatchlist])

  const removeTicker = useCallback(async (ticker: string): Promise<{ ok: boolean; error?: string }> => {
    try {
      const res = await fetch(`/api/watchlist/${encodeURIComponent(ticker)}`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        return { ok: false, error: `HTTP ${res.status}` }
      }

      if (mountedRef.current) {
        setWatchlist(prev => prev.filter(w => w.ticker !== ticker))
      }
      return { ok: true }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : 'Network error' }
    }
  }, [])

  return {
    watchlist: enrichedWatchlist,
    loading,
    error,
    addTicker,
    removeTicker,
    refetch: fetchWatchlist,
  }
}
