import { useTranslation } from 'react-i18next';
import { History, Loader2 } from 'lucide-react';
import type { DataRefresh } from '../types';

interface RefreshQueueProps {
  refreshes: DataRefresh[];
  selectedRefreshId: number | null;
  pollingIds: Set<number>;
  onSelectRefresh: (refreshId: number) => void;
}

function relativeTime(value: string, t: (key: string) => string): string {
  if (!value) return '-';
  const date = new Date(value.replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return value;
  const diff = Math.max(0, Date.now() - date.getTime());
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds} ${t('common.secondsAgo')}`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} ${t('common.minutesAgo')}`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ${t('common.hoursAgo')}`;
  const days = Math.floor(hours / 24);
  return `${days} ${t('common.daysAgo')}`;
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
  const { t } = useTranslation();
  const selected = refreshes.find((refresh) => refresh.id === selectedRefreshId) ?? refreshes[0] ?? null;

  return (
    <aside className="data-panel refresh-queue">
      <div className="data-panel-header">
        <div>
          <h3>{t('dataMgmt.refreshQueueTitle')}</h3>
          <p className="muted">{t('dataMgmt.refreshCount', { count: refreshes.length })}</p>
        </div>
      </div>

      {refreshes.length === 0 && (
        <div className="state-message">
          <History size={20} />
          {t('dataMgmt.refreshQueueEmpty')}
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
              <span className="refresh-time">{relativeTime(refresh.created_at, t)}</span>
              {pollingIds.has(refresh.id) && (
                <span className="polling-label">
                  <Loader2 size={12} className="spin" />
                  {t('dataMgmt.polling')}
                </span>
              )}
            </div>
          </button>
        ))}
      </div>

      {selected && (
        <div className="refresh-detail-panel">
          <h4>{t('dataMgmt.taskDetail', { id: selected.id })}</h4>
          <dl className="refresh-detail">
            <dt>{t('dataMgmt.status')}</dt>
            <dd>
              <span className={`status status-${selected.status}`}>{selected.status}</span>
            </dd>
            <dt>{t('dataMgmt.taskDataset')}</dt>
            <dd>{selected.dataset_type}</dd>
            <dt>{t('dataMgmt.symbol')}</dt>
            <dd>{selected.symbol ?? t('dataMgmt.symbolAll')}</dd>
            <dt>{t('dataMgmt.dateRange')}</dt>
            <dd>{selected.start_date} - {selected.end_date}</dd>
            <dt>{t('dataMgmt.duration')}</dt>
            <dd>{duration(selected.started_at, selected.finished_at)}</dd>
            <dt>{t('dataMgmt.cacheHit')}</dt>
            <dd>{selected.cache_hit ? t('common.yes') : t('common.no')}</dd>
            {selected.output_cache_path && (
              <>
                <dt>{t('dataMgmt.outputPath')}</dt>
                <dd className="mono-cell" title={selected.output_cache_path}>
                  {selected.output_cache_path}
                </dd>
              </>
            )}
            {selected.error_type && (
              <>
                <dt>{t('dataMgmt.errorType')}</dt>
                <dd className="error-text">{selected.error_type}</dd>
              </>
            )}
            {selected.error_message && (
              <>
                <dt>{t('dataMgmt.errorMessage')}</dt>
                <dd className="error-text">{selected.error_message}</dd>
              </>
            )}
          </dl>
        </div>
      )}
    </aside>
  );
}
