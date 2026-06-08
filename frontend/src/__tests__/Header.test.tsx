import React from 'react';
import { render, screen } from '@testing-library/react';
import Header from '@/components/Header';

describe('Header', () => {
  const defaults = {
    totalValue: 10000,
    cashBalance: 10000,
    status: 'connected' as const,
  };

  it('renders the app name', () => {
    render(<Header {...defaults} />);
    expect(screen.getByText('FIN')).toBeInTheDocument();
    expect(screen.getByText('ALLY')).toBeInTheDocument();
  });

  it('displays portfolio total value', () => {
    render(<Header {...defaults} totalValue={12345.67} />);
    expect(screen.getByText('$12,345.67')).toBeInTheDocument();
  });

  it('displays cash balance', () => {
    render(<Header {...defaults} cashBalance={8500.00} />);
    expect(screen.getByText('$8,500.00')).toBeInTheDocument();
  });

  it('shows LIVE indicator when connected', () => {
    render(<Header {...defaults} status="connected" />);
    expect(screen.getByText('LIVE')).toBeInTheDocument();
  });

  it('shows RECONNECTING indicator when reconnecting', () => {
    render(<Header {...defaults} status="reconnecting" />);
    expect(screen.getByText('RECONNECTING')).toBeInTheDocument();
  });

  it('shows DISCONNECTED indicator when disconnected', () => {
    render(<Header {...defaults} status="disconnected" />);
    expect(screen.getByText('DISCONNECTED')).toBeInTheDocument();
  });

  it('renders the section labels', () => {
    render(<Header {...defaults} />);
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getByText('Cash')).toBeInTheDocument();
  });
});
