import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { createScreener, getRecentValidScreeningDate, getScreenerResult, getScreenerStatus } from './api';
import type { ScreenerResult, ScreenerRun } from './types';

const UNIVERSE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '000300', label: '沪深300' },
  { value: '000905', label: '中证500' },
];

function todayYmd(): string {
  return new Date().toISOString().slice(0, 10).replace(/-/g, '');
}

function ymdToInput(ymd: string): string {
  return `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}`;
}

interface FormState {
  date: string;
  universeSymbol: string;
  topN: number;
}

const defaultForm: FormState = {
  date: todayYmd(),
  universeSymbol: '000300',
  topN: 30,
};

export function ScreenerPage() {
  const { t } = useTranslation();
  const [form, setForm] = useState<FormState>(defaultForm);
  const [submitting, setSubmitting] = useState(false);
  const [run, setRun] = useState<ScreenerRun | null>(null);
  const [result, setResult] = useState<ScreenerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dateHint, setDateHint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getRecentValidScreeningDate()
      .then((resp) => {
        if (cancelled) return;
        setForm((prev) => ({ ...prev, date: resp.date }));
        setDateHint(resp.source);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!run) return;
    let cancelled = false;
    let timer: number | null = null;

    async function tick() {
      try {
        const latest = await getScreenerStatus(run!.id);
        if (cancelled) return;
        setRun(latest);
        if (latest.status === 'completed') {
          const payload = await getScreenerResult(latest.id);
          if (!cancelled) setResult(payload);
          return;
        }
        if (latest.status === 'failed') {
          return;
        }
        timer = window.setTimeout(tick, 1500);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [run?.id]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const newRun = await createScreener({
        date: form.date.replace(/-/g, ''),
        universe_mode: 'predefined',
        universe_symbol: form.universeSymbol,
        top_n: form.topN,
        market_gate_mode: 'hard',
        market_gate_threshold: 0.4,
      });
      setRun(newRun);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="screener-page">
      <form className="screener-form" onSubmit={handleSubmit}>
        <label>
          {t('screener.date')}
          <input
            type="date"
            value={ymdToInput(form.date)}
            onChange={(e) => setForm({ ...form, date: e.target.value.replace(/-/g, '') })}
            disabled={submitting}
          />
          {dateHint && (
            <span className="form-hint">
              {dateHint === 'index_cache' ? t('screener.dateHintTrading') : t('screener.dateHintFallback')}
            </span>
          )}
        </label>
        <label>
          {t('screener.universe')}
          <select
            value={form.universeSymbol}
            onChange={(e) => setForm({ ...form, universeSymbol: e.target.value })}
            disabled={submitting}
          >
            {UNIVERSE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label>
          {t('screener.topN')}
          <input
            type="number"
            min={1}
            max={200}
            value={form.topN}
            onChange={(e) => setForm({ ...form, topN: Number(e.target.value) })}
            disabled={submitting}
          />
        </label>
        <button type="submit" disabled={submitting || (run?.status === 'running' || run?.status === 'queued')}>
          {t('screener.submit')}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {run && (
        <div className="screener-status">
          <span>run #{run.id}</span>
          <span className={`status status-${run.status}`}>{run.status}</span>
          {run.status === 'completed' && (
            <span>
              {t('screener.passed', {
                passed: run.total_passed_filters,
                total: run.total_in_universe,
              })}
            </span>
          )}
          {run.status === 'failed' && run.error && (
            <span className="error">{run.error}</span>
          )}
        </div>
      )}

      {result && (
        <div className="screener-result">
          <div className="screener-banner">
            <span>{t('screener.marketScore')}: {result.market_score.total.toFixed(2)}</span>
            <span>
              {t('screener.funnel', {
                total: result.total_in_universe,
                passed: result.total_passed_filters,
                top: result.candidates.length,
              })}
            </span>
          </div>

          {result.candidates.length === 0 ? (
            <div className="screener-empty">
              <p className="empty-state">
                {result.market_gate_passed
                  ? t('screener.noCandidatesFiltered', {
                      total: result.total_in_universe,
                      passed: result.total_passed_filters,
                    })
                  : t('screener.noCandidatesMarketGate', {
                      score: result.market_score.total.toFixed(2),
                    })}
              </p>
              <details className="screener-rules">
                <summary>{t('screener.rulesTitle')}</summary>
                <ul>
                  <li>{t('screener.rule1')}</li>
                  <li>{t('screener.rule2')}</li>
                  <li>{t('screener.rule3')}</li>
                  <li>{t('screener.rule4')}</li>
                  <li>{t('screener.rule5')}</li>
                  <li>{t('screener.rule6')}</li>
                  <li>{t('screener.rule7')}</li>
                  <li>{t('screener.rule8')}</li>
                </ul>
              </details>
            </div>
          ) : (
            <table className="screener-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t('screener.code')}</th>
                  <th>{t('screener.name')}</th>
                  <th>{t('screener.score')}</th>
                  <th>RS</th>
                  <th>Trend</th>
                  <th>DD</th>
                  <th>V/P</th>
                  <th>Liq</th>
                  <th>{t('screener.reason')}</th>
                </tr>
              </thead>
              <tbody>
                {result.candidates.map((c) => (
                  <tr key={c.code}>
                    <td>{c.rank}</td>
                    <td><code>{c.code}</code></td>
                    <td>{c.name || c.code}</td>
                    <td><strong>{c.total_score.toFixed(2)}</strong></td>
                    <td>{c.scores.relative_strength.toFixed(2)}</td>
                    <td>{c.scores.trend_quality.toFixed(2)}</td>
                    <td>{c.scores.drawdown.toFixed(2)}</td>
                    <td>{c.scores.vol_price.toFixed(2)}</td>
                    <td>{c.scores.liquidity.toFixed(2)}</td>
                    <td className="reason">{c.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}