'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import type { Portfolio, HistoryPoint } from '../types'

const POLL_INTERVAL_MS = 5000

export function usePortfolio() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: Portfolio = await res.json()
      if (mountedRef.current) {
        setPortfolio(data)
        setError(null)
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch portfolio')
      }
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio/history')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: HistoryPoint[] = await res.json()
      if (mountedRef.current) {
        setHistory(data)
      }
    } catch {
      // non-critical, don't set error
    }
  }, [])

  const refetch = useCallback(async () => {
    await Promise.all([fetchPortfolio(), fetchHistory()])
  }, [fetchPortfolio, fetchHistory])

  const schedulePoll = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current)
    }
    pollTimerRef.current = setTimeout(async () => {
      if (mountedRef.current) {
        await refetch()
        schedulePoll()
      }
    }, POLL_INTERVAL_MS)
  }, [refetch])

  useEffect(() => {
    mountedRef.current = true

    const init = async () => {
      setLoading(true)
      await refetch()
      if (mountedRef.current) {
        setLoading(false)
        schedulePoll()
      }
    }

    init()

    return () => {
      mountedRef.current = false
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current)
      }
    }
  }, [refetch, schedulePoll])

  return { portfolio, history, loading, error, refetch }
}
