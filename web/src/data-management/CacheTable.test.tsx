import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import CacheTable from './CacheTable';
import type { CacheEntry, DatasetSpec } from '../types';

const stockDataset: DatasetSpec = {
  dataset_type: 'stock_daily',
  label: 'A股日线',
  columns: ['date', 'open', 'high', 'low', 'close', 'volume'],
  symbol_required: true,
  source_name: 'akshare',
  ttl_seconds: 86400,
  historical_ttl_seconds: null,
};

const indexDataset: DatasetSpec = {
  ...stockDataset,
  dataset_type: 'index_daily',
  label: '大盘指数',
  symbol_required: false,
};

const entries: CacheEntry[] = [
  {
    id: 1,
    dataset_type: 'stock_daily',
    symbol: '000001',
    frequency: 'daily',
    start_date: '20240101',
    end_date: '20240131',
    file_path: '/data/cache/stock_daily/000001_20240101_20240131.csv',
    row_count: 20,
    schema_version: 'v1',
    source_name: 'akshare',
    expires_at: null,
    created_at: '2026-06-20 10:00:00',
    refreshed_at: '2026-06-20 10:00:00',
  },
];

describe('CacheTable', () => {
  it('submits dataset-driven cache filters', () => {
    const onQuery = vi.fn();
    const onRefresh = vi.fn();

    render(
      <CacheTable
        selectedDataset={stockDataset}
        entries={entries}
        loading={false}
        error={null}
        onQuery={onQuery}
        onRefresh={onRefresh}
        refreshing={false}
      />
    );

    fireEvent.change(screen.getByLabelText('代码'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('开始日期'), { target: { value: '2024-02-01' } });
    fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2024-02-29' } });
    fireEvent.click(screen.getByRole('button', { name: /查询缓存/ }));

    expect(onQuery).toHaveBeenCalledWith({
      dataset_type: 'stock_daily',
      symbol: '600519',
      start: '20240201',
      end: '20240229',
    });
  });

  it('hides symbol input for index datasets and submits refresh payload', () => {
    const onQuery = vi.fn();
    const onRefresh = vi.fn();

    render(
      <CacheTable
        selectedDataset={indexDataset}
        entries={[]}
        loading={false}
        error={null}
        onQuery={onQuery}
        onRefresh={onRefresh}
        refreshing={false}
      />
    );

    expect(screen.queryByLabelText('代码')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('刷新开始'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('刷新结束'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    expect(onRefresh).toHaveBeenCalledWith({
      dataset_type: 'index_daily',
      symbol: null,
      start: '20240101',
      end: '20240131',
      frequency: 'daily',
      force_refresh: false,
    });
  });

  it('renders loading, error, empty, and table states', () => {
    const props = {
      selectedDataset: stockDataset,
      onQuery: vi.fn(),
      onRefresh: vi.fn(),
      refreshing: false,
    };

    const { rerender } = render(<CacheTable {...props} entries={[]} loading error={null} />);
    expect(screen.getByText('缓存加载中...')).toBeInTheDocument();

    rerender(<CacheTable {...props} entries={[]} loading={false} error="cache failed" />);
    expect(screen.getByText('cache failed')).toBeInTheDocument();

    rerender(<CacheTable {...props} entries={[]} loading={false} error={null} />);
    expect(screen.getByText('没有匹配的缓存条目')).toBeInTheDocument();

    rerender(<CacheTable {...props} entries={entries} loading={false} error={null} />);
    expect(screen.getByText('000001')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
  });
});
