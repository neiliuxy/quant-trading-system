import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { IndexKlinePanel } from './IndexKlinePanel';

const sampleCandles = [
  { date: '20240101', open: 3000, high: 3050, low: 2980, close: 3020, volume: 1e9 },
  { date: '20240102', open: 3020, high: 3080, low: 3010, close: 3060, volume: 1.1e9 },
  { date: '20240103', open: 3060, high: 3100, low: 3050, close: 3080, volume: 1.2e9 },
];

const defaultMaVisibility = { ma5: true, ma10: true, ma20: true, ma60: true, boll: true };

describe('IndexKlinePanel', () => {
  it('renders without throwing (mock LC in jsdom)', () => {
    expect(() => render(
      <IndexKlinePanel
        data={sampleCandles}
        maVisibility={defaultMaVisibility}
        onToggleMa={() => {}}
        chartDateRange={null}
        onChangeDateRange={() => {}}
        defaultStart="20240101"
        defaultEnd="20240103"
      />
    )).not.toThrow();
  });

  it('renders MA/BOLL toggle buttons', () => {
    render(
      <IndexKlinePanel
        data={sampleCandles}
        maVisibility={defaultMaVisibility}
        onToggleMa={() => {}}
        chartDateRange={null}
        onChangeDateRange={() => {}}
        defaultStart="20240101"
        defaultEnd="20240103"
      />
    );
    expect(screen.getByRole('button', { name: /MA20/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /BOLL/i })).toBeTruthy();
  });
});