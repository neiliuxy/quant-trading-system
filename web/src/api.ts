import type {
  BacktestResult,
  CacheEntry,
  CacheQueryParams,
  ComparisonResponse,
  DataRefresh,
  DataRefreshPayload,
  DatasetSpec,
  Job,
  ScreenerResult,
  ScreenerRun,
  StrategySpec,
  WfoConfig,
  WfoResult,
  WfoRun,
} from './types';

export interface Stock {
  code: string;
  name: string;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

// In-memory cache for stocks
const stocksCache = new Map<string, Stock[]>();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function queryString(params: CacheQueryParams): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, value);
    }
  });
  const serialized = search.toString();
  return serialized ? `?${serialized}` : '';
}

export function listDatasets(): Promise<DatasetSpec[]> {
  return request<DatasetSpec[]>('/api/data/datasets');
}

export function listCache(params: CacheQueryParams = {}): Promise<CacheEntry[]> {
  return request<CacheEntry[]>(`/api/data/cache${queryString(params)}`);
}

export function createRefresh(payload: DataRefreshPayload): Promise<DataRefresh> {
  return request<DataRefresh>('/api/data/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getRefresh(refreshId: number): Promise<DataRefresh> {
  return request<DataRefresh>(`/api/data/refresh/${refreshId}`);
}

export function listJobs(): Promise<Job[]> {
  return request<Job[]>('/api/jobs');
}

export function createJob(payload: {
  symbol: string;
  start: string;
  end: string;
  cash: number;
  use_market_filter: boolean;
  risk_percent: number;
  fast_ma: number;
  slow_ma: number;
  strategy_id: string;
  strategy_params: Record<string, unknown>;
  force?: boolean;
}): Promise<Job> {
  return request<Job>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listStrategies(): Promise<StrategySpec[]> {
  return request<StrategySpec[]>('/api/strategies');
}

export function getJob(jobId: number): Promise<Job> {
  return request<Job>(`/api/jobs/${jobId}`);
}

export function getResult(jobId: number): Promise<BacktestResult> {
  return request<BacktestResult>(`/api/jobs/${jobId}/result`);
}

export function createMarketFilterComparison(jobId: number): Promise<ComparisonResponse> {
  return request<ComparisonResponse>(`/api/jobs/${jobId}/compare-market-filter`, {
    method: 'POST',
  });
}

export function deleteJob(jobId: number): Promise<{ status: string; job_id: number }> {
  return request<{ status: string; job_id: number }>(`/api/jobs/${jobId}`, {
    method: 'DELETE',
  });
}

export function deleteAllJobs(): Promise<{ status: string; deleted_count: number }> {
  return request<{ status: string; deleted_count: number }>('/api/jobs', {
    method: 'DELETE',
  });
}

// WFO 端点的 400 错误体是 {"detail": "..."},需要把 detail 透传给用户。
async function wfoRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) message = body.detail;
    } catch {
      /* keep default message */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function createWfo(payload: WfoConfig): Promise<WfoRun> {
  return wfoRequest<WfoRun>('/api/wfo', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getWfoStatus(wfoId: number): Promise<WfoRun> {
  return wfoRequest<WfoRun>(`/api/wfo/${wfoId}`);
}

export function getWfoResult(wfoId: number): Promise<WfoResult> {
  return wfoRequest<WfoResult>(`/api/wfo/${wfoId}/result`);
}

export function createScreener(payload: {
  date: string;
  universe_mode: 'predefined' | 'custom' | 'full_market';
  universe_symbol?: string | null;
  custom_list?: string[] | null;
  top_n?: number;
  market_gate_mode?: 'hard' | 'soft' | 'off';
  market_gate_threshold?: number;
}): Promise<ScreenerRun> {
  return request<ScreenerRun>('/api/screener', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getScreenerStatus(runId: number): Promise<ScreenerRun> {
  return request<ScreenerRun>(`/api/screener/${runId}`);
}

export function getScreenerResult(runId: number): Promise<ScreenerResult> {
  return request<ScreenerResult>(`/api/screener/${runId}/result`);
}

export interface RecentValidDate {
  date: string;
  source: 'index_cache' | 'today-fallback';
}

export function getRecentValidScreeningDate(): Promise<RecentValidDate> {
  return request<RecentValidDate>('/api/screener/recent-valid-date');
}

export async function getStocks(query?: string): Promise<Stock[]> {
  const normalizedQuery = query?.trim().toLowerCase() ?? '';

  if (!normalizedQuery && stocksCache.has('all')) {
    return stocksCache.get('all')!;
  }

  // Import local stocks directly
  const { STOCKS } = await import('./stocks');
  const allStocks = STOCKS as Stock[];

  if (!stocksCache.has('all')) {
    stocksCache.set('all', allStocks);
  }

  if (!normalizedQuery) {
    return allStocks;
  }

  return allStocks.filter((stock) =>
    stock.code.includes(normalizedQuery) || stock.name.toLowerCase().includes(normalizedQuery)
  );
}
