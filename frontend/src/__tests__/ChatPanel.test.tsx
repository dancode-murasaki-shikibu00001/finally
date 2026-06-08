import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPanel from '@/components/ChatPanel';
import type { ChatMessage } from '@/types';

const makeMsg = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: '1',
  role: 'assistant',
  content: 'Hello there',
  ...overrides,
});

const defaultProps = {
  messages: [] as ChatMessage[],
  onSend: jest.fn().mockResolvedValue(undefined),
  isOpen: true,
  onToggle: jest.fn(),
};

describe('ChatPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders empty state prompt when no messages', () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByText(/Ask me to analyze/i)).toBeInTheDocument();
  });

  it('renders user messages', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messages={[makeMsg({ role: 'user', content: 'Buy me 5 AAPL' })]}
      />
    );
    expect(screen.getByText('Buy me 5 AAPL')).toBeInTheDocument();
  });

  it('renders assistant messages', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messages={[makeMsg({ role: 'assistant', content: 'Done! Bought 5 AAPL.' })]}
      />
    );
    expect(screen.getByText('Done! Bought 5 AAPL.')).toBeInTheDocument();
  });

  it('shows "Thinking…" for pending messages', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messages={[makeMsg({ role: 'assistant', content: '', pending: true })]}
      />
    );
    expect(screen.getByText('Thinking…')).toBeInTheDocument();
  });

  it('shows trade result tags for executed trades', () => {
    const msg = makeMsg({
      role: 'assistant',
      content: 'Bought AAPL',
      trades: [{ ticker: 'AAPL', side: 'buy', quantity: 5, price: 200, status: 'ok' }],
    });
    render(<ChatPanel {...defaultProps} messages={[msg]} />);
    expect(screen.getByText(/BUY 5 AAPL/)).toBeInTheDocument();
  });

  it('shows error tag for failed trades', () => {
    const msg = makeMsg({
      role: 'assistant',
      content: 'Could not buy',
      trades: [{ ticker: 'AAPL', side: 'buy', quantity: 9999, status: 'error', error: 'Insufficient funds' }],
    });
    render(<ChatPanel {...defaultProps} messages={[msg]} />);
    expect(screen.getByText(/BUY 9999 AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Insufficient funds/)).toBeInTheDocument();
  });

  it('shows watchlist change tags', () => {
    const msg = makeMsg({
      role: 'assistant',
      content: 'Added PYPL',
      watchlist_changes: [{ ticker: 'PYPL', action: 'add', status: 'ok' }],
    });
    render(<ChatPanel {...defaultProps} messages={[msg]} />);
    const matches = screen.getAllByText(/PYPL/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('calls onSend when send button is clicked', async () => {
    const user = userEvent.setup();
    const onSend = jest.fn().mockResolvedValue(undefined);
    render(<ChatPanel {...defaultProps} onSend={onSend} />);
    await user.type(screen.getByRole('textbox'), 'Hello');
    await user.click(screen.getByRole('button', { name: '→' }));
    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  it('calls onSend on Enter key', async () => {
    const user = userEvent.setup();
    const onSend = jest.fn().mockResolvedValue(undefined);
    render(<ChatPanel {...defaultProps} onSend={onSend} />);
    await user.type(screen.getByRole('textbox'), 'Hello{Enter}');
    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  it('does not call onSend when input is empty', async () => {
    const user = userEvent.setup();
    const onSend = jest.fn().mockResolvedValue(undefined);
    render(<ChatPanel {...defaultProps} onSend={onSend} />);
    await user.click(screen.getByRole('button', { name: '→' }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it('clears input after send', async () => {
    const user = userEvent.setup();
    render(<ChatPanel {...defaultProps} />);
    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'test message');
    await user.click(screen.getByRole('button', { name: '→' }));
    expect(textarea).toHaveValue('');
  });

  it('calls onToggle when toggle button is clicked', async () => {
    const user = userEvent.setup();
    const onToggle = jest.fn();
    render(<ChatPanel {...defaultProps} onToggle={onToggle} />);
    await user.click(screen.getByTitle('Close chat'));
    expect(onToggle).toHaveBeenCalled();
  });

  it('shows collapsed state when isOpen is false', () => {
    render(<ChatPanel {...defaultProps} isOpen={false} />);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
