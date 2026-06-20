import { useMemo, useState } from 'react';
import { Globe, Search, TrendingUp } from 'lucide-react';
import type { DataSegment, DatasetSpec } from '../types';

interface DatasetCatalogProps {
  segment: DataSegment;
  datasets: DatasetSpec[];
  selectedDatasetType: string | null;
  loading: boolean;
  onChangeSegment: (segment: DataSegment) => void;
  onSelectDataset: (datasetType: string) => void;
}

const segmentLabels: Record<DataSegment, string> = {
  stock: '个股',
  index: '大盘',
};

function datasetSegment(dataset: DatasetSpec): DataSegment {
  return dataset.symbol_required ? 'stock' : 'index';
}

function formatTTL(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return 'none';
  if (seconds >= 86400) return `${Math.round(seconds / 86400)}d`;
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}h`;
  if (seconds >= 60) return `${Math.round(seconds / 60)}m`;
  return `${seconds}s`;
}

export default function DatasetCatalog({
  segment,
  datasets,
  selectedDatasetType,
  loading,
  onChangeSegment,
  onSelectDataset,
}: DatasetCatalogProps) {
  const [query, setQuery] = useState('');
  const visibleDatasets = datasets.filter((dataset) => datasetSegment(dataset) === segment);

  const filteredDatasets = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return visibleDatasets;
    return visibleDatasets.filter(
      (dataset) =>
        dataset.label.toLowerCase().includes(trimmed) ||
        dataset.dataset_type.toLowerCase().includes(trimmed)
    );
  }, [visibleDatasets, query]);

  return (
    <section className="data-panel data-catalog">
      <div className="data-panel-header">
        <div>
          <h3>Dataset Catalog</h3>
          <p className="muted">{visibleDatasets.length} 个可用数据集</p>
        </div>
      </div>

      <div className="segment-control" role="group" aria-label="Data segment">
        {(Object.keys(segmentLabels) as DataSegment[]).map((key) => (
          <button
            key={key}
            type="button"
            className={key === segment ? 'active' : ''}
            onClick={() => onChangeSegment(key)}
          >
            {key === 'stock' ? <TrendingUp size={14} /> : <Globe size={14} />}
            {segmentLabels[key]}
          </button>
        ))}
      </div>

      <div className="catalog-search">
        <Search size={14} />
        <input
          type="text"
          placeholder="搜索数据集..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {loading && (
        <div className="state-message">
          <span className="spinner" />
          数据集加载中...
        </div>
      )}

      {!loading && filteredDatasets.length === 0 && (
        <p className="muted">{query ? '没有匹配的数据集' : '当前分段没有可用数据集'}</p>
      )}

      <div className="dataset-list">
        {filteredDatasets.map((dataset) => (
          <button
            key={dataset.dataset_type}
            type="button"
            className={`dataset-item ${dataset.dataset_type === selectedDatasetType ? 'active' : ''}`}
            onClick={() => onSelectDataset(dataset.dataset_type)}
          >
            <div className="dataset-item-main">
              {dataset.symbol_required ? <TrendingUp size={16} /> : <Globe size={16} />}
              <div className="dataset-item-text">
                <span className="dataset-label">{dataset.label}</span>
                <span className="dataset-type">{dataset.dataset_type}</span>
              </div>
            </div>
            <span className="dataset-meta">
              <span className="dataset-source">{dataset.source_name}</span>
              <span className="dataset-ttl">TTL {formatTTL(dataset.ttl_seconds)}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
