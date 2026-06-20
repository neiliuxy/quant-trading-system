import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DatasetCatalog from './DatasetCatalog';
import type { DatasetSpec } from '../types';

const datasets: DatasetSpec[] = [
  {
    dataset_type: 'stock_daily',
    label: 'A股日线',
    columns: ['date', 'open', 'high', 'low', 'close', 'volume'],
    symbol_required: true,
    source_name: 'akshare',
    ttl_seconds: 86400,
    historical_ttl_seconds: null,
  },
  {
    dataset_type: 'index_daily',
    label: '大盘指数',
    columns: ['date', 'open', 'high', 'low', 'close', 'volume', 'amount'],
    symbol_required: false,
    source_name: 'akshare',
    ttl_seconds: 86400,
    historical_ttl_seconds: null,
  },
];

describe('DatasetCatalog', () => {
  it('renders only datasets for the active stock segment', () => {
    render(
      <DatasetCatalog
        segment="stock"
        datasets={datasets}
        selectedDatasetType="stock_daily"
        loading={false}
        onChangeSegment={vi.fn()}
        onSelectDataset={vi.fn()}
      />
    );

    expect(screen.getByText('A股日线')).toBeInTheDocument();
    expect(screen.queryByText('大盘指数')).not.toBeInTheDocument();
    expect(screen.getByText('akshare')).toBeInTheDocument();
    expect(screen.getByText('TTL 1d')).toBeInTheDocument();
  });

  it('emits segment and dataset selection events', () => {
    const onChangeSegment = vi.fn();
    const onSelectDataset = vi.fn();

    render(
      <DatasetCatalog
        segment="stock"
        datasets={datasets}
        selectedDatasetType="stock_daily"
        loading={false}
        onChangeSegment={onChangeSegment}
        onSelectDataset={onSelectDataset}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '大盘' }));
    fireEvent.click(screen.getByRole('button', { name: /A股日线/ }));

    expect(onChangeSegment).toHaveBeenCalledWith('index');
    expect(onSelectDataset).toHaveBeenCalledWith('stock_daily');
  });
});
