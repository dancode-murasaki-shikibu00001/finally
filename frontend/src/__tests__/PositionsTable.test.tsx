import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PositionsTable from '@/components/PositionsTable';
import type { Position } from '@/types';

const makePosition = (overrides: Partial<Position> = {}): Position => ({
  ticker: 'AAPL',
  quantity: 10,
  avg_cost: 200.0,
  current_price: 210.0,
  unrealized_pnl: 100.0,
  unrealized_pnl_pct: 5.0,
  ...overrides,
});

describe('PositionsTable', () => {
  it('shows empty state when no positions', () => {
    render(<PositionsTable positions={[]} />);
    expect(screen.getByText('No open positions')).toBeInTheDocument();
  });

  it('renders a position row', () => {
    render(<PositionsTable positions={[makePosition()]} />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
  });

  it('displays quantity', () => {
    render(<PositionsTable positions={[makePosition({ quantity: 5 })]} />);
    expect(screen.getByText('5.0000')).toBeInTheDocument();
  });

  it('displays avg cost', () => {
    render(<PositionsTable positions={[makePosition({ avg_cost: 200.0 })]} />);
    expect(screen.getByText('$200.00')).toBeInTheDocument();
  });

  it('displays current price', () => {
    render(<PositionsTable positions={[makePosition({ current_price: 210.0 })]} />);
    expect(screen.getByText('$210.00')).toBeInTheDocument();
  });

  it('shows dash when current price is null', () => {
    render(<PositionsTable positions={[makePosition({ current_price: null })]} />);
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('displays positive P&L with plus sign', () => {
    render(<PositionsTable positions={[makePosition({ unrealized_pnl: 100.0, unrealized_pnl_pct: 5.0 })]} />);
    expect(screen.getByText('+$100.00')).toBeInTheDocument();
    expect(screen.getByText('+5.00%')).toBeInTheDocument();
  });

  it('displays negative P&L as absolute value in red', () => {
    render(<PositionsTable positions={[makePosition({ unrealized_pnl: -50.0, unrealized_pnl_pct: -2.5 })]} />);
    // Component shows absolute value; red color applied via style prop
    expect(screen.getByText('$50.00')).toBeInTheDocument();
    expect(screen.getByText('2.50%')).toBeInTheDocument();
  });

  it('shows position count in header', () => {
    const positions = [makePosition({ ticker: 'AAPL' }), makePosition({ ticker: 'GOOGL' })];
    render(<PositionsTable positions={positions} />);
    expect(screen.getByText('Positions (2)')).toBeInTheDocument();
  });

  it('filters out zero-quantity positions', () => {
    const positions = [
      makePosition({ ticker: 'AAPL', quantity: 0 }),
      makePosition({ ticker: 'GOOGL', quantity: 5 }),
    ];
    render(<PositionsTable positions={positions} />);
    expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
    expect(screen.getByText('GOOGL')).toBeInTheDocument();
  });

  it('calls onSelect when row is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    render(<PositionsTable positions={[makePosition()]} onSelect={onSelect} />);
    await user.click(screen.getByText('AAPL'));
    expect(onSelect).toHaveBeenCalledWith('AAPL');
  });
});
