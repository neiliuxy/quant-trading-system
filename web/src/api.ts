import type { BacktestResult, ComparisonResponse, Job, StrategySpec } from './types';

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

export async function getStocks(query?: string): Promise<Stock[]> {
  // Import local stocks directly
  const { STOCKS, searchStocks } = await import('./stocks');

  if (query) {
    return searchStocks(query);
  }
  return STOCKS;
}
