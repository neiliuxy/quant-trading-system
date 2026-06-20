import { History, Loader2 } from 'lucide-react';
import type { DataRefresh } from '../types';

interface RefreshQueueProps {
  refreshes: DataRefresh[];
  selectedRefreshId: number | null;
  pollingIds: Set<number>;
  onSelectRefresh: (refreshId: number) => void;
}

function relativeTime(value: string): string {
  if (!value) return '-';
  const date = new Date(value.replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return value;
  const diff = Math.max(0, Date.now() - date.getTime());
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds} 秒前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  return `${days} 天前`;
}

function duration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return '-';
  const start = new Date(startedAt.replace(' ', 'T'));
  const end = new Date(finishedAt.replace(' ', 'T'));
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '-';
  const seconds = Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
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
        <div>
          <h3>刷新队列</h3>
          <p className="muted">{refreshes.length} 个任务</p>
        </div>
      </div>

      {refreshes.length === 0 && (
        <div className="state-message">
          <History size={20} />
          当前会话尚未发起刷新任务
        </div>
      )}

      <div className="refresh-list">
        {refreshes.map((refresh) => (
          <button
            key={refresh.id}
            type="button"
            className={`refresh-item ${refresh.id === selected?.id ? 'active' : ''}`}
            onClick={() => onSelectRefresh(refresh.id)}
          >
            <div className="refresh-item-top">
              <span className="refresh-id">#{refresh.id} {refresh.dataset_type}</span>
              <span className={`status status-${refresh.status}`}>{refresh.status}</span>
            </div>
            <div className="refresh-item-bottom">
              <span className="refresh-time">{relativeTime(refresh.created_at)}</span>
              {pollingIds.has(refresh.id) && (
                <span className="polling-label">
                  <Loader2 size={12} className="spin" />
                  轮询中
                </span>
              )}
            </div>
          </button>
        ))}
      </div>

      {selected && (
        <div className="refresh-detail-panel">
          <h4>任务详情 #{selected.id}</h4>
          <dl className="refresh-detail">
            <dt>状态</dt>
            <dd>
              <span className={`status status-${selected.status}`}>{selected.status}</span>
            </dd>
            <dt>数据集</dt>
            <dd>{selected.dataset_type}</dd>
            <dt>代码</dt>
            <dd>{selected.symbol ?? '全局'}</dd>
            <dt>日期范围</dt>
            <dd>{selected.start_date} - {selected.end_date}</dd>
            <dt>耗时</dt>
            <dd>{duration(selected.started_at, selected.finished_at)}</dd>
            <dt>缓存命中</dt>
            <dd>{selected.cache_hit ? '是' : '否'}</dd>
            {selected.output_cache_path && (
              <>
                <dt>输出路径</dt>
                <dd className="mono-cell" title={selected.output_cache_path}>
                  {selected.output_cache_path}
                </dd>
              </>
            )}
            {selected.error_type && (
              <>
                <dt>错误类型</dt>
                <dd className="error-text">{selected.error_type}</dd>
              </>
            )}
            {selected.error_message && (
              <>
                <dt>错误信息</dt>
                <dd className="error-text">{selected.error_message}</dd>
              </>
            )}
          </dl>
        </div>
      )}
    </aside>
  );
}
