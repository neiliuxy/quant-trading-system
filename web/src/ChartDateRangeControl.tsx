import { memo, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();
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
      <label>{t('dateRange.label')}
        <div className="date-range-inputs">
          <input
            type="text"
            placeholder={t('dateRange.placeholder')}
            value={draft.start}
            onChange={(e) => {
              const start = normalizeDateInput(e.target.value);
              setDraft((prev) => ({ ...prev, start }));
            }}
            onBlur={(e) => commit('start', e.target.value)}
          />
          <span>{t('common.to')}</span>
          <input
            type="text"
            placeholder={t('dateRange.placeholder')}
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
            title={t('dateRange.resetTitle')}
          >
            {t('dateRange.reset')}
          </button>
        </div>
      </label>
    </div>
  );
}

export default memo(ChartDateRangeControl);
