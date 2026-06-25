import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { getWfoResult, getWfoStatus } from './api';
import type { WfoResult, WfoRun } from './types';

interface Props {
  run: WfoRun;
  result: WfoResult | null;
  onResult: (r: WfoResult) => void;
}

function efficiencyColor(eff: number | null): string {
  if (eff === null) return '#888';
  if (eff >= 0.6) return '#37a169';
  if (eff >= 0.3) return '#e0913a';
  return '#e05a4f';
}

export function WfoResultPage({ run, result, onResult }: Props) {
  const { t } = useTranslation();
  const [progressLabel, setProgressLabel] = useState('');

  // 轮询状态直到完成
  useEffect(() => {
    if (result) return;
    if (run.status === 'completed' || run.status === 'failed') return;
    const interval = setInterval(async () => {
      const data = await getWfoStatus(run.id);
      setProgressLabel(t('wfo.progress', { current: data.current_fold, total: data.total_folds }));
      if (data.status === 'completed') {
        const payload = await getWfoResult(run.id);
        onResult(payload);
        clearInterval(interval);
      }
      if (data.status === 'failed') clearInterval(interval);
    }, 1000);
    return () => clearInterval(interval);
  }, [run.id, run.status, result, onResult, t]);

  if (run.status === 'failed') {
    return <div className="wfo-failed">WFO failed: {run.error}</div>;
  }
  if (!result) {
    return <div className="wfo-progress">{progressLabel || t('wfo.running')}</div>;
  }

  const { summary, folds } = result;
  const efficiency = summary.efficiency;
  const isNoValidFold = efficiency === null && summary.mean_is_sharpe === 0 && summary.fold_count > 0;

  const chartData = folds.map(f => ({
    name: `Fold ${f.fold_index + 1}`,
    is: f.failed || f.no_signal ? 0 : f.is_sharpe,
    oos: f.failed ? 0 : f.oos_sharpe,
  }));

  return (
    <div className="wfo-result">
      {/* 裁决卡 */}
      <div className="wfo-verdict">
        <div className="vcard">
          <div className="cap">{t('wfo.summary.isSharpe')}</div>
          <div className="big">{summary.mean_is_sharpe.toFixed(2)}</div>
        </div>
        <div className="vcard">
          <div className="cap">{t('wfo.summary.oosSharpe')}</div>
          <div className="big">{summary.mean_oos_sharpe.toFixed(2)}</div>
        </div>
        <div className="vcard" style={{ color: efficiencyColor(efficiency) }}>
          <div className="cap">{t('wfo.summary.efficiency')}</div>
          <div className="big">
            {isNoValidFold ? t('wfo.summary.noValidFold') :
             efficiency === null ? t('wfo.summary.efficiencyInvalid') :
             efficiency.toFixed(2)}
          </div>
        </div>
        <div className="vcard">
          <div className="cap">{t('wfo.summary.oosWins')}</div>
          <div className="big">{summary.oos_win_folds} / {summary.fold_count}</div>
        </div>
      </div>

      {/* 柱状图 */}
      <h3>{t('wfo.chartTitle')}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="is" fill="#4f6bed" name="IS" />
          <Bar dataKey="oos" fill="#e0913a" name="OOS" />
        </BarChart>
      </ResponsiveContainer>

      {/* 明细表 */}
      <h3>{t('wfo.tableTitle')}</h3>
      <table className="wfo-table">
        <thead>
          <tr>
            <th>Fold</th>
            <th>Train</th>
            <th>Test</th>
            <th>Best Params</th>
            <th>IS Sharpe</th>
            <th>OOS Sharpe</th>
            <th>OOS Return %</th>
            <th>OOS Trades</th>
          </tr>
        </thead>
        <tbody>
          {folds.map(f => (
            <tr key={f.fold_index} className={f.failed ? 'failed' : f.no_signal ? 'no-signal' : ''}>
              <td>{f.fold_index + 1}</td>
              <td>{f.train_start}~{f.train_end}</td>
              <td>{f.test_start}~{f.test_end}</td>
              <td>
                {f.failed ? <i>{t('wfo.foldFailed')}</i> :
                 f.no_signal ? <i>{t('wfo.foldNoSignal')}</i> :
                 Object.entries(f.best_params).map(([k, v]) => `${k}=${v}`).join(', ')}
              </td>
              <td>{f.is_sharpe.toFixed(2)}</td>
              <td>{f.oos_sharpe.toFixed(2)}</td>
              <td>{f.oos_return_pct.toFixed(2)}</td>
              <td>{f.oos_trade_count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* 参数稳定性 */}
      <h3>{t('wfo.summary.paramStability')}</h3>
      <p className="hint">{t('wfo.stabilityHint')}</p>
      <table className="wfo-stability">
        <thead>
          <tr><th>Param</th><th>Mode</th><th>Count</th><th>Mean</th><th>Std</th></tr>
        </thead>
        <tbody>
          {Object.entries(summary.param_stability).map(([name, ps]) => (
            <tr key={name}>
              <td>{name}</td>
              <td>{ps.value}</td>
              <td>{ps.count}</td>
              <td>{ps.mean.toFixed(3)}</td>
              <td>{ps.std.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
