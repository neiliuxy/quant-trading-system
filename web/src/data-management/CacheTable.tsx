import type { FormEvent } from 'react';
import { ClipboardCopy, FileSpreadsheet, RefreshCcw, Search } from 'lucide-react';
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

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value);
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
  if (!selectedDataset) {
    return (
      <section className="data-panel empty-state-panel">
        <FileSpreadsheet size={40} />
        <p>请选择一个数据集</p>
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
            <h3>查询缓存</h3>
            <p className="muted">{selectedDataset.label} / {selectedDataset.dataset_type}</p>
          </div>
        </div>

        <form className="data-filter-form" onSubmit={queryCache}>
          {selectedDataset.symbol_required && (
            <label>
              代码
              <input name="symbol" placeholder="000001" />
            </label>
          )}
          <label>
            开始日期
            <input name="start" type="date" />
          </label>
          <label>
            结束日期
            <input name="end" type="date" />
          </label>
          <button className="secondary" type="submit">
            <Search size={16} />
            查询缓存
          </button>
        </form>
      </section>

      <section className="data-panel cache-results-panel">
        <div className="data-panel-header">
          <div>
            <h3>缓存结果</h3>
            <p className="muted">{entries.length} 条记录</p>
          </div>
        </div>

        {loading && (
          <div className="state-message">
            <span className="spinner" />
            缓存加载中...
          </div>
        )}
        {error && <div className="error">{error}</div>}
        {!loading && !error && entries.length === 0 && (
          <div className="state-message">
            <Search size={20} />
            没有匹配的缓存条目
          </div>
        )}
        {!loading && !error && entries.length > 0 && (
          <div className="data-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>数据集</th>
                  <th>代码</th>
                  <th>日期范围</th>
                  <th className="numeric">行数</th>
                  <th>来源</th>
                  <th>刷新时间</th>
                  <th>路径</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.dataset_type}</td>
                    <td>{entry.symbol ?? '全局'}</td>
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
                        title="复制路径"
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
            <h3>刷新数据</h3>
            <p className="muted">从数据源拉取最新数据</p>
          </div>
        </div>

        <form className="refresh-form" onSubmit={refreshData}>
          {selectedDataset.symbol_required && (
            <label>
              刷新代码
              <input name="refreshSymbol" placeholder="000001" />
            </label>
          )}
          <label>
            刷新开始
            <input name="refreshStart" type="date" required />
          </label>
          <label>
            刷新结束
            <input name="refreshEnd" type="date" required />
          </label>
          <label>
            频率
            <select name="frequency" defaultValue="daily">
              <option value="daily">每日</option>
            </select>
          </label>
          <label className="check-row">
            <input name="forceRefresh" type="checkbox" />
            强制刷新
          </label>
          <button className="primary" type="submit" disabled={refreshing}>
            <RefreshCcw size={16} className={refreshing ? 'spin' : ''} />
            {refreshing ? '刷新中...' : '刷新数据'}
          </button>
        </form>
      </section>
    </div>
  );
}

export { compactDate };
