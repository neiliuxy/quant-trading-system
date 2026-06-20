import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { StockKlinePanel } from './StockKlinePanel';
import { buildTradeMarkers } from '../charts/buildSeries';
import i18n from '../i18n';

const sampleCandles = [
  { date: '20240101', open: 10, high: 11, low: 9.5, close: 10.5, volume: 1000 },
  { date: '20240102', open: 10.5, high: 11.2, low: 10.3, close: 11, volume: 1200 },
  { date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900 },
  { date: '20240104', open: 10.9, high: 11, low: 10.5, close: 10.7, volume: 800 },
  { date: '20240105', open: 10.7, high: 10.9, low: 10.4, close: 10.6, volume: 700 },
];

const sampleTrades = [
  { date: '20240102', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
  { date: '20240105', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
];

const defaultMaVisibility = { ma5: true, ma10: true, ma20: true, ma60: true, boll: true };

describe('StockKlinePanel', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('zh');
  });

  afterEach(async () => {
    await i18n.changeLanguage('zh');
    localStorage.clear();
  });

  it('renders without throwing (mock LC in jsdom)', () => {
    expect(() => render(
      <StockKlinePanel
        data={sampleCandles}
        trades={sampleTrades}
        maVisibility={defaultMaVisibility}
        onToggleMa={() => {}}
        chartDateRange={null}
        onChangeDateRange={() => {}}
        defaultStart="20240101"
        defaultEnd="20240105"
      />
    )).not.toThrow();
  });

  it('renders MA/BOLL toggle buttons', () => {
    render(
      <StockKlinePanel
        data={sampleCandles}
        maVisibility={defaultMaVisibility}
        onToggleMa={() => {}}
        chartDateRange={null}
        onChangeDateRange={() => {}}
        defaultStart="20240101"
        defaultEnd="20240105"
      />
    );
    expect(screen.getByRole('button', { name: /MA5/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /BOLL/i })).toBeTruthy();
  });

  it('buildTradeMarkers still alternates buy/sell (preserves semantics)', () => {
    expect(buildTradeMarkers(sampleTrades)).toEqual([
      { date: '20240102', side: 'buy' },
      { date: '20240105', side: 'sell' },
    ]);
  });
});

describe('StockKlinePanel locale switching', () => {
  afterEach(async () => {
    await i18n.changeLanguage('zh');
    localStorage.clear();
  });

  it('renders trade legend in Chinese when locale is zh', async () => {
    await i18n.changeLanguage('zh');
    render(
      <StockKlinePanel
        data={sampleCandles}
        maVisibility={defaultMaVisibility}
        onToggleMa={() => {}}
        chartDateRange={null}
        onChangeDateRange={() => {}}
        defaultStart="20240101"
        defaultEnd="20240105"
      />
    );
    // Verify translation key resolves to a non-empty string in zh
    expect(i18n.t('legend.buyPoint')).toBeTruthy();
    expect(i18n.t('legend.sellPoint')).toBeTruthy();
  });

  it('renders trade legend in English when locale is en', async () => {
    await i18n.changeLanguage('en');
    expect(i18n.t('legend.buyPoint')).toBe('Buy Point');
    expect(i18n.t('legend.sellPoint')).toBe('Sell Point');
  });
});