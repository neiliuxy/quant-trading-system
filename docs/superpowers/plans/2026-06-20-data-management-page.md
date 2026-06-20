# Data Management Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ops-focused Data Management view in the existing React dashboard for browsing DataHub datasets, inspecting cache records, triggering refreshes, and tracking session-created refresh jobs.

**Architecture:** Keep the existing single-page dashboard shell. Add a small top-level view switch in `App.tsx`, keep backtest behavior unchanged, and place all new data-management behavior in focused files under `web/src/data-management/`. The page is dataset-driven: datasets load first, the current segment's first dataset is selected automatically, and cache queries always include a concrete `dataset_type`.

**Tech Stack:** React + TypeScript + Vite + Vitest + React Testing Library, existing `fetch` API wrapper pattern in `web/src/api.ts`, existing CSS in `web/src/styles.css`, lucide-react icons for visible actions.

---

## Source Spec

Implement [docs/superpowers/specs/2026-06-20-data-management-page-design.md](/Users/neiliuxy/Workspace/quntx/quant-trading-system/docs/superpowers/specs/2026-06-20-data-management-page-design.md).

Key constraints from the spec:

- Do not add backend endpoints.
- Do not change DataHub backend behavior.
- Split datasets into `个股` and `大盘` using `symbol_required`.
- Initial cache query must happen after datasets load, using the selected dataset's `dataset_type`.
- `Refresh Queue` only shows refreshes created in the current frontend session.
- Do not build batch refresh, global refresh history, TTL editing, source editing, e2e tests, or charts.

## File Structure

Create:

- `web/src/api.test.ts`: unit tests for DataHub API wrappers using `global.fetch`.
- `web/src/data-management/DatasetCatalog.tsx`: presentational dataset list and segment control.
- `web/src/data-management/DatasetCatalog.test.tsx`: catalog rendering and selection tests.
- `web/src/data-management/CacheTable.tsx`: cache filter form and cache records table.
- `web/src/data-management/CacheTable.test.tsx`: filter form, symbol visibility, loading, empty, error rendering tests.
- `web/src/data-management/RefreshQueue.tsx`: session refresh queue and selected refresh detail.
- `web/src/data-management/RefreshQueue.test.tsx`: status and empty-state tests.
- `web/src/data-management/DataManagementView.tsx`: container for data loading, dataset selection, cache querying, refresh creation, polling, and completion-triggered cache reload.
- `web/src/data-management/DataManagementView.test.tsx`: integration-level component tests with mocked API functions.
- `web/src/App.test.tsx`: top-level smoke test for Backtest / Data Management view switching.

Modify:

- `web/src/types.ts`: add DataHub frontend types.
- `web/src/api.ts`: add DataHub API wrappers.
- `web/src/App.tsx`: add top-level `Backtest` / `Data Management` view switch and render `DataManagementView`.
- `web/src/styles.css`: add compact ops-page layout and responsive rules.

Do not modify:

- `server/api.py`
- `datahub/`
- backtest logic
- existing chart panels

---

### Task 1: Add DataHub Types and API Wrappers

**Files:**

- Modify: `web/src/types.ts`
- Modify: `web/src/api.ts`
- Create: `web/src/api.test.ts`

- [ ] **Step 1: Add failing API wrapper tests**

