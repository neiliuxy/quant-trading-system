import { memo, useEffect, useState } from 'react';

type DateRange = {
  start: string;
  end: string;
};

type Props = {
  value: DateRange | null;
  defaultStart: string;
  defaultEnd: string;
  onChange: (next: DateRange | null) => void;
};

function normalizeDateInput(value: string): string {
  return value.replace(/\D/g, '').slice(0, 8);
}

function getDraft(value: DateRange | null, defaultStart: string, defaultEnd: string): DateRange {
  return {
    start: value?.start ?? defaultStart,
    end: value?.end ?? defaultEnd,
  };
}

function ChartDateRangeControl({ value, defaultStart, defaultEnd, onChange }: Props) {
  const [draft, setDraft] = useState<DateRange>(() => getDraft(value, defaultStart, defaultEnd));

  useEffect(() => {
    setDraft(getDraft(value, defaultStart, defaultEnd));
  }, [value, defaultStart, defaultEnd]);

  function commit(field: keyof DateRange, raw: string) {
    const normalized = normalizeDateInput(raw);
    if (normalized && normalized.length !== 8) {
      return;
    }

    const next = {
      start: field === 'start' ? normalized || defaultStart : draft.start || defaultStart,
      end: field === 'end' ? normalized || defaultEnd : draft.end || defaultEnd,
    };

    onChange(next);
  }

  return (
    <div className="chart-date-range">
      <label>显示时间范围
        <div className="date-range-inputs">
          <input
            type="text"
            placeholder="YYYYMMDD"
            value={draft.start}
            onChange={(e) => {
              const start = normalizeDateInput(e.target.value);
              setDraft((prev) => ({ ...prev, start }));
            }}
            onBlur={(e) => commit('start', e.target.value)}
          />
          <span>至</span>
          <input
            type="text"
            placeholder="YYYYMMDD"
            value={draft.end}
            onChange={(e) => {
              const end = normalizeDateInput(e.target.value);
              setDraft((prev) => ({ ...prev, end }));
            }}
            onBlur={(e) => commit('end', e.target.value)}
          />
          <button
            type="button"
            className="reset-date-btn"
            onClick={() => onChange(null)}
            title="Reset to full range"
          >
            重置
          </button>
        </div>
      </label>
    </div>
  );
}

export default memo(ChartDateRangeControl);
