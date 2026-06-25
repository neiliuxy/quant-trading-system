import { useEffect, useMemo, useState } from 'react';
import { Activity, BookOpen, Database, LineChart, Play, RefreshCcw, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import i18n from './i18n';
import { createJob, createMarketFilterComparison, deleteJob, deleteAllJobs, getJob, getResult, getStocks, listJobs, listStrategies } from './api';
import type { BacktestFormValues, BacktestResult, Job, StrategySpec } from './types';
import ChartDateRangeControl from './ChartDateRangeControl';
import RunForm from './RunForm';
import StrategyGuide from './StrategyGuide';
import { calcMA, calcBoll, calcMacd, calcKdj } from './indicators';
import { filterByDateRange } from './charts/filterByDateRange';
import { buildKlineSeries } from './charts/buildSeries';
import { EquityPanel } from './panels/EquityPanel';
import type { LineVisibility } from './panels/EquityPanel';
import { StockIndicatorPanel } from './panels/StockIndicatorPanel';
import type { IndicatorKey } from './panels/StockIndicatorPanel';
import { IndexIndicatorPanel } from './panels/IndexIndicatorPanel';
import { StockKlinePanel } from './panels/StockKlinePanel';
import type { MaVisibility } from './panels/StockKlinePanel';
import { IndexKlinePanel } from './panels/IndexKlinePanel';
import DataManagementView from './data-management/DataManagementView';
import { LanguageSwitcher } from './components/LanguageSwitcher';
import { WfoConfigForm } from './WfoConfigForm';
import { WfoResultPage } from './WfoResultPage';
import type { WfoRun, WfoResult } from './types';

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

function StatusBadge({ status, labels }: { status: string; labels: Record<string, string> }) {
  return <span className={`status status-${status}`}>{labels[status] || status}</span>;
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

export default function App() {
  const { t } = useTranslation();
  const statusLabels: Record<string, string> = {
    'queued': t('job.queued'),
    'running': t('job.running'),
    'completed': t('job.completed'),
    'failed': t('job.failed'),
    'cancelled': t('job.cancelled'),
  };
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
  const [activeView, setActiveView] = useState<'backtest' | 'data'>('backtest');
  const [activeWfoRun, setActiveWfoRun] = useState<WfoRun | null>(null);
  const [wfoResult, setWfoResult] = useState<WfoResult | null>(null);

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
    if (!result) return { primary: null, secondary: [] };
    // 主指标：最终净值（绝对收益）
    const primary = {
      label: t('kpi.finalValue'),
      value: result.final_value.toFixed(2),
      sub: t('kpi.subFormat', {
        initial: result.initial_cash.toFixed(0),
        return: formatPct(result.total_return_pct),
      }),
    };
    // 次级指标：紧凑 chip
    const secondary = [
      { label: t('kpi.winRate'), value: formatPct(result.win_rate_pct) },
      { label: t('kpi.maxDrawdown'), value: formatPct(result.max_drawdown_pct) },
      { label: t('kpi.tradeCount'), value: String(result.trade_count) },
      { label: t('kpi.sharpe'), value: result.sharpe.toFixed(2) },
      { label: t('kpi.annualReturn'), value: formatPct(result.annual_return_pct) },
      { label: t('kpi.profitLossRatio'), value: result.profit_loss_ratio.toFixed(2) },
      { label: t('kpi.benchmarkReturn'), value: formatPct(result.benchmark_return_pct) },
      { label: t('kpi.excessReturn'), value: formatPct(result.excess_return_pct) },
      { label: t('kpi.avgScore'), value: result.market_score_summary.mean?.toFixed(2) ?? 'N/A' },
      { label: t('kpi.initialCash'), value: result.initial_cash.toFixed(0) },
    ];
    return { primary, secondary };
  }, [result, t]);

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

  const priceDataWithMA = useMemo(
    () => buildKlineSeries(result?.price_data ?? []),
    [result]
  );

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

  const indexDataWithMA = useMemo(
    () => buildKlineSeries(result?.index_data ?? []),
    [result]
  );

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
            <h1>{t('brand.title')}</h1>
            <p>{t('brand.subtitle')}</p>
          </div>
          <button className="nav-guide-btn" onClick={() => setShowGuide(true)} title={t('nav.strategyGuide')}>
            <BookOpen size={16} />
            {t('nav.strategyGuide')}
          </button>
        </div>

        <div className="view-switch" role="group" aria-label={t('nav.viewSwitch')}>
          <button
            type="button"
            className={activeView === 'backtest' ? 'active' : ''}
            onClick={() => setActiveView('backtest')}
          >
            <LineChart size={16} />
            {t('nav.backtest')}
          </button>
          <button
            type="button"
            className={activeView === 'data' ? 'active' : ''}
            onClick={() => setActiveView('data')}
          >
            <Database size={16} />
            {t('nav.dataMgmt')}
          </button>
        </div>

        <LanguageSwitcher />

        {activeView === 'backtest' && (
        <>
        <RunForm
          initialValue={runFormDefaults}
          strategies={strategies}
          submitting={submitting}
          hasSelectedJob={Boolean(selectedJob)}
          onSubmit={submit}
          onCompareMarketFilter={compareMarketFilter}
        />

        <details className="wfo-config">
          <summary>{t('wfo.configTitle')}</summary>
          <WfoConfigForm
            baseSymbol={runFormDefaults.symbol}
            baseStart={runFormDefaults.start}
            baseEnd={runFormDefaults.end}
            baseStrategyId={runFormDefaults.strategy_id}
            strategyParams={strategies.find(s => s.id === runFormDefaults.strategy_id)?.params ?? []}
            onSubmitted={(run) => { setActiveWfoRun(run); setWfoResult(null); }}
          />
        </details>

        <section className="history">
          <div className="history-header">
            <h2>{t('history.title')}</h2>
            {jobs.length > 0 && (
              <button
                className="clear-all-btn"
                onClick={() => setDeleteAllConfirm(true)}
                disabled={isDeleting || jobs.length === 0}
                title={t('history.clear')}
              >
                {t('history.clear')}
              </button>
            )}
          </div>
          {jobs.map((job) => (
            <div key={job.id} className="history-item-wrapper">
              <button className="history-item" onClick={() => setSelectedJob(job)}>
                <span className="history-item-label">{job.symbol} {getStockName(job.symbol)} {job.start_date}-{job.end_date}</span>
                <StatusBadge status={job.status} labels={statusLabels} />
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
        </>
        )}
      </aside>

      <section className="content-panel">
        {activeView === 'data' ? (
          <DataManagementView />
        ) : (
          <>
        {error && <div className="error">{error}</div>}
        {activeWfoRun && (
          <section className="panel wfo-panel">
            <h2>{t('wfo.title')}</h2>
            <WfoResultPage
              run={activeWfoRun}
              result={wfoResult}
              onResult={setWfoResult}
            />
          </section>
        )}
        {selectedJob && (
          <div className="result-header">
            <div>
              <h2>{t('result.backtestTitle', { symbol: selectedJob.symbol, name: getStockName(selectedJob.symbol) })}</h2>
              <p>{selectedJob.start_date} {t('common.to')} {selectedJob.end_date} | {selectedJob.cache_hit ? t('result.cacheHit') : t('result.freshJob')} | {getStrategyName(selectedJob.strategy_id)}</p>
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
            <StatusBadge status={selectedJob.status} labels={statusLabels} />
          </div>
        )}

        {result ? (
          <>
            <div className="kpi-grid">
              {kpis.primary && (
                <div className="kpi kpi-primary" key="primary">
                  <div>
                    <span className="kpi-label">{kpis.primary.label}</span>
                    <div className="kpi-value">{kpis.primary.value}</div>
                  </div>
                  <span className="kpi-sub">{kpis.primary.sub}</span>
                </div>
              )}
              {kpis.secondary.map(({ label, value }) => (
                <div className="kpi kpi-compact" key={label}>
                  <span className="kpi-label">{label}</span>
                  <span className="kpi-value">{value}</span>
                </div>
              ))}
            </div>

            {comparisonJob && (
              <section className="panel">
                <h3>{t('comparison.title')}</h3>
                {comparisonResult ? (
                  <div className="comparison-grid">
                    <div><span>{t('comparison.baseReturn')}</span><strong>{formatPct(result.total_return_pct)}</strong></div>
                    <div><span>{t('comparison.compareReturn')}</span><strong>{formatPct(comparisonResult.total_return_pct)}</strong></div>
                    <div><span>{t('comparison.baseDrawdown')}</span><strong>{formatPct(result.max_drawdown_pct)}</strong></div>
                    <div><span>{t('comparison.compareDrawdown')}</span><strong>{formatPct(comparisonResult.max_drawdown_pct)}</strong></div>
                    <div><span>{t('comparison.baseTrades')}</span><strong>{result.trade_count}</strong></div>
                    <div><span>{t('comparison.compareTrades')}</span><strong>{comparisonResult.trade_count}</strong></div>
                  </div>
                ) : (
                  <p>{t('comparison.status', { id: comparisonJob.id, status: statusLabels[comparisonJob.status] || comparisonJob.status })}</p>
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
              <StockKlinePanel
                data={result?.price_data ?? []}
                trades={result?.trades}
                maVisibility={maVisibility}
                onToggleMa={toggleMaVisibility}
                chartDateRange={chartDateRange}
                onChangeDateRange={setChartDateRange}
                defaultStart={selectedJob?.start_date || ''}
                defaultEnd={selectedJob?.end_date || ''}
                locale={i18n.language}
              />
              <StockIndicatorPanel
                data={stockIndicatorData}
                selected={stockSelectedIndicator}
                onChangeSelected={setStockSelectedIndicator}
                chartDateRange={chartDateRange}
              />
              </>
            )}

            {result && (
              (result.index_data?.length ?? 0) > 0 ? (
                <>
                <IndexKlinePanel
                  data={result?.index_data ?? []}
                  maVisibility={indexMaVisibility}
                  onToggleMa={toggleIndexMa}
                  chartDateRange={chartDateRange}
                  onChangeDateRange={setChartDateRange}
                  defaultStart={selectedJob?.start_date || ''}
                  defaultEnd={selectedJob?.end_date || ''}
                  locale={i18n.language}
                />
                <IndexIndicatorPanel
                  data={indexIndicatorData}
                  selected={selectedIndicator}
                  onChangeSelected={setSelectedIndicator}
                  chartDateRange={chartDateRange}
                />
              </>
              ) : (
                <section className="panel">
                  <h3>{t('panel.indexFallbackTitle')}</h3>
                  <p style={{ color: '#627282' }}>
                    {t('panel.indexFallbackDesc')}
                  </p>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => selectedJob && submit(runFormDefaults, true)}
                    disabled={submitting || !selectedJob}
                  >
                    <RefreshCcw size={16} /> {t('panel.rerun')}
                  </button>
                </section>
              )
            )}

            <section className="panel">
              <h3>{t('panel.trades')}</h3>
              <table>
                <thead><tr><th>{t('trades.date')}</th><th>{t('trades.pnl')}</th><th>{t('trades.pnlComm')}</th><th>{t('trades.holdingPeriod')}</th></tr></thead>
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
          <div className="empty-state">{t('result.empty')}</div>
        )}
          </>
        )}
      </section>

      {deleteConfirmJobId !== null && (
        <div className="modal-overlay" onClick={() => setDeleteConfirmJobId(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>{t('modal.deleteTitle')}</h3>
            <p>{t('modal.deleteBody')}</p>
            <div className="modal-buttons">
              <button
                className="modal-cancel"
                onClick={() => setDeleteConfirmJobId(null)}
                disabled={isDeleting}
              >
                {t('common.cancel')}
              </button>
              <button
                className="modal-delete"
                onClick={() => handleDeleteJob(deleteConfirmJobId)}
                disabled={isDeleting}
              >
                {isDeleting ? t('common.deleting') : t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteAllConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteAllConfirm(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>{t('modal.clearAllTitle')}</h3>
            <p>{t('modal.clearAllBody')}</p>
            <div className="modal-buttons">
              <button
                className="modal-cancel"
                onClick={() => setDeleteAllConfirm(false)}
                disabled={isDeleting}
              >
                {t('common.cancel')}
              </button>
              <button
                className="modal-delete"
                onClick={handleDeleteAllJobs}
                disabled={isDeleting}
              >
                {isDeleting ? t('common.deleting') : t('common.deleteAll')}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