Create `web/src/api.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { createRefresh, getRefresh, listCache, listDatasets } from './api';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

function mockJsonResponse(payload: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(payload),
    text: () => Promise.resolve(typeof payload === 'string' ? payload : JSON.stringify(payload)),
  } as Response);
}

describe('datahub api wrappers', () => {
  it('lists datasets from the datahub endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      await mockJsonResponse([
        {
          dataset_type: 'stock_daily',
          label: 'A股日线',
          columns: ['date', 'open', 'high', 'low', 'close', 'volume'],
          symbol_required: true,
          source_name: 'akshare',
          ttl_seconds: 86400,
          historical_ttl_seconds: null,
        },
      ])
    );

    const datasets = await listDatasets();

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/data/datasets`, {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(datasets[0].dataset_type).toBe('stock_daily');
    expect(datasets[0].symbol_required).toBe(true);
  });

  it('serializes cache query params and omits empty values', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(await mockJsonResponse([]));

    await listCache({
      dataset_type: 'stock_daily',
      symbol: '000001',
      start: '20240101',
      end: '',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/data/cache?dataset_type=stock_daily&symbol=000001&start=20240101`,
      { headers: { 'Content-Type': 'application/json' } }
    );
  });

  it('creates a refresh with the backend payload shape', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      await mockJsonResponse({
        id: 7,
        request_key: 'stock_daily:000001:daily:20240101:20240131:false',
        dataset_type: 'stock_daily',
        symbol: '000001',
        frequency: 'daily',
        start_date: '20240101',
        end_date: '20240131',
        force_refresh: 0,
        status: 'queued',
        cache_hit: 0,
        error_type: null,
        error_message: null,
        output_cache_path: null,
        created_at: '2026-06-20 10:00:00',
        started_at: null,
        finished_at: null,
        updated_at: '2026-06-20 10:00:00',
      })
    );

    const refresh = await createRefresh({
      dataset_type: 'stock_daily',
      symbol: '000001',
      start: '20240101',
      end: '20240131',
      frequency: 'daily',
      force_refresh: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/data/refresh`, {
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
      body: JSON.stringify({
        dataset_type: 'stock_daily',
        symbol: '000001',
        start: '20240101',
        end: '20240131',
        frequency: 'daily',
        force_refresh: false,
      }),
    });
    expect(refresh.status).toBe('queued');
  });

  it('gets refresh detail by id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      await mockJsonResponse({
        id: 7,
        request_key: 'index_daily:global:daily:20240101:20240131:false',
        dataset_type: 'index_daily',
        symbol: null,
        frequency: 'daily',
        start_date: '20240101',
        end_date: '20240131',
        force_refresh: 0,
        status: 'completed',
        cache_hit: 1,
        error_type: null,
        error_message: null,
        output_cache_path: '/tmp/index.csv',
        created_at: '2026-06-20 10:00:00',
        started_at: '2026-06-20 10:00:01',
        finished_at: '2026-06-20 10:00:02',
        updated_at: '2026-06-20 10:00:02',
      })
    );

    const refresh = await getRefresh(7);

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/data/refresh/7`, {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(refresh.output_cache_path).toBe('/tmp/index.csv');
  });

  it('preserves FastAPI error envelopes in rejected request messages', async () => {
    const payload = {
      detail: {
        error_type: 'refresh_in_progress',
        message: 'Refresh already running: 12',
        refresh_id: 12,
      },
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(await mockJsonResponse(payload, false, 409));

    await expect(
      createRefresh({
        dataset_type: 'stock_daily',
        symbol: '000001',
        start: '20240101',
        end: '20240131',
        frequency: 'daily',
        force_refresh: true,
      })
    ).rejects.toThrow(JSON.stringify(payload));
  });
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd web && npm test -- api.test.ts
```

Expected: FAIL because `listDatasets`, `listCache`, `createRefresh`, and `getRefresh` are not exported from `web/src/api.ts`.

- [ ] **Step 3: Add DataHub types**

Append these definitions to `web/src/types.ts`:

```ts
export type DataSegment = 'stock' | 'index';

export type DataRefreshStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface DatasetSpec {
  dataset_type: string;
  label: string;
  columns: string[];
  symbol_required: boolean;
  source_name: string;
  ttl_seconds: number | null;
  historical_ttl_seconds: number | null;
}

export interface CacheEntry {
  id: number;
  dataset_type: string;
  symbol: string | null;
  frequency: string;
  start_date: string;
  end_date: string;
  file_path: string;
  row_count: number;
  schema_version: string;
  source_name: string;
  expires_at: string | null;
  created_at: string;
  refreshed_at: string;
}

export interface DataRefresh {
  id: number;
  request_key: string;
  dataset_type: string;
  symbol: string | null;
  frequency: string;
  start_date: string;
  end_date: string;
  force_refresh: number;
  status: DataRefreshStatus;
  cache_hit: number;
  error_type: string | null;
  error_message: string | null;
  output_cache_path: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
}

export interface DataRefreshPayload {
  dataset_type: string;
  symbol?: string | null;
  start: string;
  end: string;
  frequency: string;
  force_refresh: boolean;
}

export interface CacheQueryParams {
  dataset_type?: string;
  symbol?: string;
  start?: string;
  end?: string;
}
```

- [ ] **Step 4: Add API wrapper imports and functions**

Change the first import in `web/src/api.ts` to include the new types:

```ts
import type {
  BacktestResult,
  CacheEntry,
  CacheQueryParams,
  ComparisonResponse,
  DataRefresh,
  DataRefreshPayload,
  DatasetSpec,
  Job,
  StrategySpec,
} from './types';
```

Add this helper below `request<T>`:

```ts
function queryString(params: Record<string, string | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, value);
    }
  });
  const serialized = search.toString();
  return serialized ? `?${serialized}` : '';
}
```

Add these functions before `getStocks`:

