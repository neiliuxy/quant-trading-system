import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
          <h3>{t('dataMgmt.catalogTitle')}</h3>
          <p className="muted">{t('dataMgmt.availableCount', { count: visibleDatasets.length })}</p>
        </div>
      </div>

      <div className="segment-control" role="group" aria-label="Data segment">
        {(['stock', 'index'] as DataSegment[]).map((key) => (
          <button
            key={key}
            type="button"
            className={key === segment ? 'active' : ''}
            onClick={() => onChangeSegment(key)}
          >
            {key === 'stock' ? <TrendingUp size={14} /> : <Globe size={14} />}
            {t(`dataMgmt.segment.${key}`)}
          </button>
        ))}
      </div>

      <div className="catalog-search">
        <Search size={14} />
        <input
          type="text"
          placeholder={t('dataMgmt.searchPlaceholder')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {loading && (
        <div className="state-message">
          <span className="spinner" />
          {t('dataMgmt.catalogLoading')}
        </div>
      )}

      {!loading && filteredDatasets.length === 0 && (
        <p className="muted">{query ? t('dataMgmt.noMatch') : t('dataMgmt.segmentEmpty')}</p>
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
              <span className="dataset-ttl">{t('dataMgmt.ttl', { value: formatTTL(dataset.ttl_seconds) })}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
