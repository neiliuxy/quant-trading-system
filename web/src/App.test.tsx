import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import i18n from './i18n';
import { getJob, getResult, getStocks, listJobs, listStrategies } from './api';

vi.mock('./data-management/DataManagementView', () => ({
  default: () => <div>Data Management View</div>,
}));

vi.mock('./api', () => ({
  createJob: vi.fn(),
  createMarketFilterComparison: vi.fn(),
  deleteAllJobs: vi.fn(),
  deleteJob: vi.fn(),
  getJob: vi.fn(),
  getResult: vi.fn(),
  getStocks: vi.fn(),
  listJobs: vi.fn(),
  listStrategies: vi.fn(),
}));

describe('App view switching', () => {
  beforeEach(() => {
    vi.mocked(getStocks).mockResolvedValue([]);
    vi.mocked(listJobs).mockResolvedValue([]);
    vi.mocked(listStrategies).mockResolvedValue([
      {
        id: 'swing_ma_boll',
        name: 'Swing MA Boll',
        description: 'demo strategy',
        params: [{ name: 'fast_ma', label: 'Fast MA', type: 'int', default: 10 }],
      },
    ]);
    vi.mocked(getJob).mockResolvedValue({
      id: 0,
      run_key: '',
      status: 'completed',
      symbol: '000001',
      start_date: '20240101',
      end_date: '20240131',
      cash: 100000,
      use_market_filter: true,
      risk_percent: 0.95,
      fast_ma: 10,
      slow_ma: 20,
      strategy_id: 'swing_ma_boll',
      strategy_params_json: '{}',
      code_version: '',
      cache_hit: false,
      error: null,
      created_at: '2026-06-20 10:00:00',
      updated_at: '2026-06-20 10:00:00',
    });
    vi.mocked(getResult).mockResolvedValue({
      symbol: '000001',
      start: '20240101',
      end: '20240131',
      initial_cash: 100000,
      final_value: 100000,
      total_return_pct: 0,
      max_drawdown_pct: 0,
      trade_count: 0,
      win_rate_pct: 0,
      equity_curve: [],
      trades: [],
      market_scores: [],
      market_score_summary: {},
      price_data: [],
      index_data: [],
    });
  });

  it('keeps the backtest view available when switching to and from data management', async () => {
    await i18n.changeLanguage('zh');
    render(<App />);

    expect(await screen.findByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) })).toBeInTheDocument();
    expect(screen.getByText(i18n.t('history.title'))).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: new RegExp(i18n.t('nav.dataMgmt')) }));

    expect(screen.getByText('Data Management View')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: new RegExp(i18n.t('nav.backtest')) }));

    expect(await screen.findByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) })).toBeInTheDocument();
    expect(screen.getByText(i18n.t('history.title'))).toBeInTheDocument();
  });
});

describe('App locale switching', () => {
  beforeEach(() => {
    vi.mocked(getStocks).mockResolvedValue([]);
    vi.mocked(listJobs).mockResolvedValue([]);
    vi.mocked(listStrategies).mockResolvedValue([
      {
        id: 'swing_ma_boll',
        name: 'Swing MA Boll',
        description: 'demo strategy',
        params: [{ name: 'fast_ma', label: 'Fast MA', type: 'int', default: 10 }],
      },
    ]);
  });

  afterEach(async () => {
    await i18n.changeLanguage('zh');
    localStorage.clear();
  });

  it('renders Chinese labels when locale is zh', async () => {
    await i18n.changeLanguage('zh');
    render(<App />);
    expect(await screen.findByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) })).toBeInTheDocument();
    expect(screen.getByText(i18n.t('history.title'))).toBeInTheDocument();
  });

  it('renders English labels when locale is en', async () => {
    await i18n.changeLanguage('en');
    render(<App />);
    expect(await screen.findByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) })).toBeInTheDocument();
    expect(screen.getByText(i18n.t('history.title'))).toBeInTheDocument();
  });
});
