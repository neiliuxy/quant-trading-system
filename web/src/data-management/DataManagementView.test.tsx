import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DataManagementView from './DataManagementView';
import { createRefresh, getRefresh, listCache, listDatasets } from '../api';
import type { CacheEntry, DataRefresh, DatasetSpec } from '../types';

vi.mock('../api', () => ({
  listDatasets: vi.fn(),
  listCache: vi.fn(),
  createRefresh: vi.fn(),
  getRefresh: vi.fn(),
}));

const datasets: DatasetSpec[] = [
  {
    dataset_type: 'stock_daily',
    label: 'A股日线',
    columns: ['date', 'open', 'high', 'low', 'close', 'volume'],
    symbol_required: true,
    source_name: 'akshare',
    ttl_seconds: 86400,
    historical_ttl_seconds: null,
  },
  {
    dataset_type: 'index_daily',
    label: '大盘指数',
    columns: ['date', 'open', 'high', 'low', 'close', 'volume', 'amount'],
    symbol_required: false,
    source_name: 'akshare',
    ttl_seconds: 86400,
    historical_ttl_seconds: null,
  },
];

const stockCache: CacheEntry[] = [
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

function refresh(status: DataRefresh['status'], id = 9): DataRefresh {
  return {
    id,
    request_key: `key-${id}`,
    dataset_type: 'stock_daily',
    symbol: '000001',
    frequency: 'daily',
    start_date: '20240101',
    end_date: '20240131',
    force_refresh: 0,
    status,
    cache_hit: 0,
    error_type: null,
    error_message: null,
    output_cache_path: status === 'completed' ? '/data/cache/stock_daily/file.csv' : null,
    created_at: '2026-06-20 10:00:00',
    started_at: status === 'queued' ? null : '2026-06-20 10:00:01',
    finished_at: status === 'completed' ? '2026-06-20 10:00:02' : null,
    updated_at: '2026-06-20 10:00:02',
  };
}

describe('DataManagementView', () => {
  beforeEach(() => {
    vi.mocked(listDatasets).mockResolvedValue(datasets);
    vi.mocked(listCache).mockResolvedValue(stockCache);
    vi.mocked(createRefresh).mockResolvedValue(refresh('queued'));
    vi.mocked(getRefresh).mockResolvedValue(refresh('completed'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('selects the first stock dataset and queries cache by dataset_type after datasets load', async () => {
    render(<DataManagementView />);

    expect(await screen.findByText('A股日线')).toBeInTheDocument();

    await waitFor(() => {
      expect(listCache).toHaveBeenCalledWith({ dataset_type: 'stock_daily' });
    });
    expect(screen.getByText('000001')).toBeInTheDocument();
  });

  it('switches to index segment and queries cache for the first index dataset', async () => {
    render(<DataManagementView />);

    fireEvent.click(await screen.findByRole('button', { name: '大盘' }));

    await waitFor(() => {
      expect(listCache).toHaveBeenLastCalledWith({ dataset_type: 'index_daily' });
    });
    expect(screen.queryByLabelText('代码')).not.toBeInTheDocument();
  });

  it('creates a refresh, adds it to the queue, polls detail, and reloads cache on completion', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    render(<DataManagementView />);

    await screen.findByText('A股日线');
    fireEvent.change(screen.getByLabelText('刷新代码'), { target: { value: '000001' } });
    fireEvent.change(screen.getByLabelText('刷新开始'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('刷新结束'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    await waitFor(() => {
      expect(createRefresh).toHaveBeenCalledWith({
        dataset_type: 'stock_daily',
        symbol: '000001',
        start: '20240101',
        end: '20240131',
        frequency: 'daily',
        force_refresh: false,
      });
    });

    expect(await screen.findByRole('button', { name: /#9 stock_daily/ })).toBeInTheDocument();

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    await waitFor(() => {
      expect(getRefresh).toHaveBeenCalledWith(9);
      expect(listCache).toHaveBeenCalledTimes(2);
      expect(listCache).toHaveBeenLastCalledWith({ dataset_type: 'stock_daily' });
    });
  });

  it('stops polling and keeps the last known refresh when detail polling fails', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getRefresh).mockRejectedValue(new Error('refresh detail failed'));

    render(<DataManagementView />);

    await screen.findByText('A股日线');
    fireEvent.change(screen.getByLabelText('刷新代码'), { target: { value: '000001' } });
    fireEvent.change(screen.getByLabelText('刷新开始'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('刷新结束'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    expect(await screen.findByRole('button', { name: /#9 stock_daily/ })).toBeInTheDocument();

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(await screen.findByText('refresh detail failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /#9 stock_daily/ })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('轮询中')).not.toBeInTheDocument();
    });
    const callsAfterFailure = vi.mocked(getRefresh).mock.calls.length;

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(vi.mocked(getRefresh).mock.calls.length).toBe(callsAfterFailure);
  });

  it('maps refresh_in_progress conflicts to a specific message', async () => {
    vi.mocked(createRefresh).mockRejectedValue(
      new Error(JSON.stringify({ detail: { error_type: 'refresh_in_progress' } }))
    );

    render(<DataManagementView />);

    await screen.findByText('A股日线');
    fireEvent.change(screen.getByLabelText('刷新代码'), { target: { value: '000001' } });
    fireEvent.change(screen.getByLabelText('刷新开始'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('刷新结束'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    expect(await screen.findByText('该数据范围已有刷新任务在运行')).toBeInTheDocument();
  });
});
