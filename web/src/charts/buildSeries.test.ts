import { describe, expect, it } from 'vitest';
import { buildKlineSeries, buildTradeMarkers } from './buildSeries';

// 22 rows so BOLL(20) has at least one non-null value at index 21
const sampleCandles = [
  { date: '20240101', open: 10, high: 11, low: 9.5, close: 10.5, volume: 1000 },
  { date: '20240102', open: 10.5, high: 11.2, low: 10.3, close: 11, volume: 1200 },
  { date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900 },
  { date: '20240104', open: 10.9, high: 11, low: 10.5, close: 10.7, volume: 800 },
  { date: '20240105', open: 10.7, high: 10.9, low: 10.4, close: 10.6, volume: 700 },
  { date: '20240106', open: 10.6, high: 10.8, low: 10.3, close: 10.5, volume: 600 },
  { date: '20240107', open: 10.5, high: 10.7, low: 10.2, close: 10.4, volume: 500 },
  { date: '20240108', open: 10.4, high: 10.6, low: 10.1, close: 10.3, volume: 400 },
  { date: '20240109', open: 10.3, high: 10.5, low: 10.0, close: 10.2, volume: 300 },
  { date: '20240110', open: 10.2, high: 10.4, low: 10.0, close: 10.1, volume: 200 },
  { date: '20240111', open: 10.1, high: 10.3, low: 10.0, close: 10.0, volume: 100 },
  { date: '20240112', open: 10.0, high: 10.2, low: 9.9, close: 10.1, volume: 100 },
  { date: '20240113', open: 10.1, high: 10.3, low: 9.9, close: 10.2, volume: 100 },
  { date: '20240114', open: 10.2, high: 10.4, low: 10.0, close: 10.3, volume: 100 },
  { date: '20240115', open: 10.3, high: 10.5, low: 10.1, close: 10.4, volume: 100 },
  { date: '20240116', open: 10.4, high: 10.6, low: 10.2, close: 10.5, volume: 100 },
  { date: '20240117', open: 10.5, high: 10.7, low: 10.3, close: 10.6, volume: 100 },
  { date: '20240118', open: 10.6, high: 10.8, low: 10.4, close: 10.7, volume: 100 },
  { date: '20240119', open: 10.7, high: 10.9, low: 10.5, close: 10.8, volume: 100 },
  { date: '20240120', open: 10.8, high: 11.0, low: 10.6, close: 10.9, volume: 100 },
  { date: '20240121', open: 10.9, high: 11.1, low: 10.7, close: 11.0, volume: 100 },
  { date: '20240122', open: 11.0, high: 11.2, low: 10.8, close: 11.1, volume: 100 },
];

const sampleTrades = [
  { date: '20240102', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
  { date: '20240105', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
];

describe('buildKlineSeries', () => {
  it('appends MA/BOLL values aligned with input rows', () => {
    const out = buildKlineSeries(sampleCandles);
    expect(out).toHaveLength(22);
    expect(out[0].ma5).toBeNull();
    expect(out[4].ma5).not.toBeNull();
    expect(out[0].boll_upper).toBeNull();
    expect(out[21].boll_mid).not.toBeNull();
  });

  it('preserves original candle fields', () => {
    const out = buildKlineSeries(sampleCandles);
    expect(out[2]).toMatchObject({
      date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900,
    });
  });
});

describe('buildTradeMarkers', () => {
  it('alternates buy/sell by index (preserves existing semantics)', () => {
    const markers = buildTradeMarkers(sampleTrades);
    expect(markers).toEqual([
      { date: '20240102', side: 'buy' },
      { date: '20240105', side: 'sell' },
    ]);
  });

  it('returns empty array for empty trades', () => {
    expect(buildTradeMarkers([])).toEqual([]);
  });
});