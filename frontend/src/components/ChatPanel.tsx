'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage, TradeResult, WatchlistChangeResult } from '@/types';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (msg: string) => Promise<void>;
  isOpen: boolean;
  onToggle: () => void;
}

function TradeResultTag({ t }: { t: TradeResult }) {
  const ok = t.status === 'ok';
  return (
    <span
      className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded font-mono"
      style={{ backgroundColor: ok ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)', color: ok ? '#3fb950' : '#f85149' }}
    >
      {ok ? '✓' : '✗'} {t.side?.toUpperCase()} {t.quantity} {t.ticker}
      {ok && t.price ? ` @ $${t.price.toFixed(2)}` : ''}
      {!ok && t.error ? `: ${t.error}` : ''}
    </span>
  );
}

function WatchlistTag({ w }: { w: WatchlistChangeResult }) {
  const ok = w.status === 'ok';
  return (
    <span
      className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded font-mono"
      style={{ backgroundColor: 'rgba(32,157,215,0.15)', color: '#209dd7' }}
    >
      {w.action === 'add' ? '+ ' : '− '}{w.ticker}
    </span>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      <div
        className={`max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? 'bg-accent-purple text-white rounded-br-sm'
            : msg.error
            ? 'bg-bg-tertiary text-price-down border border-price-down/30'
            : 'bg-bg-tertiary text-text-primary rounded-bl-sm'
        }`}
      >
        {msg.pending ? (
          <span className="text-text-muted animate-pulse">Thinking…</span>
        ) : (
          msg.content
        )}
      </div>
      {!isUser && msg.trades && msg.trades.length > 0 && (
        <div className="flex flex-wrap gap-1 max-w-[90%]">
          {msg.trades.map((t, i) => <TradeResultTag key={i} t={t} />)}
        </div>
      )}
      {!isUser && msg.watchlist_changes && msg.watchlist_changes.length > 0 && (
        <div className="flex flex-wrap gap-1 max-w-[90%]">
          {msg.watchlist_changes.map((w, i) => <WatchlistTag key={i} w={w} />)}
        </div>
      )}
    </div>
  );
}

export default function ChatPanel({ messages, onSend, isOpen, onToggle }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);
    try {
      await onSend(text);
    } finally {
      setSending(false);
    }
  }, [input, sending, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div
      className={`flex flex-col bg-bg-secondary border-l border-border transition-all duration-200 ${
        isOpen ? 'w-80' : 'w-10'
      } shrink-0`}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        {isOpen && (
          <div className="flex items-center gap-2">
            <span className="text-accent-yellow text-xs">◈</span>
            <span className="text-text-secondary text-xs uppercase tracking-wider">AI Assistant</span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="text-text-muted hover:text-text-primary text-xs ml-auto"
          title={isOpen ? 'Close chat' : 'Open AI chat'}
        >
          {isOpen ? '›' : '‹'}
        </button>
      </div>

      {isOpen && (
        <>
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3 min-h-0">
            {messages.length === 0 && (
              <div className="text-text-muted text-xs text-center mt-4 leading-relaxed">
                <div className="text-2xl mb-2">◈</div>
                Ask me to analyze your portfolio, suggest trades, or manage your watchlist.
              </div>
            )}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="shrink-0 border-t border-border p-2">
            <div className="flex gap-1">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message FinAlly…"
                disabled={sending}
                rows={2}
                className="flex-1 bg-bg-tertiary border border-border text-text-primary text-xs px-2 py-1.5 rounded outline-none focus:border-accent-blue placeholder:text-text-muted resize-none disabled:opacity-50 font-sans leading-relaxed"
              />
              <button
                onClick={handleSend}
                disabled={sending || !input.trim()}
                className="self-end px-2.5 py-1.5 bg-accent-purple text-white text-xs rounded hover:opacity-80 disabled:opacity-40 font-bold"
              >
                {sending ? '…' : '→'}
              </button>
            </div>
            <div className="text-text-muted text-xs mt-1 text-center">
              Enter to send · Shift+Enter for newline
            </div>
          </div>
        </>
      )}
    </div>
  );
}
