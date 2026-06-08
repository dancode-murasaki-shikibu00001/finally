'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { ChatMessage, TradeAction, WatchlistAction } from '../types'

interface ChatPanelProps {
  onActionComplete: () => void
}

function TradeChip({ trade }: { trade: TradeAction }) {
  const isBuy = trade.side === 'buy'
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: '3px',
        fontSize: '11px',
        fontWeight: 600,
        background: isBuy ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)',
        color: isBuy ? '#3fb950' : '#f85149',
        border: `1px solid ${isBuy ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)'}`,
        margin: '2px 2px 2px 0',
      }}
    >
      {isBuy ? '▲' : '▼'} {isBuy ? 'BOUGHT' : 'SOLD'} {trade.quantity} {trade.ticker}
    </span>
  )
}

function WatchlistChip({ change }: { change: WatchlistAction }) {
  const isAdd = change.action === 'add'
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: '3px',
        fontSize: '11px',
        fontWeight: 600,
        background: 'rgba(32,157,215,0.15)',
        color: '#209dd7',
        border: '1px solid rgba(32,157,215,0.3)',
        margin: '2px 2px 2px 0',
      }}
    >
      {isAdd ? '+' : '−'} {change.ticker} watchlist
    </span>
  )
}

function LoadingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '8px 0' }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: '#209dd7',
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  )
}

export default function ChatPanel({ onActionComplete }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: "Hello! I'm FinAlly, your AI trading assistant. I can analyze your portfolio, suggest trades, and execute them for you. What would you like to do?",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading, scrollToBottom])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: ChatMessage = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `HTTP ${res.status}`)
      }

      const data = await res.json()
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: data.message ?? '',
        trades: data.trades ?? [],
        watchlist_changes: data.watchlist_changes ?? [],
      }

      setMessages(prev => [...prev, assistantMsg])

      // If there were trades or watchlist changes, refresh data
      const hasActions =
        (assistantMsg.trades && assistantMsg.trades.length > 0) ||
        (assistantMsg.watchlist_changes && assistantMsg.watchlist_changes.length > 0)
      if (hasActions) {
        onActionComplete()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response')
      setMessages(prev => prev.slice(0, -1)) // Remove the user message on error
      setInput(text) // Restore input
    } finally {
      setLoading(false)
    }
  }, [input, loading, onActionComplete])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const suggestions = [
    'Analyze my portfolio',
    'Buy 5 AAPL',
    'What should I sell?',
    'Show me my P&L',
  ]

  return (
    <div
      data-testid="chat-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#161b22',
        borderLeft: '1px solid #21262d',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '8px 12px',
          borderBottom: '1px solid #21262d',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#ecad0a', letterSpacing: '0.05em' }}>
            AI ASSISTANT
          </div>
          <div style={{ fontSize: '9px', color: '#8b949e', letterSpacing: '0.06em' }}>
            Powered by Cerebras
          </div>
        </div>
        <div
          style={{
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            background: '#3fb950',
            boxShadow: '0 0 6px #3fb950',
          }}
        />
      </div>

      {/* Messages */}
      <div data-testid="chat-messages" style={{ flex: 1, overflowY: 'auto', padding: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '90%',
                padding: '8px 10px',
                borderRadius: msg.role === 'user' ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                background: msg.role === 'user' ? 'rgba(32,157,215,0.2)' : '#1c2128',
                border: `1px solid ${msg.role === 'user' ? 'rgba(32,157,215,0.3)' : '#21262d'}`,
                fontSize: '12px',
                lineHeight: '1.5',
                color: '#e6edf3',
                wordBreak: 'break-word',
              }}
            >
              {msg.role === 'assistant' && (
                <div style={{ fontSize: '9px', color: '#8b949e', marginBottom: '4px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                  FinAlly
                </div>
              )}
              <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

              {/* Trade chips */}
              {msg.trades && msg.trades.length > 0 && (
                <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '2px' }}>
                  {msg.trades.map((t, ti) => (
                    <TradeChip key={ti} trade={t} />
                  ))}
                </div>
              )}

              {/* Watchlist chips */}
              {msg.watchlist_changes && msg.watchlist_changes.length > 0 && (
                <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '2px' }}>
                  {msg.watchlist_changes.map((wc, wi) => (
                    <WatchlistChip key={wi} change={wc} />
                  ))}
                </div>
              )}
            </div>

            <div
              style={{
                fontSize: '9px',
                color: '#8b949e',
                marginTop: '2px',
                paddingLeft: msg.role === 'user' ? '0' : '4px',
                paddingRight: msg.role === 'user' ? '4px' : '0',
              }}
            >
              {msg.role === 'user' ? 'You' : 'AI'}
            </div>
          </div>
        ))}

        {loading && (
          <div data-testid="chat-loading" style={{ display: 'flex', alignItems: 'flex-start' }}>
            <div
              style={{
                background: '#1c2128',
                border: '1px solid #21262d',
                borderRadius: '8px 8px 8px 2px',
                padding: '8px 10px',
              }}
            >
              <div style={{ fontSize: '9px', color: '#8b949e', marginBottom: '4px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                FinAlly
              </div>
              <LoadingIndicator />
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              fontSize: '11px',
              color: '#f85149',
              padding: '4px 8px',
              background: 'rgba(248,81,73,0.1)',
              border: '1px solid rgba(248,81,73,0.2)',
              borderRadius: '4px',
            }}
          >
            Error: {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && !loading && (
        <div style={{ padding: '4px 8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => { setInput(s); textareaRef.current?.focus() }}
              style={{
                background: '#0d1117',
                border: '1px solid #21262d',
                borderRadius: '12px',
                color: '#8b949e',
                padding: '3px 10px',
                fontSize: '11px',
                fontFamily: 'inherit',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.color = '#e6edf3'
                ;(e.currentTarget as HTMLButtonElement).style.borderColor = '#8b949e'
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.color = '#8b949e'
                ;(e.currentTarget as HTMLButtonElement).style.borderColor = '#21262d'
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <div
        style={{
          padding: '8px',
          borderTop: '1px solid #21262d',
          background: '#0d1117',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: '6px',
            alignItems: 'flex-end',
            background: '#161b22',
            border: '1px solid #21262d',
            borderRadius: '6px',
            padding: '6px',
          }}
        >
          <textarea
            ref={textareaRef}
            data-testid="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything... (Enter to send)"
            rows={2}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: '#e6edf3',
              fontSize: '12px',
              fontFamily: 'inherit',
              resize: 'none',
              outline: 'none',
              lineHeight: '1.4',
            }}
          />
          <button
            data-testid="chat-send"
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            style={{
              background: loading || !input.trim() ? '#21262d' : '#753991',
              border: 'none',
              borderRadius: '4px',
              color: '#fff',
              padding: '6px 12px',
              fontSize: '12px',
              fontFamily: 'inherit',
              fontWeight: 700,
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              transition: 'background 0.15s',
              letterSpacing: '0.04em',
              flexShrink: 0,
              alignSelf: 'flex-end',
            }}
          >
            {loading ? '...' : 'SEND'}
          </button>
        </div>
        <div style={{ fontSize: '9px', color: '#8b949e', marginTop: '4px', textAlign: 'right' }}>
          Shift+Enter for newline · Enter to send
        </div>
      </div>
    </div>
  )
}
