export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

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
}

export interface ComparisonResponse {
  source_job_id: number;
  comparison_job: Job;
}
