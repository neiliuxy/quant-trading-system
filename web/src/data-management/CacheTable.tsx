import type { FormEvent } from 'react';
import { RefreshCcw, Search } from 'lucide-react';
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

export default function CacheTable({
  selectedDataset,
  entries,
  loading,
  error,
  refreshing,
  onQuery,
  onRefresh,
}: CacheTableProps) {
  if (!selectedDataset) {
    return (
      <section className="data-panel cache-workspace">
        <h3>Cache Workspace</h3>
        <p className="muted">请选择一个数据集</p>
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
    <section className="data-panel cache-workspace">
      <div className="data-panel-header">
        <div>
          <h3>Cache Workspace</h3>
          <p className="muted">{selectedDataset.label} / {selectedDataset.dataset_type}</p>
        </div>
      </div>

      <form className="data-filter-form" onSubmit={queryCache}>
        {selectedDataset.symbol_required && (
          <label>
            Symbol
            <input name="symbol" placeholder="000001" />
          </label>
        )}
        <label>
          Start
          <input name="start" type="date" />
        </label>
        <label>
          End
          <input name="end" type="date" />
        </label>
        <button className="secondary" type="submit">
          <Search size={16} />
          查询缓存
        </button>
      </form>

      {loading && <p className="muted">缓存加载中...</p>}
      {error && <div className="error">{error}</div>}
      {!loading && !error && entries.length === 0 && <p className="muted">没有匹配的缓存条目</p>}
      {!loading && !error && entries.length > 0 && (
        <div className="data-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Symbol</th>
                <th>Range</th>
                <th>Rows</th>
                <th>Source</th>
                <th>Refreshed</th>
                <th>Path</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.dataset_type}</td>
                  <td>{entry.symbol ?? 'global'}</td>
                  <td>{entry.start_date}-{entry.end_date}</td>
                  <td>{entry.row_count}</td>
                  <td>{entry.source_name}</td>
                  <td>{entry.refreshed_at}</td>
                  <td className="mono-cell">{entry.file_path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form className="refresh-form" onSubmit={refreshData}>
        <h4>Refresh</h4>
        {selectedDataset.symbol_required && (
          <label>
            Refresh symbol
            <input name="refreshSymbol" placeholder="000001" />
          </label>
        )}
        <label>
          Refresh start
          <input name="refreshStart" type="date" required />
        </label>
        <label>
          Refresh end
          <input name="refreshEnd" type="date" required />
        </label>
        <label>
          Frequency
          <select name="frequency" defaultValue="daily">
            <option value="daily">daily</option>
          </select>
        </label>
        <label className="check-row">
          <input name="forceRefresh" type="checkbox" />
          Force refresh
        </label>
        <button className="primary" type="submit" disabled={refreshing}>
          <RefreshCcw size={16} />
          {refreshing ? '刷新中...' : '刷新数据'}
        </button>
      </form>
    </section>
  );
}

export { compactDate };
