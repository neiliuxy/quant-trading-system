import { useEffect, useMemo, useState } from 'react';
import { Activity, BookOpen, Play, RefreshCcw, ZoomIn, ZoomOut, Eye, EyeOff, Trash2 } from 'lucide-react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { createJob, createMarketFilterComparison, deleteJob, deleteAllJobs, getJob, getResult, listJobs, listStrategies } from './api';
import type { BacktestResult, Job, StrategySpec } from './types';
import { StockSelect } from './StockSelect';
import { STOCKS } from './stocks';
import StrategyParamsForm from './StrategyParamsForm';
import StrategyGuide from './StrategyGuide';

const defaultForm = {
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

function formatDateForInput(dateStr: string): string {
  if (!dateStr || dateStr.length !== 8) return '';
  return `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
}

function formatDateFromInput(dateStr: string): string {
  if (!dateStr) return '';
  return dateStr.replace(/-/g, '');
}

function formatPct(value: number) {
  return `${value.toFixed(2)}%`;
}

function getStockName(code: string): string {
  const stock = STOCKS.find(s => s.code === code);
  return stock ? stock.name : code;
}

const statusLabels: Record<string, string> = {
  'queued': '等待中',
  'running': '运行中',
  'completed': '已完成',
  'failed': '失败',
};

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{statusLabels[status] || status}</span>;
}

function createCandleShape(chartHeight: number) {
  return function CandleShape(props: any) {
    const { x, width, payload } = props;
    const { open, close, highY, lowY, openY, closeY } = payload;
    if (open === undefined) return null;

    const isUp = close >= open;
    const color = isUp ? '#ef4444' : '#22c55e';
    const cx = x + width / 2;
    const h = chartHeight;

    const wickTop = h * highY;
    const wickBottom = h * lowY;
    const bodyTop = h * (isUp ? closeY : openY);
    const bodyBottom = h * (isUp ? openY : closeY);

    return (
      <g>
        <line x1={cx} y1={wickTop} x2={cx} y2={wickBottom} stroke={color} strokeWidth={1} />
        <rect
          x={cx - 3}
          y={bodyTop}
          width={6}
          height={Math.max(1, bodyBottom - bodyTop)}
          fill={isUp ? color : 'transparent'}
          stroke={color}
          strokeWidth={1}
        />
      </g>
    );
  };
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

interface LineVisibility {
  equity: boolean;
  totalScore: boolean;
  trendScore: boolean;
  sentimentScore: boolean;
  volumeScore: boolean;
}

interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
}

export default function App() {
  const [form, setForm] = useState(defaultForm);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [strategies, setStrategies] = useState<StrategySpec[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState('swing_ma_boll');
  const [comparisonJob, setComparisonJob] = useState<Job | null>(null);
  const [comparisonResult, setComparisonResult] = useState<BacktestResult | null>(null);
  const [zoom, setZoom] = useState({ start: 0, end: 100 });
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
  });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState(0);
  const [chartDateRange, setChartDateRange] = useState<{ start: string; end: string } | null>(null);
  const [deleteConfirmJobId, setDeleteConfirmJobId] = useState<number | null>(null);
  const [deleteAllConfirm, setDeleteAllConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

  const selectedStrategy = useMemo(
    () => strategies.find((s) => s.id === selectedStrategyId) ?? strategies[0],
    [strategies, selectedStrategyId]
  );

  function getStrategyName(id: string): string {
    const found = strategies.find(s => s.id === id);
    return found?.name ?? id;
  }

  async function refreshJobs() {
    const rows = await listJobs();
    setJobs(rows);
    if (!selectedJob && rows.length > 0) {
      setSelectedJob(rows[0]);
    }
  }

  useEffect(() => {
    refreshJobs().catch((err) => setError(err.message));
    listStrategies()
      .then((specs) => {
        setStrategies(specs);
        if (specs.length > 0) {
          setForm((prev) => ({ ...prev, strategy_params: Object.fromEntries(
            (specs[0]?.params ?? []).map((p) => [p.name, p.default])
          ) }));
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
      setSelectedJob(latest);
      setJobs((prev) => prev.map((job) => (job.id === latest.id ? latest : job)));
      if (latest.status === 'completed') {
        const payload = await getResult(latest.id);
        if (!cancelled) setResult(payload);
      }
      if (latest.status === 'failed') {
        setResult(null);
      }
    }
    poll().catch((err) => setError(err.message));
    const handle = window.setInterval(() => {
      poll().catch((err) => setError(err.message));
    }, selectedJob.status === 'queued' || selectedJob.status === 'running' ? 1500 : 6000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [selectedJob?.id]);

  useEffect(() => {
    if (!comparisonJob) return;
    let cancelled = false;
    async function pollComparison() {
      const latest = await getJob(comparisonJob.id);
      if (cancelled) return;
      setComparisonJob(latest);
      if (latest.status === 'completed') {
        const payload = await getResult(latest.id);
        if (!cancelled) setComparisonResult(payload);
      }
    }
    pollComparison().catch((err) => setError(err.message));
    const handle = window.setInterval(() => {
      pollComparison().catch((err) => setError(err.message));
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [comparisonJob?.id]);

  const kpis = useMemo(() => {
    if (!result) return [];
    return [
      ['收益率', formatPct(result.total_return_pct)],
      ['最大回撤', formatPct(result.max_drawdown_pct)],
      ['胜率', formatPct(result.win_rate_pct)],
      ['交易数', String(result.trade_count)],
      ['最终价值', result.final_value.toFixed(2)],
      ['评分均值', result.market_score_summary.mean?.toFixed(2) ?? 'N/A'],
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

    let data = mergedData;

    // Filter by chart date range if set
    if (chartDateRange?.start && chartDateRange?.end) {
      data = data.filter(d => d.date >= chartDateRange.start && d.date <= chartDateRange.end);
    } else {
      // Otherwise use zoom percentage
      const start = Math.floor((mergedData.length * zoom.start) / 100);
      const end = Math.ceil((mergedData.length * zoom.end) / 100);
      data = mergedData.slice(start, end);
    }

    return data;
  }, [mergedData, zoom, chartDateRange]);

  const priceDataWithMA = useMemo(() => {
    if (!result?.price_data?.length) return [];

    const data = result.price_data;

    // Calculate simple moving averages
    function calcMA(period: number): (number | null)[] {
      return data.map((_, i) => {
        if (i < period - 1) return null;
        let sum = 0;
        for (let j = 0; j < period; j++) sum += data[i - j].close;
        return parseFloat((sum / period).toFixed(2));
      });
    }

    const ma5 = calcMA(5);
    const ma10 = calcMA(10);
    const ma20 = calcMA(20);
    const ma60 = calcMA(60);

    // Price range for candle mapping
    const lows = data.map(d => d.low);
    const highs = data.map(d => d.high);
    const minPrice = Math.min(...lows) * 0.98;
    const maxPrice = Math.max(...highs) * 1.02;
    const priceRange = maxPrice - minPrice || 1;

    // Build trade markers
    const tradeMap = buildTradeMarkerMap(result.trades);

    return data.map((d, i) => ({
      ...d,
      ma5: ma5[i],
      ma10: ma10[i],
      ma20: ma20[i],
      ma60: ma60[i],
      highY: (maxPrice - d.high) / priceRange,
      lowY: (maxPrice - d.low) / priceRange,
      openY: (maxPrice - d.open) / priceRange,
      closeY: (maxPrice - d.close) / priceRange,
      ...tradeMap.get(d.date),
    }));
  }, [result]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart(e.clientX);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const delta = e.clientX - dragStart;
    const range = zoom.end - zoom.start;
    const movePercent = (delta / 800) * 100; // 800px is approximate chart width

    let newStart = zoom.start - movePercent;
    let newEnd = zoom.end - movePercent;

    if (newStart < 0) {
      newStart = 0;
      newEnd = range;
    }
    if (newEnd > 100) {
      newEnd = 100;
      newStart = 100 - range;
    }

    setZoom({ start: newStart, end: newEnd });
    setDragStart(e.clientX);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  async function submit(force = false) {
    setSubmitting(true);
    setError(null);
    try {
      const job = await createJob({ ...form, force });
      setSelectedJob(job);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function compareMarketFilter() {
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
  }

  async function handleStrategyChange(id: string) {
    setSelectedStrategyId(id);
    const spec = strategies.find((s) => s.id === id);
    if (spec) {
      const defaults = Object.fromEntries(
        spec.params.map((p) => [p.name, p.default])
      );
      setForm((prev) => ({ ...prev, strategy_id: id, strategy_params: defaults }));
    }
  }

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
          <button className="nav-guide-btn" onClick={() => setShowGuide(true)} title="策略库">
            <BookOpen size={16} />
            策略库
          </button>
        </div>

        <form className="run-form" onSubmit={(event) => { event.preventDefault(); submit(false); }}>
          <label>代码
            <StockSelect
              value={form.symbol}
              onChange={(code) => setForm({ ...form, symbol: code })}
            />
          </label>
          <label>开始日期
            <input
              type="date"
              value={formatDateForInput(form.start)}
              onChange={(e) => setForm({ ...form, start: formatDateFromInput(e.target.value) })}
            />
          </label>
          <label>结束日期
            <input
              type="date"
              value={formatDateForInput(form.end)}
              onChange={(e) => setForm({ ...form, end: formatDateFromInput(e.target.value) })}
              min={formatDateForInput(form.start)}
            />
          </label>
          <label>初始资金<input type="number" value={form.cash} onChange={(e) => setForm({ ...form, cash: Number(e.target.value) })} /></label>
          <label className="check-row">
            <input type="checkbox" checked={form.use_market_filter} onChange={(e) => setForm({ ...form, use_market_filter: e.target.checked })} />
            市场过滤器
          </label>
          <label>策略
            <select
              value={selectedStrategyId}
              onChange={(e) => handleStrategyChange(e.target.value)}
            >
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
          {selectedStrategy && (
            <StrategyParamsForm
              spec={selectedStrategy}
              value={form.strategy_params}
              onChange={(params) => setForm((prev) => ({ ...prev, strategy_params: params }))}
            />
          )}
          <button className="primary" type="submit" disabled={submitting}>
            <Play size={16} /> 开始回测
          </button>
          <button className="secondary" type="button" onClick={() => submit(true)} disabled={submitting || !selectedJob}>
            <RefreshCcw size={16} /> 强制重新运行
          </button>
          <button className="secondary" type="button" onClick={compareMarketFilter} disabled={!selectedJob}>
            对比过滤器
          </button>
        </form>

        <section className="history">
          <div className="history-header">
            <h2>历史记录</h2>
            {jobs.length > 0 && (
              <button
                className="clear-all-btn"
                onClick={() => setDeleteAllConfirm(true)}
                disabled={isDeleting || jobs.length === 0}
                title="Clear all history"
              >
                清空历史
              </button>
            )}
          </div>
          {jobs.map((job) => (
            <div key={job.id} className="history-item-wrapper">
              <button className="history-item" onClick={() => setSelectedJob(job)}>
                <span>{job.symbol} {job.start_date}-{job.end_date}</span>
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
              <p>{selectedJob.start_date} 至 {selectedJob.end_date} · {selectedJob.cache_hit ? '缓存命中' : '新任务'} · {getStrategyName(selectedJob.strategy_id)}</p>
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

            <section className="panel">
              <div className="chart-header">
                <h3>权益曲线 & 市场评分</h3>
                <div className="zoom-controls">
                  <button
                    className="zoom-btn"
                    onClick={() => setZoom({ start: Math.max(0, zoom.start - 10), end: Math.min(100, zoom.end + 10) })}
                    title="缩小（显示更多数据）"
                  >
                    <ZoomOut size={16} /> 缩小
                  </button>
                  <button
                    className="zoom-btn"
                    onClick={() => setZoom({ start: Math.min(50, zoom.start + 10), end: Math.max(50, zoom.end - 10) })}
                    title="放大（显示更少数据）"
                  >
                    <ZoomIn size={16} /> 放大
                  </button>
                  <button
                    className="zoom-btn"
                    onClick={() => setZoom({ start: 0, end: 100 })}
                    title="重置"
                  >
                    重置
                  </button>
                </div>
              </div>

              <div className="line-toggles">
                <button
                  className={`toggle-btn ${lineVisibility.equity ? 'active' : ''}`}
                  onClick={() => toggleLineVisibility('equity')}
                  title="Toggle equity curve"
                >
                  {lineVisibility.equity ? <Eye size={14} /> : <EyeOff size={14} />}
                  权益价值
                </button>
                <button
                  className={`toggle-btn ${lineVisibility.totalScore ? 'active' : ''}`}
                  onClick={() => toggleLineVisibility('totalScore')}
                  title="Toggle total score"
                >
                  {lineVisibility.totalScore ? <Eye size={14} /> : <EyeOff size={14} />}
                  总评分
                </button>
                <button
                  className={`toggle-btn ${lineVisibility.trendScore ? 'active' : ''}`}
                  onClick={() => toggleLineVisibility('trendScore')}
                  title="Toggle trend score"
                >
                  {lineVisibility.trendScore ? <Eye size={14} /> : <EyeOff size={14} />}
                  趋势评分
                </button>
                <button
                  className={`toggle-btn ${lineVisibility.sentimentScore ? 'active' : ''}`}
                  onClick={() => toggleLineVisibility('sentimentScore')}
                  title="Toggle sentiment score"
                >
                  {lineVisibility.sentimentScore ? <Eye size={14} /> : <EyeOff size={14} />}
                  情绪评分
                </button>
                <button
                  className={`toggle-btn ${lineVisibility.volumeScore ? 'active' : ''}`}
                  onClick={() => toggleLineVisibility('volumeScore')}
                  title="Toggle volume score"
                >
                  {lineVisibility.volumeScore ? <Eye size={14} /> : <EyeOff size={14} />}
                  成交量评分
                </button>
              </div>

              <div className="chart-date-range">
                <label>显示时间范围
                  <div className="date-range-inputs">
                    <input
                      type="date"
                      value={chartDateRange?.start ? formatDateForInput(chartDateRange.start) : formatDateForInput(selectedJob?.start_date || '')}
                      onChange={(e) => {
                        const start = formatDateFromInput(e.target.value);
                        setChartDateRange(prev => ({
                          start,
                          end: prev?.end || formatDateFromInput(selectedJob?.end_date || ''),
                        }));
                      }}
                      min={formatDateForInput(selectedJob?.start_date || '')}
                      max={formatDateForInput(selectedJob?.end_date || '')}
                    />
                    <span>至</span>
                    <input
                      type="date"
                      value={chartDateRange?.end ? formatDateForInput(chartDateRange.end) : formatDateForInput(selectedJob?.end_date || '')}
                      onChange={(e) => {
                        const end = formatDateFromInput(e.target.value);
                        setChartDateRange(prev => ({
                          start: prev?.start || formatDateFromInput(selectedJob?.start_date || ''),
                          end,
                        }));
                      }}
                      min={formatDateForInput(selectedJob?.start_date || '')}
                      max={formatDateForInput(selectedJob?.end_date || '')}
                    />
                    <button
                      className="reset-date-btn"
                      onClick={() => setChartDateRange(null)}
                      title="Reset to full range"
                    >
                      重置
                    </button>
                  </div>
                </label>
              </div>

              <div
                className="chart-container"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
              >
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={filteredData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" minTickGap={32} />
                    <YAxis yAxisId="left" domain={['auto', 'auto']} />
                    <YAxis yAxisId="right" orientation="right" domain={[0, 1]} />
                    <Tooltip />
                    <Legend />
                    {lineVisibility.equity && (
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="value"
                        stroke="#2563eb"
                        dot={false}
                        strokeWidth={2}
                        name="权益价值"
                        isAnimationActive={false}
                      />
                    )}
                    {lineVisibility.totalScore && (
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="total_score"
                        stroke="#0f766e"
                        dot={false}
                        strokeWidth={2}
                        name="总评分"
                        isAnimationActive={false}
                      />
                    )}
                    {lineVisibility.trendScore && (
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="trend_score"
                        stroke="#f59e0b"
                        dot={false}
                        name="趋势评分"
                        isAnimationActive={false}
                      />
                    )}
                    {lineVisibility.sentimentScore && (
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="sentiment_score"
                        stroke="#7c3aed"
                        dot={false}
                        name="情绪评分"
                        isAnimationActive={false}
                      />
                    )}
                    {lineVisibility.volumeScore && (
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="volume_score"
                        stroke="#dc2626"
                        dot={false}
                        name="成交量评分"
                        isAnimationActive={false}
                      />
                    )}
                    {filteredData.map((point, index) => (
                      point.buy && (
                        <ReferenceDot
                          key={`buy-${index}`}
                          x={point.date}
                          y={point.value}
                          yAxisId="left"
                          r={5}
                          fill="#22c55e"
                          stroke="#16a34a"
                          strokeWidth={2}
                        />
                      )
                    ))}
                    {filteredData.map((point, index) => (
                      point.sell && (
                        <ReferenceDot
                          key={`sell-${index}`}
                          x={point.date}
                          y={point.value}
                          yAxisId="left"
                          r={5}
                          fill="#ef4444"
                          stroke="#dc2626"
                          strokeWidth={2}
                        />
                      )
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="chart-hint">提示：拖动图表左右移动查看附近时间段的数据</p>
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

            {result?.price_data?.length > 0 && (
              <section className="panel">
                <div className="chart-header">
                  <h3>K 线图 & MA 均线</h3>
                </div>

                <div className="line-toggles">
                  <button
                    className={`toggle-btn ${maVisibility.ma5 ? 'active' : ''}`}
                    onClick={() => toggleMaVisibility('ma5')}
                  >
                    {maVisibility.ma5 ? <Eye size={14} /> : <EyeOff size={14} />}
                    MA5
                  </button>
                  <button
                    className={`toggle-btn ${maVisibility.ma10 ? 'active' : ''}`}
                    onClick={() => toggleMaVisibility('ma10')}
                  >
                    {maVisibility.ma10 ? <Eye size={14} /> : <EyeOff size={14} />}
                    MA10
                  </button>
                  <button
                    className={`toggle-btn ${maVisibility.ma20 ? 'active' : ''}`}
                    onClick={() => toggleMaVisibility('ma20')}
                  >
                    {maVisibility.ma20 ? <Eye size={14} /> : <EyeOff size={14} />}
                    MA20
                  </button>
                  <button
                    className={`toggle-btn ${maVisibility.ma60 ? 'active' : ''}`}
                    onClick={() => toggleMaVisibility('ma60')}
                  >
                    {maVisibility.ma60 ? <Eye size={14} /> : <EyeOff size={14} />}
                    MA60
                  </button>
                </div>

                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={400}>
                    <ComposedChart data={priceDataWithMA} margin={{ top: 0, bottom: 0, left: 0, right: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" minTickGap={32} />
                      <YAxis domain={['auto', 'auto']} />
                      <Tooltip
                        formatter={(value: any, name: string) => {
                          if (name === 'MA5') return [value?.toFixed(2), 'MA5'];
                          if (name === 'MA10') return [value?.toFixed(2), 'MA10'];
                          if (name === 'MA20') return [value?.toFixed(2), 'MA20'];
                          if (name === 'MA60') return [value?.toFixed(2), 'MA60'];
                          return [value, name];
                        }}
                        labelFormatter={(label: string) => {
                          const point = priceDataWithMA.find(d => d.date === label);
                          if (!point) return label;
                          return `${label} | O:${point.open?.toFixed(2)} H:${point.high?.toFixed(2)} L:${point.low?.toFixed(2)} C:${point.close?.toFixed(2)}`;
                        }}
                      />
                      <Legend />
                      <Bar
                        dataKey="close"
                        shape={createCandleShape(400)}
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
                      {priceDataWithMA.map((point, index) => (
                        point.buy && (
                          <ReferenceDot
                            key={`kline-buy-${index}`}
                            x={point.date}
                            y={point.close}
                            r={5}
                            fill="#22c55e"
                            stroke="#16a34a"
                            strokeWidth={2}
                          />
                        )
                      ))}
                      {priceDataWithMA.map((point, index) => (
                        point.sell && (
                          <ReferenceDot
                            key={`kline-sell-${index}`}
                            x={point.date}
                            y={point.close}
                            r={5}
                            fill="#ef4444"
                            stroke="#dc2626"
                            strokeWidth={2}
                          />
                        )
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
          <div className="empty-state">提交或选择已完成的任务以查看结果。</div>
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
            <h3>清空所有历史</h3>
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
