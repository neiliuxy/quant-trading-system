import { useEffect, useMemo, useState } from 'react';
import { Activity, Play, RefreshCcw } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { createJob, getJob, getResult, listJobs } from './api';
import type { BacktestResult, Job } from './types';

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

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{status}</span>;
}

export default function App() {
  const [form, setForm] = useState(defaultForm);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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

  const kpis = useMemo(() => {
    if (!result) return [];
    return [
      ['Return', formatPct(result.total_return_pct)],
      ['Max Drawdown', formatPct(result.max_drawdown_pct)],
      ['Win Rate', formatPct(result.win_rate_pct)],
      ['Trades', String(result.trade_count)],
      ['Final Value', result.final_value.toFixed(2)],
      ['Score Mean', result.market_score_summary.mean?.toFixed(2) ?? 'N/A'],
    ];
  }, [result]);

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

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <Activity size={22} />
          <div>
            <h1>QuantX</h1>
            <p>Backtest research workbench</p>
          </div>
        </div>

        <form className="run-form" onSubmit={(event) => { event.preventDefault(); submit(false); }}>
          <label>Symbol<input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} /></label>
          <label>Start<input value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></label>
          <label>End<input value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} /></label>
          <label>Cash<input type="number" value={form.cash} onChange={(e) => setForm({ ...form, cash: Number(e.target.value) })} /></label>
          <label className="check-row">
            <input type="checkbox" checked={form.use_market_filter} onChange={(e) => setForm({ ...form, use_market_filter: e.target.checked })} />
            Market filter
          </label>
          <button className="primary" type="submit" disabled={submitting}>
            <Play size={16} /> Start backtest
          </button>
          <button className="secondary" type="button" onClick={() => submit(true)} disabled={submitting || !selectedJob}>
            <RefreshCcw size={16} /> Force rerun
          </button>
        </form>

        <section className="history">
          <h2>History</h2>
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
              <h2>{selectedJob.symbol} Backtest</h2>
              <p>{selectedJob.start_date} to {selectedJob.end_date} · {selectedJob.cache_hit ? 'Cache hit' : 'Fresh task'}</p>
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

            <section className="panel">
              <h3>Equity Curve</h3>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={result.equity_curve}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" minTickGap={32} />
                  <YAxis domain={['auto', 'auto']} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#2563eb" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </section>

            <section className="panel">
              <h3>Market Scores</h3>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={result.market_scores}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" minTickGap={32} />
                  <YAxis domain={[0, 1]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="total_score" stroke="#0f766e" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="trend_score" stroke="#f59e0b" dot={false} />
                  <Line type="monotone" dataKey="sentiment_score" stroke="#7c3aed" dot={false} />
                  <Line type="monotone" dataKey="volume_score" stroke="#dc2626" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </section>

            <section className="panel">
              <h3>Trades</h3>
              <table>
                <thead><tr><th>Date</th><th>PnL</th><th>PnL Comm</th><th>Bars</th></tr></thead>
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
          <div className="empty-state">Submit or select a completed job to view results.</div>
        )}
      </section>
    </main>
  );
}
