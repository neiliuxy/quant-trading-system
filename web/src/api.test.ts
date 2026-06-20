import { describe, expect, it, vi } from 'vitest';
import { createRefresh, getRefresh, listCache, listDatasets } from './api';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

function mockJsonResponse(payload: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(payload),
    text: () => Promise.resolve(typeof payload === 'string' ? payload : JSON.stringify(payload)),
  } as Response);
}

describe('datahub api wrappers', () => {
  it('lists datasets from the datahub endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      await mockJsonResponse([
        {
          dataset_type: 'stock_daily',
          label: 'A股日线',
          columns: ['date', 'open', 'high', 'low', 'close', 'volume'],
          symbol_required: true,
          source_name: 'akshare',
          ttl_seconds: 86400,
          historical_ttl_seconds: null,
        },
      ])
    );

    const datasets = await listDatasets();

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/data/datasets`, {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(datasets[0].dataset_type).toBe('stock_daily');
    expect(datasets[0].symbol_required).toBe(true);
  });

  it('serializes cache query params and omits empty values', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(await mockJsonResponse([]));

    await listCache({
      dataset_type: 'stock_daily',
      symbol: '000001',
      start: '20240101',
      end: '',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/data/cache?dataset_type=stock_daily&symbol=000001&start=20240101`,
      { headers: { 'Content-Type': 'application/json' } }
    );
  });

  it('creates a refresh with the backend payload shape', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      await mockJsonResponse({
        id: 7,
        request_key: 'stock_daily:000001:daily:20240101:20240131:false',
        dataset_type: 'stock_daily',
        symbol: '000001',
        frequency: 'daily',
        start_date: '20240101',
        end_date: '20240131',
        force_refresh: 0,
        status: 'queued',
        cache_hit: 0,
        error_type: null,
        error_message: null,
        output_cache_path: null,
        created_at: '2026-06-20 10:00:00',
        started_at: null,
        finished_at: null,
        updated_at: '2026-06-20 10:00:00',
      })
    );

    const refresh = await createRefresh({
      dataset_type: 'stock_daily',
      symbol: '000001',
      start: '20240101',
      end: '20240131',
      frequency: 'daily',
      force_refresh: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/data/refresh`, {
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
      body: JSON.stringify({
        dataset_type: 'stock_daily',
        symbol: '000001',
        start: '20240101',
        end: '20240131',
        frequency: 'daily',
        force_refresh: false,
      }),
    });
    expect(refresh.status).toBe('queued');
  });

  it('gets refresh detail by id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      await mockJsonResponse({
        id: 7,
        request_key: 'index_daily:global:daily:20240101:20240131:false',
        dataset_type: 'index_daily',
        symbol: null,
        frequency: 'daily',
        start_date: '20240101',
        end_date: '20240131',
        force_refresh: 0,
        status: 'completed',
        cache_hit: 1,
        error_type: null,
        error_message: null,
        output_cache_path: '/tmp/index.csv',
        created_at: '2026-06-20 10:00:00',
        started_at: '2026-06-20 10:00:01',
        finished_at: '2026-06-20 10:00:02',
        updated_at: '2026-06-20 10:00:02',
      })
    );

    const refresh = await getRefresh(7);

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/data/refresh/7`, {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(refresh.output_cache_path).toBe('/tmp/index.csv');
  });

  it('preserves FastAPI error envelopes in rejected request messages', async () => {
    const payload = {
      detail: {
        error_type: 'refresh_in_progress',
        message: 'Refresh already running: 12',
        refresh_id: 12,
      },
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(await mockJsonResponse(payload, false, 409));

    await expect(
      createRefresh({
        dataset_type: 'stock_daily',
        symbol: '000001',
        start: '20240101',
        end: '20240131',
        frequency: 'daily',
        force_refresh: true,
      })
    ).rejects.toThrow(JSON.stringify(payload));
  });
});
