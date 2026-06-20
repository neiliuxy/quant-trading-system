import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { ClipboardCopy, FileSpreadsheet, RefreshCcw, Search } from 'lucide-react';
import { formatNumber } from '../i18n/locale';
import type { CacheEntry, CacheQueryParams, DataRefreshPayload, DatasetSpec } from '../types';

interface CacheTableProps {
  selectedDataset: DatasetSpec | null;
  entries: CacheEntry[];
  loading: boolean;
  error: string | null;
  refreshing: boolean;
  onQuery: (params: CacheQueryParams) => void;
  onRefresh: (payload: DataRefreshPayload) => void;
}

function compactDate(value: string): string {
  return value.replace(/-/g, '');
}

function formatDate(value: string): string {
  if (!value || value.length !== 8) return value;
  return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
}

function copyToClipboard(text: string) {
  if (navigator.clipboard) {
    void navigator.clipboard.writeText(text);
  }
}

export default function CacheTable({
  selectedDataset,
  entries,
  loading,
  error,
  refreshing,
  onQuery,
  onRefresh,
}: CacheTableProps) {
  const { t } = useTranslation();
  if (!selectedDataset) {
    return (
      <section className="data-panel empty-state-panel">
        <FileSpreadsheet size={40} />
        <p>{t('dataMgmt.selectDataset')}</p>
      </section>
    );
  }

  function queryCache(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onQuery({
      dataset_type: selectedDataset!.dataset_type,
      symbol: selectedDataset!.symbol_required ? String(form.get('symbol') || '').trim() : undefined,
      start: compactDate(String(form.get('start') || '')),
      end: compactDate(String(form.get('end') || '')),
    });
  }

  function refreshData(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onRefresh({
      dataset_type: selectedDataset!.dataset_type,
      symbol: selectedDataset!.symbol_required ? String(form.get('refreshSymbol') || '').trim() || null : null,
      start: compactDate(String(form.get('refreshStart') || '')),
      end: compactDate(String(form.get('refreshEnd') || '')),
      frequency: String(form.get('frequency') || 'daily'),
      force_refresh: Boolean(form.get('forceRefresh')),
    });
  }

  return (
    <div className="cache-table-stack">
      <section className="data-panel cache-query-panel">
        <div className="data-panel-header">
          <div>
            <h3>{t('dataMgmt.cacheQuery')}</h3>
            <p className="muted">{selectedDataset.label} / {selectedDataset.dataset_type}</p>
          </div>
        </div>

        <form className="data-filter-form" onSubmit={queryCache}>
          {selectedDataset.symbol_required && (
            <label>
              {t('dataMgmt.symbol')}
              <input name="symbol" placeholder="000001" />
            </label>
          )}
          <label>
            {t('dataMgmt.start')}
            <input name="start" type="date" />
          </label>
          <label>
            {t('dataMgmt.end')}
            <input name="end" type="date" />
          </label>
          <button className="secondary" type="submit">
            <Search size={16} />
            {t('dataMgmt.cacheQuery')}
          </button>
        </form>
      </section>

      <section className="data-panel cache-results-panel">
        <div className="data-panel-header">
          <div>
            <h3>{t('dataMgmt.cacheResults')}</h3>
            <p className="muted">{t('dataMgmt.recordsCount', { count: entries.length })}</p>
          </div>
        </div>

        {loading && (
          <div className="state-message">
            <span className="spinner" />
            {t('dataMgmt.cacheLoading')}
          </div>
        )}
        {error && <div className="error">{error}</div>}
        {!loading && !error && entries.length === 0 && (
          <div className="state-message">
            <Search size={20} />
            {t('dataMgmt.noCacheEntries')}
          </div>
        )}
        {!loading && !error && entries.length > 0 && (
          <div className="data-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('dataMgmt.dataset')}</th>
                  <th>{t('dataMgmt.symbol')}</th>
                  <th>{t('dataMgmt.dateRange')}</th>
                  <th className="numeric">{t('dataMgmt.rowCount')}</th>
                  <th>{t('dataMgmt.source')}</th>
                  <th>{t('dataMgmt.refreshedAt')}</th>
                  <th>{t('dataMgmt.path')}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.dataset_type}</td>
                    <td>{entry.symbol ?? t('dataMgmt.symbolAll')}</td>
                    <td>{formatDate(entry.start_date)} - {formatDate(entry.end_date)}</td>
                    <td className="numeric">{formatNumber(entry.row_count)}</td>
                    <td>
                      <span className="source-badge">{entry.source_name}</span>
                    </td>
                    <td>{entry.refreshed_at}</td>
                    <td className="mono-cell">
                      <span title={entry.file_path}>{entry.file_path}</span>
                      <button
                        type="button"
                        className="icon-copy"
                        title={t('dataMgmt.copyPath')}
                        onClick={() => copyToClipboard(entry.file_path)}
                      >
                        <ClipboardCopy size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="data-panel cache-refresh-panel">
        <div className="data-panel-header">
          <div>
            <h3>{t('dataMgmt.refreshTitle')}</h3>
            <p className="muted">{t('dataMgmt.refreshDesc')}</p>
          </div>
        </div>

        <form className="refresh-form" onSubmit={refreshData}>
          {selectedDataset.symbol_required && (
            <label>
              {t('dataMgmt.refreshSymbol')}
              <input name="refreshSymbol" placeholder="000001" />
            </label>
          )}
          <label>
            {t('dataMgmt.refreshStart')}
            <input name="refreshStart" type="date" required />
          </label>
          <label>
            {t('dataMgmt.refreshEnd')}
            <input name="refreshEnd" type="date" required />
          </label>
          <label>
            {t('dataMgmt.frequency')}
            <select name="frequency" defaultValue="daily">
              <option value="daily">{t('dataMgmt.frequencyDaily')}</option>
            </select>
          </label>
          <label className="check-row">
            <input name="forceRefresh" type="checkbox" />
            {t('dataMgmt.forceRefresh')}
          </label>
          <button className="primary" type="submit" disabled={refreshing}>
            <RefreshCcw size={16} className={refreshing ? 'spin' : ''} />
            {refreshing ? t('dataMgmt.refreshing') : t('dataMgmt.refreshSubmit')}
          </button>
        </form>
      </section>
    </div>
  );
}

export { compactDate };
