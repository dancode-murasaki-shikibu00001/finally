'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import type { PriceUpdate, ConnectionStatus } from '../types'

const MAX_HISTORY_POINTS = 60
const FLASH_DURATION_MS = 600
const RECONNECT_DELAY_MS = 3000

export function useSSE() {
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({})
  const [priceHistory, setPriceHistory] = useState<Record<string, number[]>>({})
  const [flashState, setFlashState] = useState<Record<string, 'up' | 'down' | null>>({})
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')

  const esRef = useRef<EventSource | null>(null)
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const clearFlash = useCallback((ticker: string) => {
    if (flashTimers.current[ticker]) {
      clearTimeout(flashTimers.current[ticker])
    }
    flashTimers.current[ticker] = setTimeout(() => {
      if (mountedRef.current) {
        setFlashState(prev => ({ ...prev, [ticker]: null }))
      }
    }, FLASH_DURATION_MS)
  }, [])

  const connect = useCallback(() => {
    if (typeof window === 'undefined') return
    if (esRef.current) {
      esRef.current.close()
    }

    setConnectionStatus('connecting')
    const es = new EventSource('/api/stream/prices')
    esRef.current = es

    es.onopen = () => {
      if (mountedRef.current) {
        setConnectionStatus('connected')
      }
    }

    es.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return
      try {
        const update: PriceUpdate = JSON.parse(event.data)
        const ticker = update.ticker

        setPrices(prev => ({ ...prev, [ticker]: update }))

        setPriceHistory(prev => {
          const existing = prev[ticker] ?? []
          const updated = [...existing, update.price]
          return {
            ...prev,
            [ticker]: updated.length > MAX_HISTORY_POINTS
              ? updated.slice(updated.length - MAX_HISTORY_POINTS)
              : updated,
          }
        })

        if (update.direction !== 'unchanged') {
          setFlashState(prev => ({ ...prev, [ticker]: update.direction as 'up' | 'down' }))
          clearFlash(ticker)
        }
      } catch {
        // malformed event, ignore
      }
    }

    es.onerror = () => {
      if (!mountedRef.current) return
      setConnectionStatus('disconnected')
      es.close()
      esRef.current = null

      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
      }
      reconnectTimer.current = setTimeout(() => {
        if (mountedRef.current) {
          connect()
        }
      }, RECONNECT_DELAY_MS)
    }
  }, [clearFlash])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
      }
      Object.values(flashTimers.current).forEach(t => clearTimeout(t))
    }
  }, [connect])

  return { prices, priceHistory, flashState, connectionStatus }
}
