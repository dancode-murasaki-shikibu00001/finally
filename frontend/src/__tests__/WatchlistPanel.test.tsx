import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WatchlistPanel from '@/components/WatchlistPanel';
import type { WatchlistItem } from '@/types';

const makeItem = (ticker: string): WatchlistItem => ({
  ticker,
  price: 200.0,
  change: 1.0,
  change_percent: 0.5,
  direction: 'up',
  added_at: '2024-01-01T00:00:00Z',
});

const defaultProps = {
  items: [makeItem('AAPL'), makeItem('GOOGL')],
  prices: {},
  sparklines: {},
  selectedTicker: null,
  onSelect: jest.fn(),
  onAdd: jest.fn().mockResolvedValue(undefined),
  onRemove: jest.fn().mockResolvedValue(undefined),
};

describe('WatchlistPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders watchlist items', () => {
    render(<WatchlistPanel {...defaultProps} />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('GOOGL')).toBeInTheDocument();
  });

  it('shows empty state when no items', () => {
    render(<WatchlistPanel {...defaultProps} items={[]} />);
    expect(screen.getByText(/Add tickers to your watchlist/i)).toBeInTheDocument();
  });

  it('calls onSelect when a ticker is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    render(<WatchlistPanel {...defaultProps} onSelect={onSelect} />);
    await user.click(screen.getByText('AAPL'));
    expect(onSelect).toHaveBeenCalledWith('AAPL');
  });

  it('calls onAdd when + button is clicked', async () => {
    const user = userEvent.setup();
    const onAdd = jest.fn().mockResolvedValue(undefined);
    render(<WatchlistPanel {...defaultProps} onAdd={onAdd} />);
    await user.type(screen.getByPlaceholderText('Add ticker…'), 'TSLA');
    await user.click(screen.getByRole('button', { name: '+' }));
    expect(onAdd).toHaveBeenCalledWith('TSLA');
  });

  it('calls onAdd on Enter key in input', async () => {
    const user = userEvent.setup();
    const onAdd = jest.fn().mockResolvedValue(undefined);
    render(<WatchlistPanel {...defaultProps} onAdd={onAdd} />);
    await user.type(screen.getByPlaceholderText('Add ticker…'), 'NVDA{Enter}');
    expect(onAdd).toHaveBeenCalledWith('NVDA');
  });

  it('normalizes input to uppercase', async () => {
    const user = userEvent.setup();
    const onAdd = jest.fn().mockResolvedValue(undefined);
    render(<WatchlistPanel {...defaultProps} onAdd={onAdd} />);
    await user.type(screen.getByPlaceholderText('Add ticker…'), 'tsla{Enter}');
    expect(onAdd).toHaveBeenCalledWith('TSLA');
  });

  it('clears input after successful add', async () => {
    const user = userEvent.setup();
    render(<WatchlistPanel {...defaultProps} />);
    const input = screen.getByPlaceholderText('Add ticker…');
    await user.type(input, 'TSLA{Enter}');
    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });

  it('shows error message when onAdd throws', async () => {
    const user = userEvent.setup();
    const onAdd = jest.fn().mockRejectedValue(new Error('Ticker not found'));
    render(<WatchlistPanel {...defaultProps} onAdd={onAdd} />);
    await user.type(screen.getByPlaceholderText('Add ticker…'), 'ZZZZ{Enter}');
    await waitFor(() => {
      expect(screen.getByText('Ticker not found')).toBeInTheDocument();
    });
  });

  it('displays change percent with sign', () => {
    render(<WatchlistPanel {...defaultProps} />);
    expect(screen.getAllByText('+0.50%').length).toBeGreaterThan(0);
  });

  it('highlights selected ticker', () => {
    render(<WatchlistPanel {...defaultProps} selectedTicker="AAPL" />);
    // Selected row has border-l-accent-blue class
    const rows = document.querySelectorAll('[class*="border-l-accent-blue"]');
    expect(rows.length).toBe(1);
  });

  it('does not add when input is empty', async () => {
    const user = userEvent.setup();
    const onAdd = jest.fn().mockResolvedValue(undefined);
    render(<WatchlistPanel {...defaultProps} onAdd={onAdd} />);
    await user.click(screen.getByRole('button', { name: '+' }));
    expect(onAdd).not.toHaveBeenCalled();
  });
});
