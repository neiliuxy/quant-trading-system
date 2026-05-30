import { useEffect, useMemo, useState } from 'react';
import { Activity, Play, RefreshCcw, ZoomIn, ZoomOut, Eye, EyeOff } from 'lucide-react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ComposedChart,
  ReferenceDot,
} from 'recharts';
import { createJob, createMarketFilterComparison, getJob, getResult, listJobs } from './api';
import type { BacktestResult, Job } from './types';
import { StockSelect } from './StockSelect';
import { STOCKS } from './stocks';

const defaultForm = {
  symbol: '000001',
  start: '20230530',
  end: '20260530',
  cash: 100000,
  use_market_filter: true,
  risk_percent: 0.95,
  fast_ma: 10,
  slow_ma: 20,
};

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

interface LineVisibility {
  equity: boolean;
  totalScore: boolean;
  trendScore: boolean;
  sentimentScore: boolean;
  volumeScore: boolean;
}

export default function App() {
  const [form, setForm] = useState(defaultForm);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [comparisonJob, setComparisonJob] = useState<Job | null>(null);
  const [comparisonResult, setComparisonResult] = useState<BacktestResult | null>(null);
  const [zoom, setZoom] = useState({ start: 0, end: 100 });
  const [lineVisibility, setLineVisibility] = useState<LineVisibility>({
    equity: true,
    totalScore: true,
    trendScore: true,
    sentimentScore: true,
    volumeScore: true,
  });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState(0);

  async function refreshJobs() {
    const rows = await listJobs();
    setJobs(rows);
    if (!selectedJob && rows.length > 0) {
      setSelectedJob(rows[0]);
    }
  }

  useEffect(() => {
    refreshJobs().catch((err) => setError(err.message));
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
    const tradeMarkers = new Map<string, { buy?: boolean; sell?: boolean }>();
    result.trades.forEach((trade, index) => {
      if (!tradeMarkers.has(trade.date)) {
        tradeMarkers.set(trade.date, {});
      }
      const marker = tradeMarkers.get(trade.date)!;
      // Odd index = buy, even index = sell (or vice versa depending on your logic)
      if (index % 2 === 0) {
        marker.buy = true;
      } else {
        marker.sell = true;
      }
    });

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
    const start = Math.floor((mergedData.length * zoom.start) / 100);
    const end = Math.ceil((mergedData.length * zoom.end) / 100);
    return mergedData.slice(start, end);
  }, [mergedData, zoom]);

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

  const toggleLineVisibility = (line: keyof LineVisibility) => {
    setLineVisibility(prev => ({
      ...prev,
      [line]: !prev[line],
    }));
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <Activity size={22} />
          <div>
            <h1>QuantX</h1>
            <p>回测研究工作台</p>
          </div>
        </div>

        <form className="run-form" onSubmit={(event) => { event.preventDefault(); submit(false); }}>
          <label>代码
            <select value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })}>
              <option value="">选择股票...</option>
              <option value="000001">000001 - 平安银行</option>
              <option value="000002">000002 - 万科A</option>
              <option value="000333">000333 - 美的集团</option>
              <option value="000858">000858 - 五粮液</option>
              <option value="000651">000651 - 格力电器</option>
              <option value="600000">600000 - 浦发银行</option>
              <option value="600016">600016 - 民生银行</option>
              <option value="600028">600028 - 中国石化</option>
              <option value="600029">600029 - 南方航空</option>
              <option value="600031">600031 - 三一重工</option>
              <option value="600036">600036 - 招商银行</option>
              <option value="600048">600048 - 保利地产</option>
              <option value="600050">600050 - 中国联通</option>
              <option value="600104">600104 - 上汽集团</option>
              <option value="600109">600109 - 国金证券</option>
              <option value="600111">600111 - 北京控股</option>
              <option value="600115">600115 - 中国东航</option>
              <option value="600118">600118 - 中国卫星</option>
              <option value="600123">600123 - 兰花科创</option>
              <option value="600132">600132 - 重庆啤酒</option>
              <option value="600138">600138 - 中青旅</option>
              <option value="600143">600143 - 金发科技</option>
              <option value="600150">600150 - 中国船舶</option>
              <option value="600161">600161 - 天坛生物</option>
              <option value="600170">600170 - 上海建工</option>
              <option value="600176">600176 - 中国巨石</option>
              <option value="600188">600188 - 兖州煤业</option>
              <option value="600196">600196 - 复星医药</option>
              <option value="600208">600208 - 新华制药</option>
              <option value="600219">600219 - 南山铝业</option>
              <option value="600221">600221 - 海南航空</option>
              <option value="600233">600233 - 圆通速递</option>
              <option value="600276">600276 - 恒瑞医药</option>
              <option value="600297">600297 - 广汇汽车</option>
              <option value="600309">600309 - 万华化学</option>
              <option value="600325">600325 - 华发股份</option>
              <option value="600332">600332 - 白云山</option>
              <option value="600340">600340 - 华夏幸福</option>
              <option value="600352">600352 - 浙江龙盛</option>
              <option value="600383">600383 - 金地集团</option>
              <option value="600389">600389 - 江山股份</option>
              <option value="600398">600398 - 海澜之家</option>
              <option value="600406">600406 - 国电南瑞</option>
              <option value="600438">600438 - 通威股份</option>
              <option value="600460">600460 - 士兰微</option>
              <option value="600519">600519 - 贵州茅台</option>
              <option value="600570">600570 - 恒生电子</option>
              <option value="600585">600585 - 海螺水泥</option>
              <option value="600588">600588 - 用友网络</option>
              <option value="600600">600600 - 青岛啤酒</option>
              <option value="600606">600606 - 绿地控股</option>
              <option value="600637">600637 - 东方园林</option>
              <option value="600660">600660 - 福耀玻璃</option>
              <option value="600674">600674 - 川投能源</option>
              <option value="600690">600690 - 海尔智家</option>
              <option value="600703">600703 - 三安光电</option>
              <option value="600705">600705 - 中航资本</option>
              <option value="600741">600741 - 华域汽车</option>
              <option value="600760">600760 - 中航沈飞</option>
              <option value="600795">600795 - 国电电力</option>
              <option value="600816">600816 - 安信信托</option>
              <option value="600837">600837 - 海通证券</option>
              <option value="600848">600848 - 上海临港</option>
              <option value="600900">600900 - 长江电力</option>
              <option value="600905">600905 - 三峡能源</option>
              <option value="600919">600919 - 江苏银行</option>
              <option value="600926">600926 - 杭州银行</option>
              <option value="600938">600938 - 中国海油</option>
              <option value="600941">600941 - 中国移动</option>
              <option value="600960">600960 - 渤海汽车</option>
              <option value="600989">600989 - 宝丰能源</option>
              <option value="601012">601012 - 隆基绿能</option>
              <option value="601088">601088 - 中国神华</option>
              <option value="601166">601166 - 兴业银行</option>
              <option value="601169">601169 - 北京银行</option>
              <option value="601198">601198 - 东吴证券</option>
              <option value="601211">601211 - 国泰君安</option>
              <option value="601225">601225 - 陕西煤业</option>
              <option value="601288">601288 - 农业银行</option>
              <option value="601318">601318 - 中国平安</option>
              <option value="601328">601328 - 交通银行</option>
              <option value="601336">601336 - 新华保险</option>
              <option value="601360">601360 - 三六零</option>
              <option value="601377">601377 - 兴业证券</option>
              <option value="601390">601390 - 中国中铁</option>
              <option value="601398">601398 - 工商银行</option>
              <option value="601601">601601 - 中国太保</option>
              <option value="601618">601618 - 中国中冶</option>
              <option value="601628">601628 - 中国人寿</option>
              <option value="601658">601658 - 邮储银行</option>
              <option value="601668">601668 - 中国建筑</option>
              <option value="601688">601688 - 华泰证券</option>
              <option value="601728">601728 - 中国电信</option>
              <option value="601766">601766 - 中国中车</option>
              <option value="601788">601788 - 光大证券</option>
              <option value="601799">601799 - 中国银河</option>
              <option value="601800">601800 - 中国交建</option>
              <option value="601816">601816 - 京沪高铁</option>
              <option value="601818">601818 - 光大银行</option>
              <option value="601857">601857 - 中国石油</option>
              <option value="601878">601878 - 浙商证券</option>
              <option value="601888">601888 - 中国国旅</option>
              <option value="601899">601899 - 紫金矿业</option>
              <option value="601901">601901 - 晋控煤业</option>
              <option value="601919">601919 - 中远海控</option>
              <option value="601933">601933 - 永辉超市</option>
              <option value="601939">601939 - 建设银行</option>
              <option value="601966">601966 - 玲珑轮胎</option>
              <option value="601985">601985 - 中国核电</option>
              <option value="601988">601988 - 中国银行</option>
              <option value="601989">601989 - 中国重工</option>
              <option value="601992">601992 - 中国长城</option>
              <option value="601997">601997 - 贵阳银行</option>
              <option value="601998">601998 - 中信银行</option>
            </select>
          </label>
          <label>开始日期<input value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></label>
          <label>结束日期<input value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} /></label>
          <label>初始资金<input type="number" value={form.cash} onChange={(e) => setForm({ ...form, cash: Number(e.target.value) })} /></label>
          <label className="check-row">
            <input type="checkbox" checked={form.use_market_filter} onChange={(e) => setForm({ ...form, use_market_filter: e.target.checked })} />
            市场过滤器
          </label>
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
          <h2>历史记录</h2>
          {jobs.map((job) => (
            <button key={job.id} className="history-item" onClick={() => setSelectedJob(job)}>
              <span>{job.symbol} {job.start_date}-{job.end_date}</span>
              <StatusBadge status={job.status} />
            </button>
          ))}
        </section>
      </aside>

      <section className="content-panel">
        {error && <div className="error">{error}</div>}
        {selectedJob && (
          <div className="result-header">
            <div>
              <h2>{selectedJob.symbol} {getStockName(selectedJob.symbol)} 回测</h2>
              <p>{selectedJob.start_date} 至 {selectedJob.end_date} · {selectedJob.cache_hit ? '缓存命中' : '新任务'}</p>
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
    </main>
  );
}
