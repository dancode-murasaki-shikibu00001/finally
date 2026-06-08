import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TradeBar from '@/components/TradeBar';
import type { PriceUpdate } from '@/types';

const makePriceUpdate = (ticker: string, price: number): PriceUpdate => ({
  ticker,
  price,
  previous_price: price,
  timestamp: Date.now(),
  change: 0,
  change_percent: 0,
  direction: 'flat',
});

const defaultProps = {
  prices: { AAPL: makePriceUpdate('AAPL', 200) },
  cashBalance: 10000,
  selectedTicker: null,
  onTrade: jest.fn().mockResolvedValue(undefined),
};

describe('TradeBar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders buy and sell buttons', () => {
    render(<TradeBar {...defaultProps} />);
    expect(screen.getByRole('button', { name: 'BUY' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'SELL' })).toBeInTheDocument();
  });

  it('pre-fills ticker from selectedTicker prop', () => {
    render(<TradeBar {...defaultProps} selectedTicker="AAPL" />);
    expect(screen.getByPlaceholderText('Ticker')).toHaveValue('AAPL');
  });

  it('calls onTrade with buy when BUY is clicked', async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar {...defaultProps} onTrade={onTrade} selectedTicker="AAPL" />);
    await user.clear(screen.getByPlaceholderText('Qty'));
    await user.type(screen.getByPlaceholderText('Qty'), '5');
    await user.click(screen.getByRole('button', { name: 'BUY' }));
    expect(onTrade).toHaveBeenCalledWith('AAPL', 'buy', 5);
  });

  it('calls onTrade with sell when SELL is clicked', async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar {...defaultProps} onTrade={onTrade} selectedTicker="AAPL" />);
    await user.type(screen.getByPlaceholderText('Qty'), '3');
    await user.click(screen.getByRole('button', { name: 'SELL' }));
    expect(onTrade).toHaveBeenCalledWith('AAPL', 'sell', 3);
  });

  it('shows error message when no ticker or quantity', async () => {
    const user = userEvent.setup();
    render(<TradeBar {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: 'BUY' }));
    await waitFor(() => {
      expect(screen.getByText(/Enter a valid ticker and quantity/i)).toBeInTheDocument();
    });
  });

  it('shows success message after successful trade', async () => {
    const user = userEvent.setup();
    render(<TradeBar {...defaultProps} selectedTicker="AAPL" />);
    await user.type(screen.getByPlaceholderText('Qty'), '5');
    await user.click(screen.getByRole('button', { name: 'BUY' }));
    await waitFor(() => {
      expect(screen.getByText(/BUY 5 AAPL/i)).toBeInTheDocument();
    });
  });

  it('clears quantity after successful trade', async () => {
    const user = userEvent.setup();
    render(<TradeBar {...defaultProps} selectedTicker="AAPL" />);
    const qtyInput = screen.getByPlaceholderText('Qty');
    await user.type(qtyInput, '5');
    await user.click(screen.getByRole('button', { name: 'BUY' }));
    await waitFor(() => {
      expect(qtyInput).toHaveValue(null);
    });
  });

  it('shows error message when onTrade throws', async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockRejectedValue(new Error('Insufficient funds'));
    render(<TradeBar {...defaultProps} onTrade={onTrade} selectedTicker="AAPL" />);
    await user.type(screen.getByPlaceholderText('Qty'), '1');
    await user.click(screen.getByRole('button', { name: 'BUY' }));
    await waitFor(() => {
      expect(screen.getByText('Insufficient funds')).toBeInTheDocument();
    });
  });

  it('displays cash balance', () => {
    render(<TradeBar {...defaultProps} cashBalance={7500.5} />);
    expect(screen.getByText(/Cash: \$7,500\.50/)).toBeInTheDocument();
  });

  it('normalizes ticker to uppercase', async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar {...defaultProps} onTrade={onTrade} />);
    await user.type(screen.getByPlaceholderText('Ticker'), 'aapl');
    await user.type(screen.getByPlaceholderText('Qty'), '1');
    await user.click(screen.getByRole('button', { name: 'BUY' }));
    expect(onTrade).toHaveBeenCalledWith('AAPL', 'buy', 1);
  });
});
