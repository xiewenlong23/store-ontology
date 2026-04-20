import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Dashboard from '../src/components/Dashboard';

// Mock the api module
vi.mock('../src/api', () => ({
  fetchProducts: vi.fn().mockResolvedValue([
    {
      product_id: 'P001',
      name: '嫩豆腐',
      category: 'daily_fresh',
      expiry_date: '2026-04-21',
      stock: 50,
      in_reduction: false,
    },
  ]),
}));

describe('Dashboard', () => {
  it('renders loading state initially', () => {
    render(<Dashboard />);
    expect(screen.getByText('加载中...')).toBeDefined();
  });
});
