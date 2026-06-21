export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface StrategyParamSpec {
  name: string;
  label: string;
  type: 'int' | 'float' | 'string' | 'bool';
  default: number | string | boolean;
}

export interface StrategySpec {
  id: string;
  name: string;
  description: string;
  params: StrategyParamSpec[];
}

export interface BacktestFormValues {
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
}

export interface Job {
  id: number;
  run_key: string;
  status: JobStatus;
  symbol: string;
  start_date: string;
  end_date: string;
  cash: number;
  use_market_filter: boolean;
  risk_percent: number;
  fast_ma: number;
  slow_ma: number;
  strategy_id: string;
  strategy_params_json: string;
  code_version: string;
  cache_hit: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  symbol: string;
  start: string;
  end: string;
  initial_cash: number;
  final_value: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
  win_rate_pct: number;
  sharpe: number;
  annual_return_pct: number;
  profit_loss_ratio: number;
  benchmark_return_pct: number;
  excess_return_pct: number;
  equity_curve: Array<{ date: string; value: number; cash: number }>;
  trades: Array<{ date: string; pnl: number; pnlcomm: number; barlen: number; size: number }>;
  market_scores: Array<{
    date: string;
    trend_score: number;
    sentiment_score: number;
    volume_score: number;
    total_score: number;
  }>;
  market_score_summary: Record<string, number>;
  price_data: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
  index_data: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    amount: number;
  }>;
}

export interface ComparisonResponse {
  source_job_id: number;
  comparison_job: Job;
}

export interface StrategyGuideParam {
  name: string;
  label: string;
  meaning: string;
  recommendedValue: string;
  adjustmentTips: string;
}

export interface StrategyGuideData {
  id: string;
  name: string;
  description: string;
  applicableScenarios: string;
  principle: {
    title: string;
    content: string;
  };
  parameters: StrategyGuideParam[];
  characteristics: {
    tradingFrequency: string;
    holdingPeriod: string;
    applicableStocks: string;
    riskLevel: string;
  };
}

export type DataSegment = 'stock' | 'index';

export type DataRefreshStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface DatasetSpec {
  dataset_type: string;
  label: string;
  columns: string[];
  symbol_required: boolean;
  source_name: string;
  ttl_seconds: number | null;
  historical_ttl_seconds: number | null;
}

export interface CacheEntry {
  id: number;
  dataset_type: string;
  symbol: string | null;
  frequency: string;
  start_date: string;
  end_date: string;
  file_path: string;
  row_count: number;
  schema_version: string;
  source_name: string;
  expires_at: string | null;
  created_at: string;
  refreshed_at: string;
}

export interface DataRefresh {
  id: number;
  request_key: string;
  dataset_type: string;
  symbol: string | null;
  frequency: string;
  start_date: string;
  end_date: string;
  force_refresh: number;
  status: DataRefreshStatus;
  cache_hit: number;
  error_type: string | null;
  error_message: string | null;
  output_cache_path: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
}

export interface DataRefreshPayload {
  dataset_type: string;
  symbol?: string | null;
  start: string;
  end: string;
  frequency: string;
  force_refresh: boolean;
}

export interface CacheQueryParams {
  dataset_type?: string;
  symbol?: string;
  start?: string;
  end?: string;
}
