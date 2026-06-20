import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import RefreshQueue from './RefreshQueue';
import type { DataRefresh } from '../types';

function refresh(status: DataRefresh['status'], id = 1): DataRefresh {
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
    error_type: status === 'failed' ? 'source_unavailable' : null,
    error_message: status === 'failed' ? 'network failed' : null,
    output_cache_path: status === 'completed' ? '/data/cache/file.csv' : null,
    created_at: '2026-06-20 10:00:00',
    started_at: status === 'queued' ? null : '2026-06-20 10:00:01',
    finished_at: status === 'queued' || status === 'running' ? null : '2026-06-20 10:00:02',
    updated_at: '2026-06-20 10:00:02',
  };
}

describe('RefreshQueue', () => {
  it('renders empty queue state', () => {
    render(<RefreshQueue refreshes={[]} selectedRefreshId={null} onSelectRefresh={vi.fn()} pollingIds={new Set()} />);

    expect(screen.getByText('当前会话尚未发起刷新任务')).toBeInTheDocument();
  });

  it('renders all refresh statuses and selected details', () => {
    render(
      <RefreshQueue
        refreshes={[refresh('queued', 1), refresh('running', 2), refresh('completed', 3), refresh('failed', 4)]}
        selectedRefreshId={4}
        onSelectRefresh={vi.fn()}
        pollingIds={new Set([2])}
      />
    );

    expect(screen.getByText('queued')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getAllByText('failed')).toHaveLength(2);
    expect(screen.getByText('轮询中')).toBeInTheDocument();
    expect(screen.getByText('source_unavailable')).toBeInTheDocument();
    expect(screen.getByText('network failed')).toBeInTheDocument();
  });

  it('emits selected refresh id', () => {
    const onSelectRefresh = vi.fn();

    render(
      <RefreshQueue
        refreshes={[refresh('queued', 7)]}
        selectedRefreshId={null}
        onSelectRefresh={onSelectRefresh}
        pollingIds={new Set()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /#7 stock_daily/ }));

    expect(onSelectRefresh).toHaveBeenCalledWith(7);
  });
});