```ts
export function listDatasets(): Promise<DatasetSpec[]> {
  return request<DatasetSpec[]>('/api/data/datasets');
}

export function listCache(params: CacheQueryParams = {}): Promise<CacheEntry[]> {
  return request<CacheEntry[]>(`/api/data/cache${queryString(params)}`);
}

export function createRefresh(payload: DataRefreshPayload): Promise<DataRefresh> {
  return request<DataRefresh>('/api/data/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getRefresh(refreshId: number): Promise<DataRefresh> {
  return request<DataRefresh>(`/api/data/refresh/${refreshId}`);
}
```

- [ ] **Step 5: Run the focused test and verify it passes**

Run:

```bash
cd web && npm test -- api.test.ts
```

Expected: PASS for all tests in `api.test.ts`.

- [ ] **Step 6: Commit**

Run:

```bash
git add web/src/types.ts web/src/api.ts web/src/api.test.ts
git commit -m "feat(web): add datahub api client"
```

---

### Task 2: Build Presentational Data Management Components

**Files:**

- Create: `web/src/data-management/DatasetCatalog.tsx`
- Create: `web/src/data-management/DatasetCatalog.test.tsx`
- Create: `web/src/data-management/CacheTable.tsx`
- Create: `web/src/data-management/CacheTable.test.tsx`
- Create: `web/src/data-management/RefreshQueue.tsx`
- Create: `web/src/data-management/RefreshQueue.test.tsx`

- [ ] **Step 1: Write failing tests for `DatasetCatalog`**

Create `web/src/data-management/DatasetCatalog.test.tsx`:

```tsx
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
    expect(screen.getByText('TTL 86400s')).toBeInTheDocument();
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
```

- [ ] **Step 2: Write failing tests for `CacheTable`**

Create `web/src/data-management/CacheTable.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import CacheTable from './CacheTable';
import type { CacheEntry, DatasetSpec } from '../types';

const stockDataset: DatasetSpec = {
  dataset_type: 'stock_daily',
  label: 'A股日线',
  columns: ['date', 'open', 'high', 'low', 'close', 'volume'],
  symbol_required: true,
  source_name: 'akshare',
  ttl_seconds: 86400,
  historical_ttl_seconds: null,
};

const indexDataset: DatasetSpec = {
  ...stockDataset,
  dataset_type: 'index_daily',
  label: '大盘指数',
  symbol_required: false,
};

const entries: CacheEntry[] = [
  {
    id: 1,
    dataset_type: 'stock_daily',
    symbol: '000001',
    frequency: 'daily',
    start_date: '20240101',
    end_date: '20240131',
    file_path: '/data/cache/stock_daily/000001_20240101_20240131.csv',
    row_count: 20,
    schema_version: 'v1',
    source_name: 'akshare',
    expires_at: null,
    created_at: '2026-06-20 10:00:00',
    refreshed_at: '2026-06-20 10:00:00',
  },
];

describe('CacheTable', () => {
  it('submits dataset-driven cache filters', () => {
    const onQuery = vi.fn();
    const onRefresh = vi.fn();

    render(
      <CacheTable
        selectedDataset={stockDataset}
        entries={entries}
        loading={false}
        error={null}
        onQuery={onQuery}
        onRefresh={onRefresh}
        refreshing={false}
      />
    );

    fireEvent.change(screen.getByLabelText('Symbol'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2024-02-01' } });
    fireEvent.change(screen.getByLabelText('End'), { target: { value: '2024-02-29' } });
    fireEvent.click(screen.getByRole('button', { name: /查询缓存/ }));

    expect(onQuery).toHaveBeenCalledWith({
      dataset_type: 'stock_daily',
      symbol: '600519',
      start: '20240201',
      end: '20240229',
    });
  });

  it('hides symbol input for index datasets and submits refresh payload', () => {
    const onQuery = vi.fn();
    const onRefresh = vi.fn();

    render(
      <CacheTable
        selectedDataset={indexDataset}
        entries={[]}
        loading={false}
        error={null}
        onQuery={onQuery}
        onRefresh={onRefresh}
        refreshing={false}
      />
    );

    expect(screen.queryByLabelText('Symbol')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Refresh start'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('Refresh end'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    expect(onRefresh).toHaveBeenCalledWith({
      dataset_type: 'index_daily',
      symbol: null,
      start: '20240101',
      end: '20240131',
      frequency: 'daily',
      force_refresh: false,
    });
  });

  it('renders loading, error, empty, and table states', () => {
    const props = {
      selectedDataset: stockDataset,
      onQuery: vi.fn(),
      onRefresh: vi.fn(),
      refreshing: false,
    };

    const { rerender } = render(<CacheTable {...props} entries={[]} loading error={null} />);
    expect(screen.getByText('缓存加载中...')).toBeInTheDocument();

    rerender(<CacheTable {...props} entries={[]} loading={false} error="cache failed" />);
    expect(screen.getByText('cache failed')).toBeInTheDocument();

    rerender(<CacheTable {...props} entries={[]} loading={false} error={null} />);
    expect(screen.getByText('没有匹配的缓存条目')).toBeInTheDocument();

    rerender(<CacheTable {...props} entries={entries} loading={false} error={null} />);
    expect(screen.getByText('000001')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Write failing tests for `RefreshQueue`**

Create `web/src/data-management/RefreshQueue.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import RefreshQueue from './RefreshQueue';
import type { DataRefresh } from '../types';

