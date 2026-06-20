import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import RunForm from './RunForm';
import i18n from './i18n';
import type { BacktestFormValues, StrategySpec } from './types';

const strategies: StrategySpec[] = [
  {
    id: 'swing_ma_boll',
    name: 'Swing',
    description: 'desc',
    params: [{ name: 'window', label: 'Window', type: 'int', default: 20 }],
  },
  {
    id: 'b1',
    name: 'B1',
    description: 'desc',
    params: [{ name: 'threshold', label: 'Threshold', type: 'float', default: 1.5 }],
  },
];

const initialValue: BacktestFormValues = {
  symbol: '000001',
  start: '20240101',
  end: '20241231',
  cash: 100000,
  use_market_filter: true,
  risk_percent: 0.95,
  fast_ma: 10,
  slow_ma: 20,
  strategy_id: 'swing_ma_boll',
  strategy_params: { window: 20 },
};

describe('RunForm', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('zh');
  });

  afterEach(async () => {
    await i18n.changeLanguage('zh');
    localStorage.clear();
  });

  it('keeps edits local until submit', () => {
    const onSubmit = vi.fn();
    const onCompareMarketFilter = vi.fn();

    render(
      <RunForm
        initialValue={initialValue}
        strategies={strategies}
        submitting={false}
        hasSelectedJob
        onSubmit={onSubmit}
        onCompareMarketFilter={onCompareMarketFilter}
      />
    );

    fireEvent.change(screen.getByDisplayValue('100000'), { target: { value: '200000' } });
    fireEvent.change(screen.getByDisplayValue('2024-01-01'), { target: { value: '2024-02-01' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'b1' } });

    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.submit(screen.getByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) }).closest('form')!);

    expect(onSubmit).toHaveBeenCalledWith(
      {
        ...initialValue,
        start: '20240201',
        cash: 200000,
        strategy_id: 'b1',
        strategy_params: { threshold: 1.5 },
      },
      false
    );
  });
});

describe('RunForm locale switching', () => {
  afterEach(async () => {
    await i18n.changeLanguage('zh');
    localStorage.clear();
  });

  it('renders Chinese labels when locale is zh', async () => {
    await i18n.changeLanguage('zh');
    render(
      <RunForm
        initialValue={initialValue}
        strategies={strategies}
        submitting={false}
        hasSelectedJob
        onSubmit={vi.fn()}
        onCompareMarketFilter={vi.fn()}
      />
    );
    expect(screen.getByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) })).toBeInTheDocument();
  });

  it('renders English labels when locale is en', async () => {
    await i18n.changeLanguage('en');
    render(
      <RunForm
        initialValue={initialValue}
        strategies={strategies}
        submitting={false}
        hasSelectedJob
        onSubmit={vi.fn()}
        onCompareMarketFilter={vi.fn()}
      />
    );
    expect(screen.getByRole('button', { name: new RegExp(i18n.t('form.runBacktest')) })).toBeInTheDocument();
  });
});
