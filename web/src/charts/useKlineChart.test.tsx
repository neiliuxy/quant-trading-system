import { render } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it } from 'vitest';
import { useKlineChart } from './useKlineChart';
import { buildKlineSeries } from './buildSeries';

const sampleCandles = [
  { date: '20240101', open: 10, high: 11, low: 9.5, close: 10.5, volume: 1000 },
  { date: '20240102', open: 10.5, high: 11.2, low: 10.3, close: 11, volume: 1200 },
  { date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900 },
];

const sampleData = buildKlineSeries(sampleCandles);
const maVisibility = { ma5: true, ma10: true, ma20: true, ma60: true, boll: true };

function Harness({ data, trades = [] as { date: string; side: 'buy' | 'sell' }[] }: { data: typeof sampleData; trades?: { date: string; side: 'buy' | 'sell' }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useKlineChart({ container: ref.current, data, maVisibility, trades });
  return <div ref={ref} data-testid="kline-host" style={{ width: 800, height: 400 }} />;
}

describe('useKlineChart', () => {
  it('renders without throwing (mock LC in jsdom)', () => {
    expect(() => render(<Harness data={sampleData} />)).not.toThrow();
  });

  it('handles empty trades without errors', () => {
    expect(() => render(<Harness data={sampleData} trades={[]} />)).not.toThrow();
  });
});