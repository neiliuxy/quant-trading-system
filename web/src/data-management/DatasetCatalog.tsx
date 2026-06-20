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

export default function DatasetCatalog({
  segment,
  datasets,
  selectedDatasetType,
  loading,
  onChangeSegment,
  onSelectDataset,
}: DatasetCatalogProps) {
  const visibleDatasets = datasets.filter((dataset) => datasetSegment(dataset) === segment);

  return (
    <section className="data-panel data-catalog">
      <div className="data-panel-header">
        <h3>Dataset Catalog</h3>
        <div className="segment-control" role="group" aria-label="Data segment">
          {(Object.keys(segmentLabels) as DataSegment[]).map((key) => (
            <button
              key={key}
              type="button"
              className={key === segment ? 'active' : ''}
              onClick={() => onChangeSegment(key)}
            >
              {segmentLabels[key]}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="muted">数据集加载中...</p>}

      {!loading && visibleDatasets.length === 0 && <p className="muted">当前分段没有可用数据集</p>}

      <div className="dataset-list">
        {visibleDatasets.map((dataset) => (
          <button
            key={dataset.dataset_type}
            type="button"
            className={`dataset-item ${dataset.dataset_type === selectedDatasetType ? 'active' : ''}`}
            onClick={() => onSelectDataset(dataset.dataset_type)}
          >
            <span className="dataset-label">{dataset.label}</span>
            <span className="dataset-type">{dataset.dataset_type}</span>
            <span className="dataset-meta">
              <span>{dataset.source_name}</span>
              <span>TTL {dataset.ttl_seconds ?? 'none'}s</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
