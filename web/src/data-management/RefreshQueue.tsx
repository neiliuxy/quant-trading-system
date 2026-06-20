import type { DataRefresh } from '../types';

interface RefreshQueueProps {
  refreshes: DataRefresh[];
  selectedRefreshId: number | null;
  pollingIds: Set<number>;
  onSelectRefresh: (refreshId: number) => void;
}

export default function RefreshQueue({
  refreshes,
  selectedRefreshId,
  pollingIds,
  onSelectRefresh,
}: RefreshQueueProps) {
  const selected = refreshes.find((refresh) => refresh.id === selectedRefreshId) ?? refreshes[0] ?? null;

  return (
    <aside className="data-panel refresh-queue">
      <div className="data-panel-header">
        <h3>刷新队列</h3>
      </div>

      {refreshes.length === 0 && <p className="muted">当前会话尚未发起刷新任务</p>}

      <div className="refresh-list">
        {refreshes.map((refresh) => (
          <button
            key={refresh.id}
            type="button"
            className={`refresh-item ${refresh.id === selected?.id ? 'active' : ''}`}
            onClick={() => onSelectRefresh(refresh.id)}
          >
            <span>#{refresh.id} {refresh.dataset_type}</span>
            <span className={`status status-${refresh.status}`}>{refresh.status}</span>
            {pollingIds.has(refresh.id) && <span className="polling-label">轮询中</span>}
          </button>
        ))}
      </div>

      {selected && (
        <dl className="refresh-detail">
          <dt>Status</dt>
          <dd>{selected.status}</dd>
          <dt>Dataset</dt>
          <dd>{selected.dataset_type}</dd>
          <dt>Symbol</dt>
          <dd>{selected.symbol ?? 'global'}</dd>
          <dt>Range</dt>
          <dd>{selected.start_date}-{selected.end_date}</dd>
          <dt>Cache hit</dt>
          <dd>{String(Boolean(selected.cache_hit))}</dd>
          {selected.output_cache_path && (
            <>
              <dt>Output</dt>
              <dd className="mono-cell">{selected.output_cache_path}</dd>
            </>
          )}
          {selected.error_type && (
            <>
              <dt>Error type</dt>
              <dd>{selected.error_type}</dd>
            </>
          )}
          {selected.error_message && (
            <>
              <dt>Error message</dt>
              <dd>{selected.error_message}</dd>
            </>
          )}
        </dl>
      )}
    </aside>
  );
}
