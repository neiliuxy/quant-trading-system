import { useEffect, useMemo, useState } from 'react';
import { Activity, BookOpen, Play, RefreshCcw, Eye, EyeOff, Trash2 } from 'lucide-react';
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { createJob, createMarketFilterComparison, deleteJob, deleteAllJobs, getJob, getResult, getStocks, listJobs, listStrategies } from './api';
import type { BacktestFormValues, BacktestResult, Job, StrategySpec } from './types';
import ChartDateRangeControl from './ChartDateRangeControl';
import RunForm from './RunForm';
import StrategyGuide from './StrategyGuide';
import { calcMA, calcBoll, calcMacd, calcKdj } from './indicators';
import { filterByDateRange } from './charts/filterByDateRange';
import { EquityPanel } from './panels/EquityPanel';
import type { LineVisibility } from './panels/EquityPanel';

const defaultForm: BacktestFormValues = {
  symbol: '000001',
  start: getDefaultStartDate(),
  end: getDefaultEndDate(),
  cash: 100000,
  use_market_filter: true,
  risk_percent: 0.95,
  fast_ma: 10,
  slow_ma: 20,
  strategy_id: 'swing_ma_boll',
  strategy_params: {} as Record<string, unknown>,
};

function getDefaultStartDate(): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() - 5);
  return date.toISOString().split('T')[0].replace(/-/g, '');
}

function getDefaultEndDate(): string {
  const date = new Date();
  return date.toISOString().split('T')[0].replace(/-/g, '');
}

function formatPct(value: number) {
  return `${value.toFixed(2)}%`;
}

const statusLabels: Record<string, string> = {
  'queued': '排队中',
  'running': '运行中',
  'completed': '已完成',
  'failed': '失败',
};

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{statusLabels[status] || status}</span>;
}

function CandleShape(props: any) {
  const { x, y, width, height, payload } = props;
  const { open, high, low, close } = payload;
  if (open === undefined || close === 0) return null;

  const isUp = close >= open;
  const color = isUp ? '#ef4444' : '#22c55e';
  const cx = x + width / 2;

  // y = top of bar (close price pixel), y + height = baseline (0 price pixel)
  // pixels per price unit = height / close
  const pxPerUnit = height / close;

  const highY = y + height - high * pxPerUnit;
  const lowY = y + height - low * pxPerUnit;
  const openY = y + height - open * pxPerUnit;
  const closeY = y + height - close * pxPerUnit;
  const bodyTop = Math.min(openY, closeY);
  const bodyBottom = Math.max(openY, closeY);

  return (
    <g>
      <line x1={cx} y1={highY} x2={cx} y2={lowY} stroke={color} strokeWidth={1} />
      <rect
        x={x + 1}
        y={bodyTop}
        width={width - 2}
        height={Math.max(1, bodyBottom - bodyTop)}
        fill={isUp ? color : 'transparent'}
        stroke={color}
        strokeWidth={1}
      />
    </g>
  );
}

function buildTradeMarkerMap(trades: Array<{ date: string }>): Map<string, { buy?: boolean; sell?: boolean }> {
  const map = new Map<string, { buy?: boolean; sell?: boolean }>();
  trades.forEach((trade, index) => {
    if (!map.has(trade.date)) {
      map.set(trade.date, {});
    }
    const marker = map.get(trade.date)!;
    if (index % 2 === 0) {
      marker.buy = true;
    } else {
      marker.sell = true;
    }
  });
  return map;
}

function sameJob(lhs: Job | null, rhs: Job | null): boolean {
  if (lhs === rhs) return true;
  if (!lhs || !rhs) return false;
  return (
    lhs.id === rhs.id &&
    lhs.status === rhs.status &&
    lhs.updated_at === rhs.updated_at &&
    lhs.error === rhs.error &&
    lhs.cache_hit === rhs.cache_hit
  );
}

interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;
}

interface IndexMaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;
}

