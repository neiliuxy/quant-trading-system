import { useEffect, useMemo, useRef, useState } from 'react';
import { createRefresh, getRefresh, listCache, listDatasets } from '../api';
import type { CacheEntry, CacheQueryParams, DataRefresh, DataRefreshPayload, DataSegment, DatasetSpec } from '../types';
import CacheTable from './CacheTable';
import DatasetCatalog from './DatasetCatalog';
import RefreshQueue from './RefreshQueue';

function segmentForDataset(dataset: DatasetSpec): DataSegment {
  return dataset.symbol_required ? 'stock' : 'index';
}

function messageFromError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  try {
    const parsed = JSON.parse(message);
    if (parsed?.detail?.error_type === 'refresh_in_progress') {
      return '该数据范围已有刷新任务在运行';
    }
    if (parsed?.detail?.message) {
      return String(parsed.detail.message);
    }
  } catch {
    return message;
  }
  return message;
}

export default function DataManagementView() {
  const [segment, setSegment] = useState<DataSegment>('stock');
  const [datasets, setDatasets] = useState<DatasetSpec[]>([]);
  const [selectedDatasetType, setSelectedDatasetType] = useState<string | null>(null);
  const [cacheEntries, setCacheEntries] = useState<CacheEntry[]>([]);
  const [refreshes, setRefreshes] = useState<DataRefresh[]>([]);
  const [selectedRefreshId, setSelectedRefreshId] = useState<number | null>(null);
  const [pollingIds, setPollingIds] = useState<Set<number>>(new Set());
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [cacheLoading, setCacheLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cacheError, setCacheError] = useState<string | null>(null);
  const [pollingError, setPollingError] = useState<string | null>(null);
  const lastCacheQueryRef = useRef<CacheQueryParams | null>(null);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.dataset_type === selectedDatasetType) ?? null,
    [datasets, selectedDatasetType]
  );

  const visibleDatasets = useMemo(
    () => datasets.filter((dataset) => segmentForDataset(dataset) === segment),
    [datasets, segment]
  );

  async function queryCache(params: CacheQueryParams) {
    setCacheLoading(true);
    setCacheError(null);
    lastCacheQueryRef.current = params;
    try {
      const rows = await listCache(params);
      setCacheEntries(rows);
    } catch (err) {
      setCacheEntries([]);
      setCacheError(messageFromError(err));
    } finally {
      setCacheLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    setDatasetsLoading(true);
    listDatasets()
      .then((rows) => {
        if (cancelled) return;
        setDatasets(rows);
        const first = rows.find((dataset) => segmentForDataset(dataset) === 'stock') ?? null;
        setSelectedDatasetType(first?.dataset_type ?? null);
        if (first) {
          void queryCache({ dataset_type: first.dataset_type });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(messageFromError(err));
      })
      .finally(() => {
        if (!cancelled) setDatasetsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleChangeSegment(nextSegment: DataSegment) {
    if (selectedDataset && segmentForDataset(selectedDataset) === nextSegment) {
      setSegment(nextSegment);
      return;
    }
    setSegment(nextSegment);
    const first = datasets.find((dataset) => segmentForDataset(dataset) === nextSegment) ?? null;
    setSelectedDatasetType(first?.dataset_type ?? null);
    setCacheEntries([]);
    if (first) {
      void queryCache({ dataset_type: first.dataset_type });
    }
  }

  function handleSelectDataset(datasetType: string) {
    setSelectedDatasetType(datasetType);
    void queryCache({ dataset_type: datasetType });
  }

  async function handleRefresh(payload: DataRefreshPayload) {
    setRefreshing(true);
    setError(null);
    try {
      const refresh = await createRefresh(payload);
      setRefreshes((prev) => [refresh, ...prev.filter((item) => item.id !== refresh.id)]);
      setSelectedRefreshId(refresh.id);
      if (refresh.status === 'queued' || refresh.status === 'running') {
        setPollingIds((prev) => new Set(prev).add(refresh.id));
      }
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (pollingIds.size === 0) return;
    const handle = window.setInterval(() => {
      pollingIds.forEach((refreshId) => {
        getRefresh(refreshId)
          .then((latest) => {
            setRefreshes((prev) => prev.map((item) => (item.id === latest.id ? latest : item)));
            if (latest.status !== 'queued' && latest.status !== 'running') {
              setPollingIds((prev) => {
                const next = new Set(prev);
                next.delete(latest.id);
                return next;
              });
              if (
                latest.status === 'completed' &&
                lastCacheQueryRef.current?.dataset_type === latest.dataset_type
              ) {
                void queryCache(lastCacheQueryRef.current);
              }
            }
          })
          .catch((err) => {
            setPollingError(messageFromError(err));
            setPollingIds((prev) => {
              const next = new Set(prev);
              next.delete(refreshId);
              return next;
            });
          });
      });
    }, 1500);
    return () => window.clearInterval(handle);
  }, [pollingIds]);

  return (
    <div className="data-management-view">
      <div className="result-header">
        <div>
          <h2>Data Management</h2>
          <p>数据集、缓存与刷新任务</p>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {pollingError && <div className="error">{pollingError}</div>}
      <div className="data-management-grid">
        <DatasetCatalog
          segment={segment}
          datasets={visibleDatasets}
          selectedDatasetType={selectedDatasetType}
          loading={datasetsLoading}
          onChangeSegment={handleChangeSegment}
          onSelectDataset={handleSelectDataset}
        />
        <CacheTable
          selectedDataset={selectedDataset}
          entries={cacheEntries}
          loading={cacheLoading}
          error={cacheError}
          onQuery={queryCache}
          onRefresh={handleRefresh}
          refreshing={refreshing}
        />
        <RefreshQueue
          refreshes={refreshes}
          selectedRefreshId={selectedRefreshId}
          onSelectRefresh={setSelectedRefreshId}
          pollingIds={pollingIds}
        />
      </div>
    </div>
  );
}
