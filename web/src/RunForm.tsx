import { memo, useEffect, useMemo, useState } from 'react';
import { Play, RefreshCcw } from 'lucide-react';
import { StockSelect } from './StockSelect';
import StrategyParamsForm from './StrategyParamsForm';
import type { BacktestFormValues, StrategySpec } from './types';

type Props = {
  initialValue: BacktestFormValues;
  strategies: StrategySpec[];
  submitting: boolean;
  hasSelectedJob: boolean;
  onSubmit: (next: BacktestFormValues, force: boolean) => void;
  onCompareMarketFilter: () => void;
};

function formatDateForInput(dateStr: string): string {
  if (!dateStr || dateStr.length !== 8) return '';
  return `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
}

function formatDateFromInput(dateStr: string): string {
  if (!dateStr) return '';
  return dateStr.replace(/-/g, '');
}

function buildStrategyDefaults(spec?: StrategySpec): Record<string, unknown> {
  return Object.fromEntries((spec?.params ?? []).map((param) => [param.name, param.default]));
}

function RunForm({
  initialValue,
  strategies,
  submitting,
  hasSelectedJob,
  onSubmit,
  onCompareMarketFilter,
}: Props) {
  const [draft, setDraft] = useState<BacktestFormValues>(initialValue);

  useEffect(() => {
    setDraft(initialValue);
  }, [initialValue]);

  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.id === draft.strategy_id) ?? strategies[0],
    [strategies, draft.strategy_id]
  );

  function update<K extends keyof BacktestFormValues>(key: K, value: BacktestFormValues[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  function handleStrategyChange(strategyId: string) {
    const nextStrategy = strategies.find((strategy) => strategy.id === strategyId);
    setDraft((prev) => ({
      ...prev,
      strategy_id: strategyId,
      strategy_params: buildStrategyDefaults(nextStrategy),
    }));
  }

  return (
    <form
      className="run-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(draft, false);
      }}
    >
      <label>
        代码
        <StockSelect
          value={draft.symbol}
          onChange={(code) => update('symbol', code)}
        />
      </label>
      <label>
        开始日期
        <input
          type="date"
          value={formatDateForInput(draft.start)}
          onChange={(e) => update('start', formatDateFromInput(e.target.value))}
        />
      </label>
      <label>
        结束日期
        <input
          type="date"
          value={formatDateForInput(draft.end)}
          onChange={(e) => update('end', formatDateFromInput(e.target.value))}
          min={formatDateForInput(draft.start)}
        />
      </label>
      <label>
        初始资金
        <input
          type="number"
          value={draft.cash}
          onChange={(e) => update('cash', Number(e.target.value))}
        />
      </label>
      <label className="check-row">
        <input
          type="checkbox"
          checked={draft.use_market_filter}
          onChange={(e) => update('use_market_filter', e.target.checked)}
        />
        市场过滤器
      </label>
      <label>
        策略
        <select
          value={draft.strategy_id}
          onChange={(e) => handleStrategyChange(e.target.value)}
        >
          {strategies.map((strategy) => (
            <option key={strategy.id} value={strategy.id}>{strategy.name}</option>
          ))}
        </select>
      </label>
      {selectedStrategy && (
        <StrategyParamsForm
          spec={selectedStrategy}
          value={draft.strategy_params}
          onChange={(params) => update('strategy_params', params)}
        />
      )}
      <button className="primary" type="submit" disabled={submitting}>
        <Play size={16} /> 开始回测
      </button>
      <button
        className="secondary"
        type="button"
        onClick={() => onSubmit(draft, true)}
        disabled={submitting || !hasSelectedJob}
      >
        <RefreshCcw size={16} /> 强制重新运行
      </button>
      <button
        className="secondary"
        type="button"
        onClick={onCompareMarketFilter}
        disabled={!hasSelectedJob}
      >
        对比过滤器
      </button>
    </form>
  );
}

export default memo(RunForm);