function refresh(status: DataRefresh['status'], id = 1): DataRefresh {
  return {
    id,
    request_key: `key-${id}`,
    dataset_type: 'stock_daily',
    symbol: '000001',
    frequency: 'daily',
    start_date: '20240101',
    end_date: '20240131',
    force_refresh: 0,
    status,
    cache_hit: 0,
    error_type: status === 'failed' ? 'source_unavailable' : null,
    error_message: status === 'failed' ? 'network failed' : null,
    output_cache_path: status === 'completed' ? '/data/cache/file.csv' : null,
    created_at: '2026-06-20 10:00:00',
    started_at: status === 'queued' ? null : '2026-06-20 10:00:01',
    finished_at: status === 'queued' || status === 'running' ? null : '2026-06-20 10:00:02',
    updated_at: '2026-06-20 10:00:02',
  };
}

describe('RefreshQueue', () => {
  it('renders empty queue state', () => {
    render(<RefreshQueue refreshes={[]} selectedRefreshId={null} onSelectRefresh={vi.fn()} pollingIds={new Set()} />);

    expect(screen.getByText('当前会话尚未发起刷新任务')).toBeInTheDocument();
  });

  it('renders all refresh statuses and selected details', () => {
    render(
      <RefreshQueue
        refreshes={[refresh('queued', 1), refresh('running', 2), refresh('completed', 3), refresh('failed', 4)]}
        selectedRefreshId={4}
        onSelectRefresh={vi.fn()}
        pollingIds={new Set([2])}
      />
    );

    expect(screen.getByText('queued')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getAllByText('failed')).toHaveLength(2);
    expect(screen.getByText('轮询中')).toBeInTheDocument();
    expect(screen.getByText('source_unavailable')).toBeInTheDocument();
    expect(screen.getByText('network failed')).toBeInTheDocument();
  });

  it('emits selected refresh id', () => {
    const onSelectRefresh = vi.fn();

    render(
      <RefreshQueue
        refreshes={[refresh('queued', 7)]}
        selectedRefreshId={null}
        onSelectRefresh={onSelectRefresh}
        pollingIds={new Set()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /#7 stock_daily/ }));

    expect(onSelectRefresh).toHaveBeenCalledWith(7);
  });
});
```

- [ ] **Step 4: Run component tests and verify they fail**

Run:

```bash
cd web && npm test -- DatasetCatalog.test.tsx CacheTable.test.tsx RefreshQueue.test.tsx
```

Expected: FAIL because the three component files do not exist.

- [ ] **Step 5: Implement `DatasetCatalog`**

Create `web/src/data-management/DatasetCatalog.tsx`:

```tsx
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
```

- [ ] **Step 6: Implement `CacheTable`**

Create `web/src/data-management/CacheTable.tsx`:

```tsx
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
```

The `frequency` control intentionally exposes only `daily` in v1. The backend payload supports `frequency`, but no additional frontend choices are in scope until a dataset spec needs them.

- [ ] **Step 7: Implement `RefreshQueue`**

Create `web/src/data-management/RefreshQueue.tsx`:

```tsx
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
```

- [ ] **Step 8: Run component tests and verify they pass**

Run:

```bash
cd web && npm test -- DatasetCatalog.test.tsx CacheTable.test.tsx RefreshQueue.test.tsx
```

Expected: PASS for all three component test files.

- [ ] **Step 9: Commit**

Run:

```bash
git add web/src/data-management/DatasetCatalog.tsx web/src/data-management/DatasetCatalog.test.tsx web/src/data-management/CacheTable.tsx web/src/data-management/CacheTable.test.tsx web/src/data-management/RefreshQueue.tsx web/src/data-management/RefreshQueue.test.tsx
git commit -m "feat(web): add data management panels"
```

---

### Task 3: Build `DataManagementView` State Orchestration

**Files:**

- Create: `web/src/data-management/DataManagementView.tsx`
- Create: `web/src/data-management/DataManagementView.test.tsx`

- [ ] **Step 1: Write failing orchestration tests**

Create `web/src/data-management/DataManagementView.test.tsx`:

```tsx
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DataManagementView from './DataManagementView';
import { createRefresh, getRefresh, listCache, listDatasets } from '../api';
import type { CacheEntry, DataRefresh, DatasetSpec } from '../types';

vi.mock('../api', () => ({
  listDatasets: vi.fn(),
  listCache: vi.fn(),
  createRefresh: vi.fn(),
  getRefresh: vi.fn(),
}));

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

const stockCache: CacheEntry[] = [
  {
    id: 1,
    dataset_type: 'stock_daily',
    symbol: '000001',
    frequency: 'daily',
    start_date: '20240101',
    end_date: '20240131',
    file_path: '/data/cache/stock_daily/000001_20240101_20240131.csv',
    row_count: 20,
    schema_version: 'v1',
    source_name: 'akshare',
    expires_at: null,
    created_at: '2026-06-20 10:00:00',
    refreshed_at: '2026-06-20 10:00:00',
  },
];

function refresh(status: DataRefresh['status'], id = 9): DataRefresh {
  return {
    id,
    request_key: `key-${id}`,
    dataset_type: 'stock_daily',
    symbol: '000001',
    frequency: 'daily',
    start_date: '20240101',
    end_date: '20240131',
    force_refresh: 0,
    status,
    cache_hit: 0,
    error_type: null,
    error_message: null,
    output_cache_path: status === 'completed' ? '/data/cache/stock_daily/file.csv' : null,
    created_at: '2026-06-20 10:00:00',
    started_at: status === 'queued' ? null : '2026-06-20 10:00:01',
    finished_at: status === 'completed' ? '2026-06-20 10:00:02' : null,
    updated_at: '2026-06-20 10:00:02',
  };
}

describe('DataManagementView', () => {
  beforeEach(() => {
    vi.mocked(listDatasets).mockResolvedValue(datasets);
    vi.mocked(listCache).mockResolvedValue(stockCache);
    vi.mocked(createRefresh).mockResolvedValue(refresh('queued'));
    vi.mocked(getRefresh).mockResolvedValue(refresh('completed'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('selects the first stock dataset and queries cache by dataset_type after datasets load', async () => {
    render(<DataManagementView />);

    expect(await screen.findByText('A股日线')).toBeInTheDocument();

    await waitFor(() => {
      expect(listCache).toHaveBeenCalledWith({ dataset_type: 'stock_daily' });
    });
    expect(screen.getByText('000001')).toBeInTheDocument();
  });

  it('switches to index segment and queries cache for the first index dataset', async () => {
    render(<DataManagementView />);

    fireEvent.click(await screen.findByRole('button', { name: '大盘' }));

    await waitFor(() => {
      expect(listCache).toHaveBeenLastCalledWith({ dataset_type: 'index_daily' });
    });
    expect(screen.queryByLabelText('Symbol')).not.toBeInTheDocument();
  });

  it('creates a refresh, adds it to the queue, polls detail, and reloads cache on completion', async () => {
    // shouldAdvanceTime keeps React Testing Library findBy/waitFor timers moving while polling uses fake timers.
    vi.useFakeTimers({ shouldAdvanceTime: true });

    render(<DataManagementView />);

    await screen.findByText('A股日线');
    fireEvent.change(screen.getByLabelText('Refresh symbol'), { target: { value: '000001' } });
    fireEvent.change(screen.getByLabelText('Refresh start'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('Refresh end'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    await waitFor(() => {
      expect(createRefresh).toHaveBeenCalledWith({
        dataset_type: 'stock_daily',
        symbol: '000001',
        start: '20240101',
        end: '20240131',
        frequency: 'daily',
        force_refresh: false,
      });
    });

    expect(await screen.findByRole('button', { name: /#9 stock_daily/ })).toBeInTheDocument();

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    await waitFor(() => {
      expect(getRefresh).toHaveBeenCalledWith(9);
      expect(listCache).toHaveBeenCalledTimes(2);
      expect(listCache).toHaveBeenLastCalledWith({ dataset_type: 'stock_daily' });
    });

  });

  it('stops polling and keeps the last known refresh when detail polling fails', async () => {
    // shouldAdvanceTime keeps React Testing Library findBy/waitFor timers moving while polling uses fake timers.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getRefresh).mockRejectedValue(new Error('refresh detail failed'));

    render(<DataManagementView />);

    await screen.findByText('A股日线');
    fireEvent.change(screen.getByLabelText('Refresh symbol'), { target: { value: '000001' } });
    fireEvent.change(screen.getByLabelText('Refresh start'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('Refresh end'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    expect(await screen.findByRole('button', { name: /#9 stock_daily/ })).toBeInTheDocument();

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(await screen.findByText('refresh detail failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /#9 stock_daily/ })).toBeInTheDocument();

    // The failed poll removes the id from pollingIds, which reruns the effect
    // and tears down the interval. Wait for the polling badge to disappear so
    // the cleanup has committed before asserting no further calls happen.
    await waitFor(() => {
      expect(screen.queryByText('轮询中')).not.toBeInTheDocument();
    });
    const callsAfterFailure = vi.mocked(getRefresh).mock.calls.length;

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(vi.mocked(getRefresh).mock.calls.length).toBe(callsAfterFailure);
  });

  it('maps refresh_in_progress conflicts to a specific message', async () => {
    vi.mocked(createRefresh).mockRejectedValue(
      new Error(JSON.stringify({ detail: { error_type: 'refresh_in_progress' } }))
    );

    render(<DataManagementView />);

    await screen.findByText('A股日线');
    fireEvent.change(screen.getByLabelText('Refresh symbol'), { target: { value: '000001' } });
    fireEvent.change(screen.getByLabelText('Refresh start'), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText('Refresh end'), { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /刷新数据/ }));

    expect(await screen.findByText('该数据范围已有刷新任务在运行')).toBeInTheDocument();
  });
});
```

This is the first test file in this repo to use `vi.mock` / `vi.mocked`. Keep the mock at module scope, before the tests, so component imports receive the mocked API functions.

- [ ] **Step 2: Run orchestration test and verify it fails**

Run:

```bash
cd web && npm test -- DataManagementView.test.tsx
```

Expected: FAIL because `DataManagementView.tsx` does not exist.

- [ ] **Step 3: Implement `DataManagementView`**

Create `web/src/data-management/DataManagementView.tsx`:

```tsx
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
  const [lastCacheQuery, setLastCacheQuery] = useState<CacheQueryParams | null>(null);
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
    setLastCacheQuery(params);
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
```

- [ ] **Step 4: Run orchestration test and fix any type/test issues**

Run:

```bash
cd web && npm test -- DataManagementView.test.tsx
```

Expected: PASS for `DataManagementView.test.tsx`. Timer advancement is wrapped in Testing Library `act` in the test snippet above:

```tsx
await act(async () => {
  await vi.runOnlyPendingTimersAsync();
});
```

- [ ] **Step 5: Run all data-management tests**

Run:

```bash
cd web && npm test -- api.test.ts DatasetCatalog.test.tsx CacheTable.test.tsx RefreshQueue.test.tsx DataManagementView.test.tsx
```

Expected: PASS for the API and data-management tests.

- [ ] **Step 6: Commit**

Run:

```bash
git add web/src/data-management/DataManagementView.tsx web/src/data-management/DataManagementView.test.tsx
git commit -m "feat(web): orchestrate data management view"
```

---

### Task 4: Wire the View Into `App.tsx` and Add Styles

**Files:**

- Create: `web/src/App.test.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Verify baseline before wiring**

Before editing, inspect the current app manually:

```bash
cd web && npm test
```

Expected: PASS. This confirms the existing frontend suite and the new data-management tests are green before wiring the new view.

- [ ] **Step 2: Add failing App view-switch smoke test**

Create `web/src/App.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { getJob, getResult, getStocks, listJobs, listStrategies } from './api';

vi.mock('./data-management/DataManagementView', () => ({
  default: () => <div>Data Management View</div>,
}));

vi.mock('./api', () => ({
  createJob: vi.fn(),
  createMarketFilterComparison: vi.fn(),
  deleteAllJobs: vi.fn(),
  deleteJob: vi.fn(),
  getJob: vi.fn(),
  getResult: vi.fn(),
  getStocks: vi.fn(),
  listJobs: vi.fn(),
  listStrategies: vi.fn(),
}));

describe('App view switching', () => {
  beforeEach(() => {
    vi.mocked(getStocks).mockResolvedValue([]);
    vi.mocked(listJobs).mockResolvedValue([]);
    vi.mocked(listStrategies).mockResolvedValue([
      {
        id: 'swing_ma_boll',
        name: 'Swing MA Boll',
        description: 'demo strategy',
        params: [{ name: 'fast_ma', label: 'Fast MA', type: 'int', default: 10 }],
      },
    ]);
    // Defensive fallbacks: App never selects a job from an empty job list, but
    // give these a resolved value so any re-render that touches the polling
    // effects cannot throw on undefined return values.
    vi.mocked(getJob).mockResolvedValue({
      id: 0,
      run_key: '',
      status: 'completed',
      symbol: '000001',
      start_date: '20240101',
      end_date: '20240131',
      cash: 100000,
      use_market_filter: true,
      risk_percent: 0.95,
      fast_ma: 10,
      slow_ma: 20,
      strategy_id: 'swing_ma_boll',
      strategy_params_json: '{}',
      code_version: '',
      cache_hit: false,
      error: null,
      created_at: '2026-06-20 10:00:00',
      updated_at: '2026-06-20 10:00:00',
    });
    vi.mocked(getResult).mockResolvedValue({
      symbol: '000001',
      start: '20240101',
      end: '20240131',
      initial_cash: 100000,
      final_value: 100000,
      total_return_pct: 0,
      max_drawdown_pct: 0,
      trade_count: 0,
      win_rate_pct: 0,
      equity_curve: [],
      trades: [],
      market_scores: [],
      market_score_summary: {},
      price_data: [],
      index_data: [],
    });
  });

  it('keeps the backtest view available when switching to and from data management', async () => {
    render(<App />);

    expect(await screen.findByRole('button', { name: /开始回测/ })).toBeInTheDocument();
    expect(screen.getByText('历史记录')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Data Management/ }));

    expect(screen.getByText('Data Management View')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /开始回测/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Backtest/ }));

    expect(await screen.findByRole('button', { name: /开始回测/ })).toBeInTheDocument();
    expect(screen.getByText('历史记录')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the App smoke test and verify it fails**

Run:

```bash
cd web && npm test -- App.test.tsx
```

Expected: FAIL because `Data Management` / `Backtest` view-switch controls do not exist yet.

- [ ] **Step 4: Wire `DataManagementView` into `App.tsx`**

In `web/src/App.tsx`, update imports:

```tsx
import { Activity, BookOpen, Database, LineChart, Play, RefreshCcw, Trash2 } from 'lucide-react';
import DataManagementView from './data-management/DataManagementView';
```

Add state near the other top-level UI state:

```tsx
const [activeView, setActiveView] = useState<'backtest' | 'data'>('backtest');
```

Add a view switch below the `brand-row` and before `RunForm`:

```tsx
<div className="view-switch" role="group" aria-label="Primary view">
  <button
    type="button"
    className={activeView === 'backtest' ? 'active' : ''}
    onClick={() => setActiveView('backtest')}
  >
    <LineChart size={16} />
    Backtest
  </button>
  <button
    type="button"
    className={activeView === 'data' ? 'active' : ''}
    onClick={() => setActiveView('data')}
  >
    <Database size={16} />
    Data Management
  </button>
</div>
```

Keep the existing `RunForm` and history section visible only for backtests:

```tsx
{activeView === 'backtest' && (
  <>
    <RunForm
      initialValue={runFormDefaults}
      strategies={strategies}
      submitting={submitting}
      hasSelectedJob={Boolean(selectedJob)}
      onSubmit={submit}
      onCompareMarketFilter={compareMarketFilter}
    />

    <section className="history">
      ...
    </section>
  </>
)}
```

In the `content-panel`, render `DataManagementView` when selected. In the backtest branch, move the current `content-panel` children as one unchanged block: the error banner, selected-job header, result branch, chart panels, trade table, index fallback, and empty state currently inside `web/src/App.tsx`.

Required shape:

```tsx
<section className="content-panel">
  {activeView === 'data' ? (
    <DataManagementView />
  ) : (
    <>
      {/* Move the existing backtest content-panel children here unchanged. */}
    </>
  )}
</section>
```

Keep the existing delete modals outside that conditional so existing behavior remains unchanged when returning to the backtest view.

- [ ] **Step 5: Add ops-page styles**

Append to `web/src/styles.css`:

```css
.view-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 18px;
}

.view-switch button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid #cbd5df;
  border-radius: 6px;
  background: #fff;
  color: #405060;
  padding: 9px;
  cursor: pointer;
}

.view-switch button.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.data-management-view {
  min-width: 0;
}

.data-management-grid {
  display: grid;
  grid-template-columns: 220px minmax(340px, 1fr) 260px;
  gap: 16px;
  align-items: start;
}

.data-panel {
  background: #fff;
  border: 1px solid #d9e1e8;
  border-radius: 8px;
  padding: 14px;
  min-width: 0;
}

.data-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.data-panel-header h3,
.refresh-form h4 {
  margin: 0;
}

.muted {
  color: #627282;
  font-size: 13px;
}

.segment-control {
  display: flex;
  gap: 6px;
}

.segment-control button {
  border: 1px solid #cbd5df;
  border-radius: 4px;
  background: #fff;
  color: #405060;
  padding: 6px 10px;
  cursor: pointer;
}

.segment-control button.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.dataset-list,
.refresh-list {
  display: grid;
  gap: 8px;
}

.dataset-item,
.refresh-item {
  width: 100%;
  border: 1px solid #e5ebf1;
  border-radius: 6px;
  background: #fff;
  color: #17202a;
  padding: 10px;
  text-align: left;
  cursor: pointer;
}

.dataset-item.active,
.refresh-item.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.dataset-label,
.dataset-type {
  display: block;
}

.dataset-label {
  font-weight: 600;
}

.dataset-type,
.dataset-meta,
.polling-label {
  color: #627282;
  font-size: 12px;
}

.dataset-meta {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}

.data-filter-form,
.refresh-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  align-items: end;
  margin-bottom: 14px;
}

.refresh-form {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #e5ebf1;
}

.data-filter-form label,
.refresh-form label {
  display: grid;
  gap: 6px;
  color: #405060;
  font-size: 13px;
}

.refresh-form label.check-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.data-filter-form input,
.refresh-form input,
.refresh-form select {
  border: 1px solid #cbd5df;
  border-radius: 4px;
  padding: 8px;
  background: #fff;
}

.data-table-scroll {
  overflow-x: auto;
}

.mono-cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.refresh-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px;
  align-items: center;
}

.polling-label {
  grid-column: 1 / -1;
}

.refresh-detail {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px 10px;
  margin: 14px 0 0;
  font-size: 13px;
}

.refresh-detail dt {
  color: #627282;
}

.refresh-detail dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}

@media (max-width: 1440px) {
  .data-management-grid {
    grid-template-columns: 200px minmax(320px, 1fr) 240px;
  }
}

@media (max-width: 980px) {
  .data-management-grid {
    grid-template-columns: 1fr;
  }

  .data-filter-form,
  .refresh-form {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run frontend unit tests**

Run:

```bash
cd web && npm test
```

Expected: PASS for the full Vitest suite.

- [ ] **Step 7: Run type check and production build**

Run:

```bash
cd web && npx tsc --noEmit
cd web && npm run build
```

Expected: TypeScript check exits 0, then Vite build exits 0.

- [ ] **Step 8: Commit**

Run:

```bash
git add web/src/App.tsx web/src/App.test.tsx web/src/styles.css
git commit -m "feat(web): add data management view switch"
```

---

### Task 5: Manual Browser Verification

**Files:**

- No source edits expected.

- [ ] **Step 1: Start backend**

Run:

```bash
python server/main.py
```

Expected: FastAPI server listens on `http://127.0.0.1:8000`.

- [ ] **Step 2: Start frontend**

Run in a second terminal:

```bash
cd web && npm run dev
```

Expected: Vite server listens on `http://127.0.0.1:5173`.

- [ ] **Step 3: Verify page behavior manually**

Open `http://127.0.0.1:5173` and verify:

- Backtest view still loads by default.
- Clicking `Data Management` shows the data page.
- `个股` is selected by default.
- The first stock dataset is selected automatically.
- Cache table requests use that dataset's `dataset_type`.
- Switching to `大盘` hides symbol inputs.
- Starting a refresh adds a row to the right-side queue.
- Refresh status updates until `completed` or `failed`.
- When refresh completes for the same `dataset_type` currently displayed in the cache table, the current cache table reloads.
- Returning to `Backtest` keeps the original form/history workflow usable.

- [ ] **Step 4: Record manual verification result in final handoff**

If both servers run and the browser checks pass, include:

```text
Manual verification: backend http://127.0.0.1:8000 and frontend http://127.0.0.1:5173; Data Management view loaded, segment switching worked, refresh queue updated, backtest view still usable.
```

If backend data source calls fail because akshare/network is unavailable, include:

```text
Manual verification: UI loaded and API error states rendered; live refresh could not complete because the data source request failed with <exact error>.
```

---

## Final Verification

Run these commands before claiming implementation completion:

```bash
cd web && npm test
cd web && npx tsc --noEmit
cd web && npm run build
python -m pytest -q tests/
git status --short
```

Expected:

- Vitest exits 0.
- TypeScript check exits 0.
- Vite build exits 0.
- Python pytest exits 0.
- `git status --short` contains only intended source changes or is clean after commits.

## Plan Self-Review

Spec coverage:

- Dataset catalog: Task 2.
- Cache inspection with concrete `dataset_type`: Task 2 builds the cache UI, Task 3 wires dataset-driven queries.
- Single refresh and polling: Tasks 1, 2, and 3.
- Refresh polling failure keeps the last known state and stops retrying: Task 3.
- Session-local refresh queue: Tasks 2 and 3.
- Existing dashboard integration and view-switch regression coverage: Task 4.
- Visual direction and responsive layout: Task 4.
- Tests: Tasks 1 through 4.
- Manual verification: Task 5.

No backend endpoints are added. No batch refresh, global refresh history, TTL editing, source editing, e2e tests, or DataHub backend changes are included.
