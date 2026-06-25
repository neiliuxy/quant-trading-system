import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { createWfo } from './api';
import type { StrategyParamSpec, WfoRun } from './types';

interface Props {
  baseSymbol: string;
  baseStart: string;
  baseEnd: string;
  baseStrategyId: string;
  strategyParams: StrategyParamSpec[];
  onSubmitted: (run: WfoRun) => void;
}

interface ParamRange {
  min: number;
  max: number;
  step: number;
}

export function WfoConfigForm({
  baseSymbol, baseStart, baseEnd, baseStrategyId,
  strategyParams, onSubmitted,
}: Props) {
  const { t } = useTranslation();
  const numericParams = strategyParams.filter(p => p.type === 'int' || p.type === 'float');

  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [ranges, setRanges] = useState<Record<string, ParamRange>>({});
  const [trainDays, setTrainDays] = useState(504);
  const [testDays, setTestDays] = useState(126);
  const [stepDays, setStepDays] = useState(126);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setRangeField = (name: string, field: keyof ParamRange, value: number) => {
    setRanges(prev => ({
      ...prev,
      [name]: { ...(prev[name] ?? { min: 0, max: 0, step: 1 }), [field]: value },
    }));
  };

  const submit = async () => {
    setError(null);
    const paramGrid: Record<string, number[]> = {};
    for (const name of Object.keys(selected)) {
      if (!selected[name]) continue;
      const r = ranges[name];
      if (!r) continue;
      const vals: number[] = [];
      for (let v = r.min; v <= r.max + 1e-9; v += r.step) {
        vals.push(Number(v.toFixed(6)));
      }
      paramGrid[name] = vals;
    }
    setSubmitting(true);
    try {
      const run = await createWfo({
        symbol: baseSymbol, start: baseStart, end: baseEnd,
        cash: 100000, use_market_filter: true,
        strategy_id: baseStrategyId,
        param_grid: paramGrid,
        train_days: trainDays, test_days: testDays, step_days: stepDays,
      });
      onSubmitted(run);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="wfo-form">
      <div>
        <label>{t('wfo.selectParams')}</label>
        {numericParams.map(p => (
          <div key={p.name}>
            <label className="wfo-param-row">
              <input
                type="checkbox"
                checked={!!selected[p.name]}
                onChange={(e) => setSelected({ ...selected, [p.name]: e.target.checked })}
              />
              <span>{p.label} ({p.name})</span>
            </label>
            {selected[p.name] && (
              <span className="wfo-range-inputs">
                <input
                  type="number" placeholder={t('wfo.min')}
                  value={ranges[p.name]?.min ?? ''}
                  onChange={(e) => setRangeField(p.name, 'min', Number(e.target.value))}
                />
                <input
                  type="number" placeholder={t('wfo.max')}
                  value={ranges[p.name]?.max ?? ''}
                  onChange={(e) => setRangeField(p.name, 'max', Number(e.target.value))}
                />
                <input
                  type="number" placeholder={t('wfo.step')}
                  value={ranges[p.name]?.step ?? ''}
                  onChange={(e) => setRangeField(p.name, 'step', Number(e.target.value))}
                />
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="wfo-window-inputs">
        <label>
          {t('wfo.trainDays')}
          <input type="number" value={trainDays} onChange={(e) => setTrainDays(Number(e.target.value))} />
        </label>
        <label>
          {t('wfo.testDays')}
          <input type="number" value={testDays} onChange={(e) => setTestDays(Number(e.target.value))} />
        </label>
        <label>
          {t('wfo.stepDays')}
          <input type="number" value={stepDays} onChange={(e) => setStepDays(Number(e.target.value))} />
        </label>
      </div>
      <button className="primary" onClick={submit} disabled={submitting}>
        {submitting ? t('wfo.running') : t('wfo.submit')}
      </button>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
