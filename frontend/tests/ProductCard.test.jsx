import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProductCard from '../src/components/ProductCard';

describe('ProductCard', () => {
  it('renders product name and stock', () => {
    const product = {
      product_id: 'P001',
      name: '嫩豆腐',
      category: 'daily_fresh',
      expiry_date: '2026-04-25',
      stock: 50,
      in_reduction: false,
    };

    render(<ProductCard product={product} />);
    expect(screen.getByText('嫩豆腐')).toBeDefined();
    expect(screen.getByText('库存: 50')).toBeDefined();
  });

  it('shows green status for products with >3 days left', () => {
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 10);
    const product = {
      product_id: 'P001',
      name: '测试商品',
      category: 'beverage',
      expiry_date: futureDate.toISOString().split('T')[0],
      stock: 100,
      in_reduction: false,
    };

    const { container } = render(<ProductCard product={product} />);
    const bgElement = container.querySelector('.bg-green-50');
    expect(bgElement).not.toBeNull();
  });
});