export default function App() {
  const [runFormDefaults, setRunFormDefaults] = useState<BacktestFormValues>(defaultForm);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [strategies, setStrategies] = useState<StrategySpec[]>([]);
  const [comparisonJob, setComparisonJob] = useState<Job | null>(null);
  const [comparisonResult, setComparisonResult] = useState<BacktestResult | null>(null);
  const [lineVisibility, setLineVisibility] = useState<LineVisibility>({
    equity: true,
    totalScore: true,
    trendScore: false,
    sentimentScore: false,
    volumeScore: false,
  });
  const [maVisibility, setMaVisibility] = useState<MaVisibility>({
    ma5: true,
    ma10: true,
    ma20: true,
    ma60: true,
    boll: false,
  });
  const [indexMaVisibility, setIndexMaVisibility] = useState<IndexMaVisibility>({
    ma5: true,
    ma10: true,
    ma20: true,
    ma60: true,
    boll: false,
  });
  const toggleIndexMa = (key: keyof IndexMaVisibility) => {
    setIndexMaVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
  };
  type IndicatorKey = 'macd' | 'kdj' | 'volume' | 'amount';
  const [stockSelectedIndicator, setStockSelectedIndicator] = useState<IndicatorKey>('macd');
  const [selectedIndicator, setSelectedIndicator] = useState<IndicatorKey>('macd');
  const [chartDateRange, setChartDateRange] = useState<{ start: string; end: string } | null>(null);
  const [deleteConfirmJobId, setDeleteConfirmJobId] = useState<number | null>(null);
  const [deleteAllConfirm, setDeleteAllConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [stockLookup, setStockLookup] = useState<Map<string, string>>(new Map());

  function getStrategyName(id: string): string {
    const found = strategies.find(s => s.id === id);
    return found?.name ?? id;
  }

  function getStockName(code: string): string {
    return stockLookup.get(code) ?? code;
  }

  const refreshJobs = useMemo(
    () => async () => {
      const rows = await listJobs();
      setJobs(rows);
      if (!selectedJob && rows.length > 0) {
        setSelectedJob(rows[0]);
      }
    },
    [selectedJob]
  );

  useEffect(() => {
    refreshJobs().catch((err) => setError(err.message));
    getStocks()
      .then((stocks) => setStockLookup(new Map(stocks.map((stock) => [stock.code, stock.name]))))
      .catch(() => undefined);
    listStrategies()
      .then((specs) => {
        setStrategies(specs);
        if (specs.length > 0) {
          setRunFormDefaults((prev) => ({
            ...prev,
            strategy_id: specs[0].id,
            strategy_params: Object.fromEntries((specs[0]?.params ?? []).map((p) => [p.name, p.default])),
          }));
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedJob) return;
    let cancelled = false;
    async function poll() {
      const latest = await getJob(selectedJob.id);
      if (cancelled) return;
      setSelectedJob((prev) => (sameJob(prev, latest) ? prev : latest));
      setJobs((prev) => prev.map((job) => (job.id === latest.id && !sameJob(job, latest) ? latest : job)));
      if (latest.status === 'completed') {
        const payload = await getResult(latest.id);
        if (!cancelled) setResult(payload);
      }
      if (latest.status === 'failed') {
        setResult(null);
      }
    }
    poll().catch((err) => setError(err.message));
    const shouldPoll = selectedJob.status === 'queued' || selectedJob.status === 'running';
    const handle = shouldPoll
      ? window.setInterval(() => {
          poll().catch((err) => setError(err.message));
        }, 1500)
      : null;
    return () => {
      cancelled = true;
      if (handle !== null) {
        window.clearInterval(handle);
      }
    };
  }, [selectedJob?.id, selectedJob?.status]);

  useEffect(() => {
    if (!comparisonJob) return;
    let cancelled = false;
    async function pollComparison() {
      const latest = await getJob(comparisonJob.id);
      if (cancelled) return;
      setComparisonJob((prev) => (sameJob(prev, latest) ? prev : latest));
      if (latest.status === 'completed') {
        const payload = await getResult(latest.id);
        if (!cancelled) setComparisonResult(payload);
      }
    }
    pollComparison().catch((err) => setError(err.message));
    const shouldPoll = comparisonJob.status === 'queued' || comparisonJob.status === 'running';
    const handle = shouldPoll
      ? window.setInterval(() => {
          pollComparison().catch((err) => setError(err.message));
        }, 1500)
      : null;
    return () => {
      cancelled = true;
      if (handle !== null) {
        window.clearInterval(handle);
      }
    };
  }, [comparisonJob?.id, comparisonJob?.status]);

  const kpis = useMemo(() => {
    if (!result) return [];
    return [
      ['Return', formatPct(result.total_return_pct)],
      ['Max Drawdown', formatPct(result.max_drawdown_pct)],
      ['胜率', formatPct(result.win_rate_pct)],
      ['Trades', String(result.trade_count)],
      ['Final Value', result.final_value.toFixed(2)],
      ['Average Score', result.market_score_summary.mean?.toFixed(2) ?? 'N/A'],
    ];
  }, [result]);

  const mergedData = useMemo(() => {
    if (!result) return [];
    const equityMap = new Map(result.equity_curve.map(e => [e.date, { ...e, type: 'equity' }]));
    const marketMap = new Map(result.market_scores.map(m => [m.date, { ...m, type: 'market' }]));

    // Add buy/sell markers from trades
    const tradeMarkers = buildTradeMarkerMap(result.trades);

    const allDates = new Set([...equityMap.keys(), ...marketMap.keys()]);
    const merged = Array.from(allDates).map(date => ({
      date,
      value: equityMap.get(date)?.value,
      total_score: marketMap.get(date)?.total_score,
      trend_score: marketMap.get(date)?.trend_score,
      sentiment_score: marketMap.get(date)?.sentiment_score,
      volume_score: marketMap.get(date)?.volume_score,
      ...tradeMarkers.get(date),
    }));

    return merged.sort((a, b) => a.date.localeCompare(b.date));
  }, [result]);

  const filteredData = useMemo(() => {
    if (!mergedData.length) return [];
    return filterByDateRange(mergedData, chartDateRange);
  }, [mergedData, chartDateRange]);

  const priceDataWithMA = useMemo(() => {
    if (!result?.price_data?.length) return [];

    const data = result.price_data;
    const closes = data.map((d) => d.close);
    const ma5 = calcMA(closes, 5);
    const ma10 = calcMA(closes, 10);
    const ma20 = calcMA(closes, 20);
    const ma60 = calcMA(closes, 60);
    const boll = calcBoll(closes, 20, 2.0);

    // Build trade markers
    const tradeMap = buildTradeMarkerMap(result.trades);

    return data.map((d, i) => ({
      ...d,
      ma5: ma5[i],
      ma10: ma10[i],
      ma20: ma20[i],
      ma60: ma60[i],
      boll_upper: boll.upper[i],
      boll_mid: boll.mid[i],
      boll_lower: boll.lower[i],
      ...tradeMap.get(d.date),
    }));
  }, [result]);

  const filteredPriceData = useMemo(() => {
    if (!priceDataWithMA.length) return [];
    return filterByDateRange(priceDataWithMA, chartDateRange);
  }, [priceDataWithMA, chartDateRange]);

  const stockIndicatorData = useMemo(() => {
    if (!priceDataWithMA.length) return [];
    const highs = priceDataWithMA.map((d) => d.high);
    const lows = priceDataWithMA.map((d) => d.low);
    const closes = priceDataWithMA.map((d) => d.close);

    if (stockSelectedIndicator === 'macd') {
      const { dif, dea, macd } = calcMacd(closes);
      return priceDataWithMA.map((d, i) => ({
        date: d.date,
        isUp: d.close >= d.open,
        dif: dif[i],
        dea: dea[i],
        macd: macd[i],
      }));
    }
    if (stockSelectedIndicator === 'kdj') {
      const { k, d, j } = calcKdj(highs, lows, closes);
      return priceDataWithMA.map((p, i) => ({
        date: p.date,
        k: k[i],
        d: d[i],
        j: j[i],
      }));
    }
    if (stockSelectedIndicator === 'volume') {
      return priceDataWithMA.map((d) => ({
        date: d.date,
        isUp: d.close >= d.open,
        value: d.volume,
      }));
    }
    return priceDataWithMA.map((d) => ({
      date: d.date,
      isUp: d.close >= d.open,
      value: (d.close * d.volume) / 1e8,
    }));
  }, [priceDataWithMA, stockSelectedIndicator]);

  const filteredStockIndicatorData = useMemo(() => {
    if (!stockIndicatorData.length) return [];
    return filterByDateRange(stockIndicatorData, chartDateRange);
  }, [stockIndicatorData, chartDateRange]);

  const indexDataWithMA = useMemo(() => {
    if (!result?.index_data?.length) return [];
    const closes = result.index_data.map((d) => d.close);
    const ma5 = calcMA(closes, 5);
    const ma10 = calcMA(closes, 10);
    const ma20 = calcMA(closes, 20);
    const ma60 = calcMA(closes, 60);
    const boll = calcBoll(closes, 20, 2.0);
    return result.index_data.map((d, i) => ({
      ...d,
      ma5: ma5[i],
      ma10: ma10[i],
      ma20: ma20[i],
      ma60: ma60[i],
      boll_upper: boll.upper[i],
      boll_mid: boll.mid[i],
      boll_lower: boll.lower[i],
    }));
  }, [result]);

  const filteredIndexData = useMemo(() => {
    if (!indexDataWithMA.length) return [];
    return filterByDateRange(indexDataWithMA, chartDateRange);
  }, [indexDataWithMA, chartDateRange]);

  const indexIndicatorData = useMemo(() => {
    if (!indexDataWithMA.length) return [];
    const highs = indexDataWithMA.map((d) => d.high);
    const lows = indexDataWithMA.map((d) => d.low);
    const closes = indexDataWithMA.map((d) => d.close);

    if (selectedIndicator === 'macd') {
      const { dif, dea, macd } = calcMacd(closes);
      return indexDataWithMA.map((d, i) => ({
        date: d.date,
        isUp: d.close >= d.open,
        dif: dif[i],
        dea: dea[i],
        macd: macd[i],
      }));
    }
    if (selectedIndicator === 'kdj') {
      const { k, d, j } = calcKdj(highs, lows, closes);
      return indexDataWithMA.map((p, i) => ({
        date: p.date,
        k: k[i],
        d: d[i],
        j: j[i],
      }));
    }
    if (selectedIndicator === 'volume') {
      return indexDataWithMA.map((d) => ({
        date: d.date,
        isUp: d.close >= d.open,
        value: d.volume,
      }));
    }
    // amount
    return indexDataWithMA.map((d) => ({
      date: d.date,
      isUp: d.close >= d.open,
      value: d.amount / 1e8,  // 杞嚎鍏?
    }));
  }, [indexDataWithMA, selectedIndicator]);

  const filteredIndicatorData = useMemo(() => {
    if (!indexIndicatorData.length) return [];
    return filterByDateRange(indexIndicatorData, chartDateRange);
  }, [indexIndicatorData, chartDateRange]);

  const klineBuyPoints = useMemo(() => filteredPriceData.filter(p => p.buy), [filteredPriceData]);
  const klineSellPoints = useMemo(() => filteredPriceData.filter(p => p.sell), [filteredPriceData]);
  const filteredPriceDataMap = useMemo(
    () => new Map(filteredPriceData.map(d => [d.date, d])),
    [filteredPriceData]
  );
  const filteredIndexDataMap = useMemo(
    () => new Map(filteredIndexData.map(d => [d.date, d])),
    [filteredIndexData]
  );

  const submit = useMemo(
    () => async (form: BacktestFormValues, force = false) => {
      setSubmitting(true);
      setError(null);
      setRunFormDefaults(form);
      try {
        const job = await createJob({ ...form, force });
        setSelectedJob(job);
        await refreshJobs();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setSubmitting(false);
      }
    },
    [refreshJobs]
  );

  const compareMarketFilter = useMemo(
    () => async () => {
      if (!selectedJob) return;
      setError(null);
      try {
        const response = await createMarketFilterComparison(selectedJob.id);
        setComparisonJob(response.comparison_job);
        setComparisonResult(null);
        await refreshJobs();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [refreshJobs, selectedJob]
  );

  const toggleLineVisibility = (line: keyof LineVisibility) => {
    setLineVisibility(prev => ({
      ...prev,
      [line]: !prev[line],
    }));
  };

  const toggleMaVisibility = (ma: keyof MaVisibility) => {
    setMaVisibility(prev => ({
      ...prev,
      [ma]: !prev[ma],
    }));
  };

  async function handleDeleteJob(jobId: number) {
    setIsDeleting(true);
    try {
      await deleteJob(jobId);
      if (selectedJob?.id === jobId) {
        setSelectedJob(null);
        setResult(null);
      }
      await refreshJobs();
      setDeleteConfirmJobId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleDeleteAllJobs() {
    setIsDeleting(true);
    try {
      await deleteAllJobs();
      setJobs([]);
      setSelectedJob(null);
      setResult(null);
      setDeleteAllConfirm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsDeleting(false);
    }
  }

  if (showGuide) {
    return <StrategyGuide onBack={() => setShowGuide(false)} />;
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <Activity size={22} />
          <div>
            <h1>QuantX</h1>
            <p>回测研究工作台</p>
          </div>
          <button className="nav-guide-btn" onClick={() => setShowGuide(true)} title="策略说明">
            <BookOpen size={16} />
            策略说明
          </button>
        </div>

        <RunForm
          initialValue={runFormDefaults}
          strategies={strategies}
          submitting={submitting}
          hasSelectedJob={Boolean(selectedJob)}
          onSubmit={submit}
          onCompareMarketFilter={compareMarketFilter}
        />

        <section className="history">
          <div className="history-header">
            <h2>历史记录</h2>
            {jobs.length > 0 && (
              <button
                className="clear-all-btn"
                onClick={() => setDeleteAllConfirm(true)}
                disabled={isDeleting || jobs.length === 0}
                title="清空历史"
              >
                清空历史
              </button>
            )}
          </div>
          {jobs.map((job) => (
            <div key={job.id} className="history-item-wrapper">
              <button className="history-item" onClick={() => setSelectedJob(job)}>
                <span>{job.symbol} {getStockName(job.symbol)} {job.start_date}-{job.end_date}</span>
                <StatusBadge status={job.status} />
              </button>
              <button
                className="delete-job-btn"
                onClick={() => setDeleteConfirmJobId(job.id)}
                disabled={isDeleting}
                title="Delete this job"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </section>
      </aside>

      <section className="content-panel">
        {error && <div className="error">{error}</div>}
        {selectedJob && (
          <div className="result-header">
            <div>
              <h2>{selectedJob.symbol} {getStockName(selectedJob.symbol)} 回测</h2>
              <p>{selectedJob.start_date} 至 {selectedJob.end_date} | {selectedJob.cache_hit ? '缓存命中' : '新任务'} | {getStrategyName(selectedJob.strategy_id)}</p>
              <p className="result-params">
                {(() => {
                  try {
                    const params = JSON.parse(selectedJob.strategy_params_json || '{}');
                    const entries = Object.entries(params);
                    if (!entries.length) return null;
                    return entries.map(([k, v]) => `${k}=${v}`).join('  ');
                  } catch { return null; }
                })()}
              </p>
            </div>
            <StatusBadge status={selectedJob.status} />
          </div>
        )}

        {result ? (
          <>
            <div className="kpi-grid">
              {kpis.map(([label, value]) => (
                <div className="kpi" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>

            {comparisonJob && (
              <section className="panel">
                <h3>市场过滤器对比</h3>
                {comparisonResult ? (
                  <div className="comparison-grid">
                    <div><span>基础收益</span><strong>{formatPct(result.total_return_pct)}</strong></div>
                    <div><span>对比收益</span><strong>{formatPct(comparisonResult.total_return_pct)}</strong></div>
                    <div><span>基础回撤</span><strong>{formatPct(result.max_drawdown_pct)}</strong></div>
                    <div><span>对比回撤</span><strong>{formatPct(comparisonResult.max_drawdown_pct)}</strong></div>
                    <div><span>基础交易</span><strong>{result.trade_count}</strong></div>
                    <div><span>对比交易</span><strong>{comparisonResult.trade_count}</strong></div>
                  </div>
                ) : (
                  <p>对比任务 #{comparisonJob.id} 状态：{statusLabels[comparisonJob.status] || comparisonJob.status}</p>
                )}
              </section>
            )}

            <EquityPanel
              data={mergedData}
              chartDateRange={chartDateRange}
              onChangeDateRange={setChartDateRange}
              defaultStart={selectedJob?.start_date || ''}
              defaultEnd={selectedJob?.end_date || ''}
              lineVisibility={lineVisibility}
              onToggleLine={toggleLineVisibility}
            />

            {result?.price_data?.length > 0 && (
              <>
              <section className="panel">
                <div className="chart-header">
                  <h3>回测股票 K 线 + MA + BOLL</h3>
                </div>

                <div className="line-toggles">
                  {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map((key) => (
                    <button
                      key={key}
                      className={`toggle-btn ${maVisibility[key] ? 'active' : ''}`}
                      onClick={() => toggleMaVisibility(key)}
                    >
                      {maVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
                      {key === 'boll' ? 'BOLL' : key.toUpperCase()}
                    </button>
                  ))}
                </div>

              <ChartDateRangeControl
                value={chartDateRange}
                defaultStart={selectedJob?.start_date || ''}
                defaultEnd={selectedJob?.end_date || ''}
                onChange={setChartDateRange}
              />

                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={400}>
                    <ComposedChart data={filteredPriceData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" minTickGap={32} />
                      <YAxis domain={[0, 'auto']} />
                      <Tooltip
                        formatter={(value: any, name: string) => {
                          if (name === 'MA5') return [value?.toFixed(2), 'MA5'];
                          if (name === 'MA10') return [value?.toFixed(2), 'MA10'];
                          if (name === 'MA20') return [value?.toFixed(2), 'MA20'];
                          if (name === 'MA60') return [value?.toFixed(2), 'MA60'];
                          if (typeof value === 'number') return [value.toFixed(2), name];
                          return [value, name];
                        }}
                        labelFormatter={(label: string) => {
                          const point = filteredPriceDataMap.get(label);
                          if (!point) return label;
                          return `${label} | O:${point.open?.toFixed(2)} H:${point.high?.toFixed(2)} L:${point.low?.toFixed(2)} C:${point.close?.toFixed(2)}`;
                        }}
                      />
                      <Legend />
                      <Bar
                        dataKey="close"
                        shape={CandleShape}
                        isAnimationActive={false}
                        legendType="none"
                      />
                      {maVisibility.ma5 && (
                        <Line
                          type="monotone"
                          dataKey="ma5"
                          stroke="#ef4444"
                          dot={false}
                          strokeWidth={1.5}
                          name="MA5"
                          isAnimationActive={false}
                          connectNulls={false}
                        />
                      )}
                      {maVisibility.ma10 && (
                        <Line
                          type="monotone"
                          dataKey="ma10"
                          stroke="#f59e0b"
                          dot={false}
                          strokeWidth={1.5}
                          name="MA10"
                          isAnimationActive={false}
                          connectNulls={false}
                        />
                      )}
                      {maVisibility.ma20 && (
                        <Line
                          type="monotone"
                          dataKey="ma20"
                          stroke="#2563eb"
                          dot={false}
                          strokeWidth={1.5}
                          name="MA20"
                          isAnimationActive={false}
                          connectNulls={false}
                        />
                      )}
                      {maVisibility.ma60 && (
                        <Line
                          type="monotone"
                          dataKey="ma60"
                          stroke="#7c3aed"
                          dot={false}
                          strokeWidth={1.5}
                          name="MA60"
                          isAnimationActive={false}
                          connectNulls={false}
                        />
                      )}
                      {maVisibility.boll && (
                        <>
                          <Line type="monotone" dataKey="boll_upper" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 上轨" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="boll_mid" stroke="#eab308" dot={false} strokeWidth={1.2} name="BOLL 中轨" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="boll_lower" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 下轨" isAnimationActive={false} connectNulls={false} />
                        </>
                      )}
                      {klineBuyPoints.map((point) => (
                        <ReferenceDot
                          key={`kline-buy-${point.date}`}
                          x={point.date}
                          y={point.low}
                          shape={BuyMarker}
                          ifOverflow="extendDomain"
                        />
                      ))}
                      {klineSellPoints.map((point) => (
                        <ReferenceDot
                          key={`kline-sell-${point.date}`}
                          x={point.date}
                          y={point.high}
                          shape={SellMarker}
                          ifOverflow="extendDomain"
                        />
                      ))}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                <div className="trade-legend">
                  <div className="trade-legend-item">
                    <div className="trade-legend-dot buy"></div>
                    <span>买入点</span>
                  </div>
                  <div className="trade-legend-item">
                    <div className="trade-legend-dot sell"></div>
                    <span>卖出点</span>
                  </div>
                </div>
              </section>
              <section className="panel">
                <div className="chart-header">
                  <h3>回测股票技术指标</h3>
                  <select
                    value={stockSelectedIndicator}
                    onChange={(e) => setStockSelectedIndicator(e.target.value as IndicatorKey)}
                    style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #cbd5df', background: '#fff' }}
                  >
                    <option value="macd">MACD</option>
                    <option value="kdj">KDJ</option>
                    <option value="volume">Volume</option>
                    <option value="amount">Amount (100M CNY)</option>
                  </select>
                </div>

                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={filteredStockIndicatorData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" minTickGap={32} />
                      <YAxis domain={['auto', 'auto']} />
                      <Tooltip />
                      {stockSelectedIndicator === 'macd' && (
                        <>
                          <Bar dataKey="macd" isAnimationActive={false} name="MACD">
                            {filteredStockIndicatorData.map((entry, i) => (
                              <Cell key={`stock-m-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                            ))}
                          </Bar>
                          <Line type="monotone" dataKey="dif" stroke="#facc15" dot={false} strokeWidth={1.4} name="DIF" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="dea" stroke="#f97316" dot={false} strokeWidth={1.4} name="DEA" isAnimationActive={false} connectNulls={false} />
                        </>
                      )}
                      {stockSelectedIndicator === 'kdj' && (
                        <>
                          <Line type="monotone" dataKey="k" stroke="#f3f4f6" dot={false} strokeWidth={1.4} name="K" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="d" stroke="#facc15" dot={false} strokeWidth={1.4} name="D" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="j" stroke="#a855f7" dot={false} strokeWidth={1.4} name="J" isAnimationActive={false} connectNulls={false} />
                          <ReferenceLine y={80} stroke="#9ca3af" strokeDasharray="2 2" />
                          <ReferenceLine y={20} stroke="#9ca3af" strokeDasharray="2 2" />
                        </>
                      )}
                      {stockSelectedIndicator === 'volume' && (
                        <Bar dataKey="value" isAnimationActive={false} name="Volume">
                          {filteredStockIndicatorData.map((entry, i) => (
                            <Cell key={`stock-v-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                          ))}
                        </Bar>
                      )}
                      {stockSelectedIndicator === 'amount' && (
                        <Bar dataKey="value" isAnimationActive={false} name="Amount">
                          {filteredStockIndicatorData.map((entry, i) => (
                            <Cell key={`stock-a-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                          ))}
                        </Bar>
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </section>
              </>
            )}

            {result && (
              (result.index_data?.length ?? 0) > 0 ? (
                <>
                <section className="panel">
                  <div className="chart-header">
                    <h3>上证指数 K 线 + MA + BOLL</h3>
                  </div>

                <div className="line-toggles">
                  {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map((key) => (
                    <button
                      key={key}
                      className={`toggle-btn ${indexMaVisibility[key] ? 'active' : ''}`}
                      onClick={() => toggleIndexMa(key)}
                    >
                      {indexMaVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
                      {key === 'boll' ? 'BOLL' : key.toUpperCase()}
                    </button>
                  ))}
                </div>

              <ChartDateRangeControl
                value={chartDateRange}
                defaultStart={selectedJob?.start_date || ''}
                defaultEnd={selectedJob?.end_date || ''}
                onChange={setChartDateRange}
              />

                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={400}>
                    <ComposedChart data={filteredIndexData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" minTickGap={32} />
                      <YAxis domain={['auto', 'auto']} />
                      <Tooltip
                        formatter={(value: any, name: string) => {
                          if (value == null) return ['--', name];
                          if (typeof value === 'number') return [value.toFixed(2), name];
                          return [value, name];
                        }}
                        labelFormatter={(label: string) => {
                          const point = filteredIndexDataMap.get(label);
                          if (!point) return label;
                          return `${label} | O:${point.open.toFixed(2)} H:${point.high.toFixed(2)} L:${point.low.toFixed(2)} C:${point.close.toFixed(2)}`;
                        }}
                      />
                      <Legend />
                      <Bar dataKey="close" shape={CandleShape} isAnimationActive={false} legendType="none" />
                      {indexMaVisibility.ma5 && (
                        <Line type="monotone" dataKey="ma5" stroke="#ef4444" dot={false} strokeWidth={1.5} name="MA5" isAnimationActive={false} connectNulls={false} />
                      )}
                      {indexMaVisibility.ma10 && (
                        <Line type="monotone" dataKey="ma10" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="MA10" isAnimationActive={false} connectNulls={false} />
                      )}
                      {indexMaVisibility.ma20 && (
                        <Line type="monotone" dataKey="ma20" stroke="#2563eb" dot={false} strokeWidth={1.5} name="MA20" isAnimationActive={false} connectNulls={false} />
                      )}
                      {indexMaVisibility.ma60 && (
                        <Line type="monotone" dataKey="ma60" stroke="#7c3aed" dot={false} strokeWidth={1.5} name="MA60" isAnimationActive={false} connectNulls={false} />
                      )}
                      {indexMaVisibility.boll && (
                        <>
                          <Line type="monotone" dataKey="boll_upper" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL上轨" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="boll_mid" stroke="#eab308" dot={false} strokeWidth={1.2} name="BOLL中轨" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="boll_lower" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL下轨" isAnimationActive={false} connectNulls={false} />
                        </>
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="panel">
                <div className="chart-header">
                  <h3>上证指数技术指标</h3>
                  <select
                    value={selectedIndicator}
                    onChange={(e) => setSelectedIndicator(e.target.value as IndicatorKey)}
                    style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #cbd5df', background: '#fff' }}
                  >
                    <option value="macd">MACD</option>
                    <option value="kdj">KDJ</option>
                    <option value="volume">Volume</option>
                    <option value="amount">Amount (100M CNY)</option>
                  </select>
                </div>

                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={filteredIndicatorData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" minTickGap={32} />
                      <YAxis domain={['auto', 'auto']} />
                      <Tooltip />
                      {selectedIndicator === 'macd' && (
                        <>
                          <Bar dataKey="macd" isAnimationActive={false} name="MACD">
                            {filteredIndicatorData.map((entry, i) => (
                              <Cell key={`m-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                            ))}
                          </Bar>
                          <Line type="monotone" dataKey="dif" stroke="#facc15" dot={false} strokeWidth={1.4} name="DIF" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="dea" stroke="#f97316" dot={false} strokeWidth={1.4} name="DEA" isAnimationActive={false} connectNulls={false} />
                        </>
                      )}
                      {selectedIndicator === 'kdj' && (
                        <>
                          <Line type="monotone" dataKey="k" stroke="#f3f4f6" dot={false} strokeWidth={1.4} name="K" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="d" stroke="#facc15" dot={false} strokeWidth={1.4} name="D" isAnimationActive={false} connectNulls={false} />
                          <Line type="monotone" dataKey="j" stroke="#a855f7" dot={false} strokeWidth={1.4} name="J" isAnimationActive={false} connectNulls={false} />
                          <ReferenceLine y={80} stroke="#9ca3af" strokeDasharray="2 2" />
                          <ReferenceLine y={20} stroke="#9ca3af" strokeDasharray="2 2" />
                        </>
                      )}
                      {selectedIndicator === 'volume' && (
                        <Bar dataKey="value" isAnimationActive={false} name="Volume">
                          {filteredIndicatorData.map((entry, i) => (
                            <Cell key={`v-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                          ))}
                        </Bar>
                      )}
                      {selectedIndicator === 'amount' && (
                        <Bar dataKey="value" isAnimationActive={false} name="Amount">
                          {filteredIndicatorData.map((entry, i) => (
                            <Cell key={`a-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                          ))}
                        </Bar>
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </section>
              </>
              ) : (
                <section className="panel">
                  <h3>上证指数</h3>
                  <p style={{ color: '#627282' }}>
                    上证指数数据加载失败，可能是网络或数据源问题，请重试回测。
                  </p>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => selectedJob && submit(runFormDefaults, true)}
                    disabled={submitting || !selectedJob}
                  >
                    <RefreshCcw size={16} /> 重新运行
                  </button>
                </section>
              )
            )}

            <section className="panel">
              <h3>交易记录</h3>
              <table>
                <thead><tr><th>日期</th><th>盈亏</th><th>盈亏(含手续费)</th><th>持仓周期</th></tr></thead>
                <tbody>
                  {result.trades.map((trade, index) => (
                    <tr key={`${trade.date}-${index}`}>
                      <td>{trade.date}</td>
                      <td>{trade.pnl.toFixed(2)}</td>
                      <td>{trade.pnlcomm.toFixed(2)}</td>
                      <td>{trade.barlen}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        ) : (
          <div className="empty-state">提交任务或选择已完成任务后可查看结果。</div>
        )}
      </section>

      {deleteConfirmJobId !== null && (
        <div className="modal-overlay" onClick={() => setDeleteConfirmJobId(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>确认删除</h3>
            <p>确定要删除这个回测任务吗？此操作无法撤销。</p>
            <div className="modal-buttons">
              <button
                className="modal-cancel"
                onClick={() => setDeleteConfirmJobId(null)}
                disabled={isDeleting}
              >
                取消
              </button>
              <button
                className="modal-delete"
                onClick={() => handleDeleteJob(deleteConfirmJobId)}
                disabled={isDeleting}
              >
                {isDeleting ? '删除中...' : '删除'}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteAllConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteAllConfirm(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>清空历史</h3>
            <p>确定要删除所有回测任务吗？此操作无法撤销。</p>
            <div className="modal-buttons">
              <button
                className="modal-cancel"
                onClick={() => setDeleteAllConfirm(false)}
                disabled={isDeleting}
              >
                取消
              </button>
              <button
                className="modal-delete"
                onClick={handleDeleteAllJobs}
                disabled={isDeleting}
              >
                {isDeleting ? '删除中...' : '删除全部'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

