# K 线图重构 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `web/src/App.tsx` 中由 Recharts 拼凑的两处 K 线图（个股回测 K 线、上证指数 K 线）替换为 TradingView Lightweight Charts，提升显示细腻度、缩放/平移/十字光标体验、买卖点对齐精度。

**Architecture:**
- 抽取 5 个 panel 组件（EquityPanel / StockKlinePanel / StockIndicatorPanel / IndexKlinePanel / IndexIndicatorPanel）到 `web/src/panels/`，为集成测试铺路
- 新建 `web/src/charts/` 模块：`filterByDateRange`（统一日期过滤）、`buildSeries`（MA/BOLL + marker 转换）、`useKlineChart`（LC 生命周期 hook）
- 副图与权益曲线继续用 Recharts；LC 仅替换 K 线
- 推迟到未来：K线 ↔ 副图 双向同步（LC + Recharts 不可桥接）

**Tech Stack:**
- TypeScript React 18 + Vite
- Recharts（保留：权益曲线 + 副图）
- TradingView Lightweight Charts v4.2（新增：K 线）
- vitest + @testing-library/react（已有）

**Spec:** `docs/kline-chart-refactor.md`

---

## File Map

| 路径 | 动作 | 阶段 | 行数 |
|---|---|---|---|
| `web/package.json` | 修改 | 0 | +1 |
| `web/src/test/setup.ts` | 修改 | 0 | +50 |
| `web/src/charts/filterByDateRange.ts` | 新建 | 1 | ~10 |
| `web/src/charts/filterByDateRange.test.ts` | 新建 | 1 | ~25 |
| `web/src/charts/buildSeries.ts` | 新建 | 1 | ~45 |
| `web/src/charts/buildSeries.test.ts` | 新建 | 1 | ~50 |
| `web/src/charts/useKlineChart.ts` | 新建 | 2 | ~180 |
| `web/src/charts/useKlineChart.test.tsx` | 新建 | 2 | ~60 |
| `web/src/panels/EquityPanel.tsx` | 新建 | 1 | ~120 |
| `web/src/panels/StockKlinePanel.tsx` | 新建 | 1, 3 | ~140 |
| `web/src/panels/StockIndicatorPanel.tsx` | 新建 | 1 | ~90 |
| `web/src/panels/IndexKlinePanel.tsx` | 新建 | 1, 3 | ~130 |
| `web/src/panels/IndexIndicatorPanel.tsx` | 新建 | 1 | ~90 |
| `web/src/panels/StockKlinePanel.test.tsx` | 新建 | 3 | ~80 |
| `web/src/panels/IndexKlinePanel.test.tsx` | 新建 | 3 | ~80 |
| `web/src/charts/README.md` | 新建 | 4 | ~30 |
| `web/src/App.tsx` | 修改 | 1, 3, 4 | 净减 ~250（1394 → ~1140） |
| `CLAUDE.md` | 修改 | 4 | +2 |

总计：16 个文件变更（2 修改 + 14 新建），App.tsx 净减 ~250 行。

---

## Phase 0：依赖 + 测试基础设施

### Task 1: 添加 lightweight-charts 依赖 + 提交

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: 添加 lightweight-charts 依赖**

编辑 `web/package.json` 的 `dependencies` 段（recharts 之后）：

```json
{
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest",
    "recharts": "latest",
    "lucide-react": "latest",
    "lightweight-charts": "^4.2.0"
  }
}
```

- [ ] **Step 2: 安装依赖**

Run: `cd web && npm install`

Expected: `lightweight-charts@4.2.x` 安装到 `node_modules`，无 ERR。

- [ ] **Step 3: 验证依赖加载**

Run: `cd web && node -e "console.log(require('lightweight-charts').version || 'loaded')"`

Expected: 输出 `loaded` 或版本号字符串（无 throw）。

- [ ] **Step 4: 提交**

```bash
git add web/package.json web/package-lock.json
git commit -m "chore(deps): add lightweight-charts v4.2 for kline chart refactor"
```

---

### Task 2: 添加 ResizeObserver + lightweight-charts 测试 mock

**Files:**
- Modify: `web/src/test/setup.ts`

- [ ] **Step 1: 追加 ResizeObserver mock**

编辑 `web/src/test/setup.ts`：

```ts
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// Lightweight Charts requires ResizeObserver in jsdom (not provided)
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as any;

// Mock lightweight-charts module for unit/integration tests.
// Real chart rendering is verified manually in browser (Phase 3).
vi.mock('lightweight-charts', () => {
  const noop = () => {};
  const seriesApi = {
    setData: noop,
    setMarkers: noop,
    applyOptions: noop,
  };
  return {
    createChart: () => ({
      addCandlestickSeries: () => seriesApi,
      addLineSeries: () => seriesApi,
      addHistogramSeries: () => seriesApi,
      applyOptions: noop,
      remove: noop,
      subscribeCrosshairMove: noop,
      unsubscribeCrosshairMove: noop,
      timeScale: () => ({
        fitContent: noop,
        setVisibleLogicalRange: noop,
      }),
    }),
    CrosshairMode: { Normal: 0, Magnet: 1 },
  };
});
```

- [ ] **Step 2: 运行现有测试，确认无回归**

Run: `cd web && npm run test`

Expected: 已有 2 个测试（ChartDateRangeControl、StrategyParamsForm）通过；mock 加载无报错。

- [ ] **Step 3: 提交**

```bash
git add web/src/test/setup.ts
git commit -m "test(setup): mock ResizeObserver and lightweight-charts for jsdom"
```

---

## Phase 1：工具函数 + 抽取 panel

### Task 3: 实现 filterByDateRange (TDD)

**Files:**
- Create: `web/src/charts/filterByDateRange.ts`
- Create: `web/src/charts/filterByDateRange.test.ts`

- [ ] **Step 1: 写失败测试**

创建 `web/src/charts/filterByDateRange.test.ts`：

```ts
import { describe, expect, it } from 'vitest';
import { filterByDateRange } from './filterByDateRange';

describe('filterByDateRange', () => {
  const rows = [
    { date: '20240101', v: 1 },
    { date: '20240115', v: 2 },
    { date: '20240201', v: 3 },
    { date: '20240215', v: 4 },
  ];

  it('returns input unchanged when range is null', () => {
    expect(filterByDateRange(rows, null)).toEqual(rows);
  });

  it('filters rows within inclusive range', () => {
    const out = filterByDateRange(rows, { start: '20240115', end: '20240201' });
    expect(out.map(r => r.date)).toEqual(['20240115', '20240201']);
  });

  it('returns empty array when no rows match', () => {
    expect(filterByDateRange(rows, { start: '20250101', end: '20250131' })).toEqual([]);
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd web && npm run test -- filterByDateRange`

Expected: FAIL with "Cannot find module './filterByDateRange'" 或类似。

- [ ] **Step 3: 实现 filterByDateRange**

创建 `web/src/charts/filterByDateRange.ts`：

```ts
export interface DateRange {
  start: string;
  end: string;
}

export function filterByDateRange<T extends { date: string }>(
  rows: T[],
  range: DateRange | null
): T[] {
  if (!range) return rows;
  return rows.filter(r => r.date >= range.start && r.date <= range.end);
}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd web && npm run test -- filterByDateRange`

Expected: 3 个测试全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/charts/filterByDateRange.ts web/src/charts/filterByDateRange.test.ts
git commit -m "feat(charts): add filterByDateRange utility"
```

---

### Task 4: 实现 buildSeries (TDD)

**Files:**
- Create: `web/src/charts/buildSeries.ts`
- Create: `web/src/charts/buildSeries.test.ts`

- [ ] **Step 1: 写失败测试**

创建 `web/src/charts/buildSeries.test.ts`：

```ts
import { describe, expect, it } from 'vitest';
import { buildKlineSeries, buildTradeMarkers } from './buildSeries';

const sampleCandles = [
  { date: '20240101', open: 10, high: 11, low: 9.5, close: 10.5, volume: 1000 },
  { date: '20240102', open: 10.5, high: 11.2, low: 10.3, close: 11, volume: 1200 },
  { date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900 },
  { date: '20240104', open: 10.9, high: 11, low: 10.5, close: 10.7, volume: 800 },
  { date: '20240105', open: 10.7, high: 10.9, low: 10.4, close: 10.6, volume: 700 },
];

const sampleTrades = [
  { date: '20240102', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
  { date: '20240105', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
];

describe('buildKlineSeries', () => {
  it('appends MA/BOLL values aligned with input rows', () => {
    const out = buildKlineSeries(sampleCandles);
    expect(out).toHaveLength(5);
    expect(out[0].ma5).toBeNull();
    expect(out[4].ma5).toBeCloseTo(10.74, 2);
    expect(out[0].boll_upper).toBeNull();
    expect(out[4].boll_mid).toBeCloseTo(10.74, 2);
  });

  it('preserves original candle fields', () => {
    const out = buildKlineSeries(sampleCandles);
    expect(out[2]).toMatchObject({
      date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900,
    });
  });
});

describe('buildTradeMarkers', () => {
  it('alternates buy/sell by index (preserves existing semantics)', () => {
    const markers = buildTradeMarkers(sampleTrades);
    expect(markers).toEqual([
      { date: '20240102', side: 'buy' },
      { date: '20240105', side: 'sell' },
    ]);
  });

  it('returns empty array for empty trades', () => {
    expect(buildTradeMarkers([])).toEqual([]);
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd web && npm run test -- buildSeries`

Expected: FAIL with module not found.

- [ ] **Step 3: 实现 buildSeries**

创建 `web/src/charts/buildSeries.ts`：

```ts
import { calcBoll, calcMA } from '../indicators';

export interface CandleInput {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeInput {
  date: string;
  pnl: number;
  pnlcomm: number;
  barlen: number;
  size: number;
}

export interface KlineRow extends CandleInput {
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  boll_upper: number | null;
  boll_mid: number | null;
  boll_lower: number | null;
}

export type TradeSide = 'buy' | 'sell';
export interface TradeMarker {
  date: string;
  side: TradeSide;
}

export function buildKlineSeries(data: CandleInput[]): KlineRow[] {
  const closes = data.map(d => d.close);
  const ma5 = calcMA(closes, 5);
  const ma10 = calcMA(closes, 10);
  const ma20 = calcMA(closes, 20);
  const ma60 = calcMA(closes, 60);
  const { upper, mid, lower } = calcBoll(closes, 20, 2.0);

  return data.map((d, i) => ({
    ...d,
    ma5: ma5[i],
    ma10: ma10[i],
    ma20: ma20[i],
    ma60: ma60[i],
    boll_upper: upper[i],
    boll_mid: mid[i],
    boll_lower: lower[i],
  }));
}

// 复用现有 buildTradeMarkerMap 的偶/奇判定语义（见 App.tsx:124-138）
export function buildTradeMarkers(trades: TradeInput[]): TradeMarker[] {
  return trades.map((t, i) => ({
    date: t.date,
    side: (i % 2 === 0 ? 'buy' : 'sell') as TradeSide,
  }));
}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd web && npm run test -- buildSeries`

Expected: 4 个测试全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/charts/buildSeries.ts web/src/charts/buildSeries.test.ts
git commit -m "feat(charts): add buildKlineSeries and buildTradeMarkers"
```

---

### Task 5: App.tsx 替换 5 处 filteredXxx 为 filterByDateRange

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 引入 filterByDateRange**

在 `web/src/App.tsx` 顶部 imports 区域（约第 24 行 `import { calcMA, ... }` 之后）添加：

```ts
import { filterByDateRange } from './charts/filterByDateRange';
```

- [ ] **Step 2: 替换 5 处 filteredXxx useMemo**

在 `web/src/App.tsx` 中找到 5 个 `filteredXxx` useMemo（`filteredData` 约 344 行、`filteredPriceData` 约 399 行、`filteredStockIndicatorData` 约 451 行、`filteredIndexData` 约 481 行、`filteredIndicatorData` 约 530 行），将每个 memo 体内对 `chartDateRange` 的判断替换为 `filterByDateRange` 调用。

例如 `filteredData`（约 344-360 行）：

```ts
const filteredData = useMemo(() => {
  if (!mergedData.length) return [];
  return filterByDateRange(mergedData, chartDateRange);
}, [mergedData, chartDateRange]);
```

`filteredPriceData`（约 399-410 行）：

```ts
const filteredPriceData = useMemo(() => {
  if (!priceDataWithMA.length) return [];
  return filterByDateRange(priceDataWithMA, chartDateRange);
}, [priceDataWithMA, chartDateRange]);
```

`filteredStockIndicatorData`（约 451-459 行）：

```ts
const filteredStockIndicatorData = useMemo(() => {
  if (!stockIndicatorData.length) return [];
  return filterByDateRange(stockIndicatorData, chartDateRange);
}, [stockIndicatorData, chartDateRange]);
```

`filteredIndexData`（约 481-488 行）：

```ts
const filteredIndexData = useMemo(() => {
  if (!indexDataWithMA.length) return [];
  return filterByDateRange(indexDataWithMA, chartDateRange);
}, [indexDataWithMA, chartDateRange]);
```

`filteredIndicatorData`（约 530-538 行）：

```ts
const filteredIndicatorData = useMemo(() => {
  if (!indexIndicatorData.length) return [];
  return filterByDateRange(indexIndicatorData, chartDateRange);
}, [indexIndicatorData, chartDateRange]);
```

- [ ] **Step 3: 运行测试**

Run: `cd web && npm run test`

Expected: 已有 2 + 3 + 4 = 9 个测试通过（无回归）。

- [ ] **Step 4: 浏览器手动验证**

Run: `cd web && npm run dev`

打开 `http://127.0.0.1:5173`，提交一个回测，确认：
- 权益曲线、个股 K 线、个股副图、上证指数 K 线、指数副图 都正常显示
- 输入 `chartDateRange`（YYYYMMDD）后所有 5 个 panel 同步过滤

- [ ] **Step 5: 提交**

```bash
git add web/src/App.tsx
git commit -m "refactor(App): use filterByDateRange to dedupe 5 filter useMemos"
```

---

### Task 6: 抽取 EquityPanel

**Files:**
- Create: `web/src/panels/EquityPanel.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 创建 EquityPanel.tsx**

创建 `web/src/panels/EquityPanel.tsx`：

```tsx
import { useState } from 'react';
import { Eye, EyeOff, ZoomIn, ZoomOut } from 'lucide-react';
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceDot,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';

export interface EquityPoint {
  date: string;
  value?: number;
  total_score?: number;
  trend_score?: number;
  sentiment_score?: number;
  volume_score?: number;
  buy?: boolean;
  sell?: boolean;
}

export interface LineVisibility {
  equity: boolean;
  totalScore: boolean;
  trendScore: boolean;
  sentimentScore: boolean;
  volumeScore: boolean;
}

export interface EquityPanelProps {
  data: EquityPoint[];
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
  lineVisibility: LineVisibility;
  onToggleLine: (key: keyof LineVisibility) => void;
}

function BuyMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [
    `${cx},${cy - size}`, `${cx - size},${cy + size}`, `${cx + size},${cy + size}`,
  ].join(' ');
  return <polygon points={points} fill="#22c55e" stroke="#15803d" strokeWidth={1} />;
}

function SellMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [
    `${cx},${cy + size}`, `${cx - size},${cy - size}`, `${cx + size},${cy - size}`,
  ].join(' ');
  return <polygon points={points} fill="#ef4444" stroke="#b91c1c" strokeWidth={1} />;
}

export function EquityPanel(props: EquityPanelProps) {
  const [zoom, setZoom] = useState({ start: 0, end: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState(0);

  const filteredData = filterByDateRange(
    props.data,
    props.chartDateRange ?? (props.data.length
      ? null
      : null)
  );

  // Apply zoom only when chartDateRange is not set
  const displayData = props.chartDateRange
    ? filteredData
    : (() => {
        const start = Math.floor((props.data.length * zoom.start) / 100);
        const end = Math.ceil((props.data.length * zoom.end) / 100);
        return props.data.slice(start, end);
      })();

  const buyPoints = displayData.filter(p => p.buy);
  const sellPoints = displayData.filter(p => p.sell);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart(e.clientX);
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const delta = e.clientX - dragStart;
    const range = zoom.end - zoom.start;
    const movePercent = (delta / 800) * 100;
    let newStart = zoom.start - movePercent;
    let newEnd = zoom.end - movePercent;
    if (newStart < 0) { newStart = 0; newEnd = range; }
    if (newEnd > 100) { newEnd = 100; newStart = 100 - range; }
    setZoom({ start: newStart, end: newEnd });
    setDragStart(e.clientX);
  };
  const handleMouseUp = () => setIsDragging(false);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>权益曲线 & 市场评分</h3>
        <div className="zoom-controls">
          <button className="zoom-btn" onClick={() => setZoom({ start: Math.max(0, zoom.start - 10), end: Math.min(100, zoom.end + 10) })}>
            <ZoomOut size={16} /> 缩小
          </button>
          <button className="zoom-btn" onClick={() => setZoom({ start: Math.min(50, zoom.start + 10), end: Math.max(50, zoom.end - 10) })}>
            <ZoomIn size={16} /> 放大
          </button>
          <button className="zoom-btn" onClick={() => setZoom({ start: 0, end: 100 })}>
            重置
          </button>
        </div>
      </div>

      <div className="line-toggles">
        {([
          ['equity', '权益曲线'],
          ['totalScore', '总评分'],
          ['trendScore', '趋势评分'],
          ['sentimentScore', '情绪评分'],
          ['volumeScore', '成交量评分'],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            className={`toggle-btn ${props.lineVisibility[key] ? 'active' : ''}`}
            onClick={() => props.onToggleLine(key)}
          >
            {props.lineVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
            {label}
          </button>
        ))}
      </div>

      <ChartDateRangeControl
        value={props.chartDateRange}
        defaultStart={props.defaultStart}
        defaultEnd={props.defaultEnd}
        onChange={props.onChangeDateRange}
      />

      <div
        className="chart-container"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={displayData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis yAxisId="left" domain={['auto', 'auto']} />
            <YAxis yAxisId="right" orientation="right" domain={[0, 1]} />
            <Tooltip />
            <Legend />
            {props.lineVisibility.equity && (
              <Line yAxisId="left" type="monotone" dataKey="value" stroke="#2563eb" dot={false} strokeWidth={2} name="Equity" isAnimationActive={false} />
            )}
            {props.lineVisibility.totalScore && (
              <Line yAxisId="right" type="monotone" dataKey="total_score" stroke="#0f766e" dot={false} strokeWidth={2} name="Total Score" isAnimationActive={false} />
            )}
            {props.lineVisibility.trendScore && (
              <Line yAxisId="right" type="monotone" dataKey="trend_score" stroke="#f59e0b" dot={false} name="趋势评分" isAnimationActive={false} />
            )}
            {props.lineVisibility.sentimentScore && (
              <Line yAxisId="right" type="monotone" dataKey="sentiment_score" stroke="#7c3aed" dot={false} name="情绪评分" isAnimationActive={false} />
            )}
            {props.lineVisibility.volumeScore && (
              <Line yAxisId="right" type="monotone" dataKey="volume_score" stroke="#dc2626" dot={false} name="Volume Score" isAnimationActive={false} />
            )}
            {buyPoints.map(point => (
              <ReferenceDot key={`buy-${point.date}`} x={point.date} y={point.value} yAxisId="left" shape={BuyMarker} ifOverflow="extendDomain" />
            ))}
            {sellPoints.map(point => (
              <ReferenceDot key={`sell-${point.date}`} x={point.date} y={point.value} yAxisId="left" shape={SellMarker} ifOverflow="extendDomain" />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="chart-hint">Tip: drag the chart left or right to inspect nearby dates.</p>
      <div className="trade-legend">
        <div className="trade-legend-item"><div className="trade-legend-dot buy"></div><span>Buy</span></div>
        <div className="trade-legend-item"><div className="trade-legend-dot sell"></div><span>Sell</span></div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 修改 App.tsx 引入并使用 EquityPanel**

在 `web/src/App.tsx` 顶部 imports 添加：

```ts
import { EquityPanel } from './panels/EquityPanel';
import type { LineVisibility, EquityPoint } from './panels/EquityPanel';
```

将 `App.tsx` 第 759-934 行的权益曲线 panel `<section>` 整段（包含 chart-header、line-toggles、ChartDateRangeControl、chart-container、trade-legend）替换为：

```tsx
<EquityPanel
  data={mergedData}
  chartDateRange={chartDateRange}
  onChangeDateRange={setChartDateRange}
  defaultStart={selectedJob?.start_date || ''}
  defaultEnd={selectedJob?.end_date || ''}
  lineVisibility={lineVisibility}
  onToggleLine={toggleLineVisibility}
/>
```

删除 App.tsx 中以下局部常量（已迁入 panel）：
- `BuyMarker` 函数（约第 100-110 行）
- `SellMarker` 函数（约第 112-122 行）

`LineVisibility` interface（约第 151-157 行）和 `toggleLineVisibility` 函数（约第 612-617 行）保留在 App.tsx（仍由 App 持有状态）。

- [ ] **Step 3: 运行测试**

Run: `cd web && npm run test`

Expected: 9 个测试通过。

- [ ] **Step 4: 浏览器手动验证**

Run: `cd web && npm run dev`

提交一个回测，确认权益曲线 panel 视觉、交互、买卖点、缩放按钮、拖拽、`chartDateRange` 过滤都正常。

- [ ] **Step 5: 提交**

```bash
git add web/src/panels/EquityPanel.tsx web/src/App.tsx
git commit -m "refactor(panels): extract EquityPanel from App.tsx"
```

---

### Task 7: 抽取 StockIndicatorPanel

**Files:**
- Create: `web/src/panels/StockIndicatorPanel.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 创建 StockIndicatorPanel.tsx**

创建 `web/src/panels/StockIndicatorPanel.tsx`：

```tsx
import {
  Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';

export type IndicatorKey = 'macd' | 'kdj' | 'volume' | 'amount';

export interface IndicatorPoint {
  date: string;
  isUp: boolean;
  dif?: number | null;
  dea?: number | null;
  macd?: number | null;
  k?: number | null;
  d?: number | null;
  j?: number | null;
  value?: number | null;
}

export interface StockIndicatorPanelProps {
  data: IndicatorPoint[];
  selected: IndicatorKey;
  onChangeSelected: (next: IndicatorKey) => void;
  chartDateRange: DateRange | null;
}

export function StockIndicatorPanel(props: StockIndicatorPanelProps) {
  const filtered = filterByDateRange(props.data, props.chartDateRange);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>Backtest Stock Indicators</h3>
        <select
          value={props.selected}
          onChange={(e) => props.onChangeSelected(e.target.value as IndicatorKey)}
          style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #cbd5df', background: '#fff' }}
        >
          <option value="macd">MACD</option>
          <option value="kdj">KDJ</option>
          <option value="volume">Volume</option>
          <option value="amount">Amount (100M CNY)</option>
        </select>
      </div>

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip />
            {props.selected === 'macd' && (
              <>
                <Bar dataKey="macd" isAnimationActive={false} name="MACD">
                  {filtered.map((entry, i) => (
                    <Cell key={`m-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                  ))}
                </Bar>
                <Line type="monotone" dataKey="dif" stroke="#facc15" dot={false} strokeWidth={1.4} name="DIF" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="dea" stroke="#f97316" dot={false} strokeWidth={1.4} name="DEA" isAnimationActive={false} connectNulls={false} />
              </>
            )}
            {props.selected === 'kdj' && (
              <>
                <Line type="monotone" dataKey="k" stroke="#f3f4f6" dot={false} strokeWidth={1.4} name="K" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="d" stroke="#facc15" dot={false} strokeWidth={1.4} name="D" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="j" stroke="#a855f7" dot={false} strokeWidth={1.4} name="J" isAnimationActive={false} connectNulls={false} />
                <ReferenceLine y={80} stroke="#9ca3af" strokeDasharray="2 2" />
                <ReferenceLine y={20} stroke="#9ca3af" strokeDasharray="2 2" />
              </>
            )}
            {props.selected === 'volume' && (
              <Bar dataKey="value" isAnimationActive={false} name="Volume">
                {filtered.map((entry, i) => (
                  <Cell key={`v-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                ))}
              </Bar>
            )}
            {props.selected === 'amount' && (
              <Bar dataKey="value" isAnimationActive={false} name="Amount">
                {filtered.map((entry, i) => (
                  <Cell key={`a-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                ))}
              </Bar>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 修改 App.tsx 引入并使用 StockIndicatorPanel**

在 `web/src/App.tsx` 顶部 imports 添加：

```ts
import { StockIndicatorPanel } from './panels/StockIndicatorPanel';
import type { IndicatorKey } from './panels/StockIndicatorPanel';
```

删除 `App.tsx` 中 `type IndicatorKey` 局部声明（约第 211 行 `type IndicatorKey = 'macd' | 'kdj' | 'volume' | 'amount';`）。

将 `App.tsx` 中"Backtest Stock Indicators" panel（约第 1106-1165 行）整段替换为：

```tsx
<StockIndicatorPanel
  data={stockIndicatorData}
  selected={stockSelectedIndicator}
  onChangeSelected={setStockSelectedIndicator}
  chartDateRange={chartDateRange}
/>
```

- [ ] **Step 3: 运行测试**

Run: `cd web && npm run test`

Expected: 9 个测试通过。

- [ ] **Step 4: 浏览器手动验证**

确认 Backtest Stock Indicators panel 的 4 个指标（MACD/KDJ/Volume/Amount）切换正常；`chartDateRange` 过滤生效。

- [ ] **Step 5: 提交**

```bash
git add web/src/panels/StockIndicatorPanel.tsx web/src/App.tsx
git commit -m "refactor(panels): extract StockIndicatorPanel from App.tsx"
```

---

### Task 8: 抽取 IndexIndicatorPanel

**Files:**
- Create: `web/src/panels/IndexIndicatorPanel.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 创建 IndexIndicatorPanel.tsx**

创建 `web/src/panels/IndexIndicatorPanel.tsx`：

```tsx
import {
  Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';
import type { IndicatorKey, IndicatorPoint } from './StockIndicatorPanel';

export interface IndexIndicatorPanelProps {
  data: IndicatorPoint[];
  selected: IndicatorKey;
  onChangeSelected: (next: IndicatorKey) => void;
  chartDateRange: DateRange | null;
}

export function IndexIndicatorPanel(props: IndexIndicatorPanelProps) {
  const filtered = filterByDateRange(props.data, props.chartDateRange);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>Index Indicators</h3>
        <select
          value={props.selected}
          onChange={(e) => props.onChangeSelected(e.target.value as IndicatorKey)}
          style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #cbd5df', background: '#fff' }}
        >
          <option value="macd">MACD</option>
          <option value="kdj">KDJ</option>
          <option value="volume">Volume</option>
          <option value="amount">Amount (100M CNY)</option>
        </select>
      </div>

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip />
            {props.selected === 'macd' && (
              <>
                <Bar dataKey="macd" isAnimationActive={false} name="MACD">
                  {filtered.map((entry, i) => (
                    <Cell key={`m-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                  ))}
                </Bar>
                <Line type="monotone" dataKey="dif" stroke="#facc15" dot={false} strokeWidth={1.4} name="DIF" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="dea" stroke="#f97316" dot={false} strokeWidth={1.4} name="DEA" isAnimationActive={false} connectNulls={false} />
              </>
            )}
            {props.selected === 'kdj' && (
              <>
                <Line type="monotone" dataKey="k" stroke="#f3f4f6" dot={false} strokeWidth={1.4} name="K" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="d" stroke="#facc15" dot={false} strokeWidth={1.4} name="D" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="j" stroke="#a855f7" dot={false} strokeWidth={1.4} name="J" isAnimationActive={false} connectNulls={false} />
                <ReferenceLine y={80} stroke="#9ca3af" strokeDasharray="2 2" />
                <ReferenceLine y={20} stroke="#9ca3af" strokeDasharray="2 2" />
              </>
            )}
            {props.selected === 'volume' && (
              <Bar dataKey="value" isAnimationActive={false} name="Volume">
                {filtered.map((entry, i) => (
                  <Cell key={`v-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                ))}
              </Bar>
            )}
            {props.selected === 'amount' && (
              <Bar dataKey="value" isAnimationActive={false} name="Amount">
                {filtered.map((entry, i) => (
                  <Cell key={`a-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                ))}
              </Bar>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 修改 App.tsx**

在 `web/src/App.tsx` 顶部 imports 添加：

```ts
import { IndexIndicatorPanel } from './panels/IndexIndicatorPanel';
```

将 "Index Indicators" panel（约第 1241-1300 行）替换为：

```tsx
<IndexIndicatorPanel
  data={indexIndicatorData}
  selected={selectedIndicator}
  onChangeSelected={setSelectedIndicator}
  chartDateRange={chartDateRange}
/>
```

- [ ] **Step 3: 运行测试 + 浏览器手动验证 + 提交**

Run: `cd web && npm run test`

```bash
git add web/src/panels/IndexIndicatorPanel.tsx web/src/App.tsx
git commit -m "refactor(panels): extract IndexIndicatorPanel from App.tsx"
```

---

### Task 9: 抽取 StockKlinePanel (Phase 1 — 仍用 Recharts)

**Files:**
- Create: `web/src/panels/StockKlinePanel.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 创建 StockKlinePanel.tsx (Recharts 版)**

创建 `web/src/panels/StockKlinePanel.tsx`（Phase 1 用 Recharts，Phase 3 再切 LC）：

```tsx
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceDot,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Eye, EyeOff } from 'lucide-react';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';

export interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;
}

export interface PriceRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  boll_upper?: number | null;
  boll_mid?: number | null;
  boll_lower?: number | null;
  buy?: boolean;
  sell?: boolean;
}

export interface StockKlinePanelProps {
  data: PriceRow[];
  maVisibility: MaVisibility;
  onToggleMa: (key: keyof MaVisibility) => void;
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
}

function CandleShape(props: any) {
  const { x, y, width, height, payload } = props;
  const { open, high, low, close } = payload;
  if (open === undefined || close === 0) return null;
  const isUp = close >= open;
  const color = isUp ? '#ef4444' : '#22c55e';
  const cx = x + width / 2;
  const pxPerUnit = height / close;
  const highY = y + height - high * pxPerUnit;
  const lowY = y + height - low * pxPerUnit;
  const openY = y + height - open * pxPerUnit;
  const closeY = y + height - close * pxPerUnit;
  const bodyTop = Math.min(openY, closeY);
  const bodyBottom = Math.max(openY, closeY);
  return (
    <g>
      <line x1={cx} y1={highY} x2={cx} y2={lowY} stroke={color} strokeWidth={1} />
      <rect
        x={x + 1} y={bodyTop}
        width={width - 2}
        height={Math.max(1, bodyBottom - bodyTop)}
        fill={isUp ? color : 'transparent'}
        stroke={color} strokeWidth={1}
      />
    </g>
  );
}

function BuyMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [`${cx},${cy - size}`, `${cx - size},${cy + size}`, `${cx + size},${cy + size}`].join(' ');
  return <polygon points={points} fill="#22c55e" stroke="#15803d" strokeWidth={1} />;
}

function SellMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [`${cx},${cy + size}`, `${cx - size},${cy - size}`, `${cx + size},${cy - size}`].join(' ');
  return <polygon points={points} fill="#ef4444" stroke="#b91c1c" strokeWidth={1} />;
}

export function StockKlinePanel(props: StockKlinePanelProps) {
  const filtered = filterByDateRange(props.data, props.chartDateRange);
  const filteredMap = new Map(filtered.map(d => [d.date, d]));
  const buyPoints = filtered.filter(p => p.buy);
  const sellPoints = filtered.filter(p => p.sell);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>回测股票 K 线 + MA + BOLL</h3>
      </div>

      <div className="line-toggles">
        {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map(key => (
          <button
            key={key}
            className={`toggle-btn ${props.maVisibility[key] ? 'active' : ''}`}
            onClick={() => props.onToggleMa(key)}
          >
            {props.maVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
            {key === 'boll' ? 'BOLL' : key.toUpperCase()}
          </button>
        ))}
      </div>

      <ChartDateRangeControl
        value={props.chartDateRange}
        defaultStart={props.defaultStart}
        defaultEnd={props.defaultEnd}
        onChange={props.onChangeDateRange}
      />

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis domain={[0, 'auto']} />
            <Tooltip
              formatter={(value: any, name: string) => {
                if (typeof value === 'number') return [value.toFixed(2), name];
                return [value, name];
              }}
              labelFormatter={(label: string) => {
                const point = filteredMap.get(label);
                if (!point) return label;
                return `${label} | O:${point.open?.toFixed(2)} H:${point.high?.toFixed(2)} L:${point.low?.toFixed(2)} C:${point.close?.toFixed(2)}`;
              }}
            />
            <Legend />
            <Bar dataKey="close" shape={CandleShape} isAnimationActive={false} legendType="none" />
            {props.maVisibility.ma5 && <Line type="monotone" dataKey="ma5" stroke="#ef4444" dot={false} strokeWidth={1.5} name="MA5" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma10 && <Line type="monotone" dataKey="ma10" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="MA10" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma20 && <Line type="monotone" dataKey="ma20" stroke="#2563eb" dot={false} strokeWidth={1.5} name="MA20" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma60 && <Line type="monotone" dataKey="ma60" stroke="#7c3aed" dot={false} strokeWidth={1.5} name="MA60" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.boll && (
              <>
                <Line type="monotone" dataKey="boll_upper" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 上轨" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="boll_mid" stroke="#eab308" dot={false} strokeWidth={1.2} name="BOLL 中轨" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="boll_lower" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 下轨" isAnimationActive={false} connectNulls={false} />
              </>
            )}
            {buyPoints.map(point => (
              <ReferenceDot key={`buy-${point.date}`} x={point.date} y={point.low} shape={BuyMarker} ifOverflow="extendDomain" />
            ))}
            {sellPoints.map(point => (
              <ReferenceDot key={`sell-${point.date}`} x={point.date} y={point.high} shape={SellMarker} ifOverflow="extendDomain" />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 修改 App.tsx**

在 `web/src/App.tsx` 顶部 imports 添加：

```ts
import { StockKlinePanel } from './panels/StockKlinePanel';
import type { MaVisibility } from './panels/StockKlinePanel';
```

删除 `App.tsx` 中 `MaVisibility` interface 局部声明（约第 159-165 行）和 `toggleMaVisibility` 函数（约第 619-624 行）。

将 "回测股票 K 线 + MA + BOLL" panel（约第 965-1105 行）整段替换为：

```tsx
<StockKlinePanel
  data={priceDataWithMA}
  maVisibility={maVisibility}
  onToggleMa={toggleMaVisibility}
  chartDateRange={chartDateRange}
  onChangeDateRange={setChartDateRange}
  defaultStart={selectedJob?.start_date || ''}
  defaultEnd={selectedJob?.end_date || ''}
/>
```

- [ ] **Step 3: 运行测试 + 浏览器手动验证 + 提交**

```bash
git add web/src/panels/StockKlinePanel.tsx web/src/App.tsx
git commit -m "refactor(panels): extract StockKlinePanel from App.tsx (Recharts)"
```

---

### Task 10: 抽取 IndexKlinePanel (Phase 1 — 仍用 Recharts)

**Files:**
- Create: `web/src/panels/IndexKlinePanel.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 创建 IndexKlinePanel.tsx**

创建 `web/src/panels/IndexKlinePanel.tsx`（Recharts 版）：

```tsx
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Eye, EyeOff } from 'lucide-react';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';
import type { MaVisibility, PriceRow } from './StockKlinePanel';

export interface IndexKlinePanelProps {
  data: PriceRow[];
  maVisibility: MaVisibility;
  onToggleMa: (key: keyof MaVisibility) => void;
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
}

function CandleShape(props: any) {
  const { x, y, width, height, payload } = props;
  const { open, high, low, close } = payload;
  if (open === undefined || close === 0) return null;
  const isUp = close >= open;
  const color = isUp ? '#ef4444' : '#22c55e';
  const cx = x + width / 2;
  const pxPerUnit = height / close;
  const highY = y + height - high * pxPerUnit;
  const lowY = y + height - low * pxPerUnit;
  const openY = y + height - open * pxPerUnit;
  const closeY = y + height - close * pxPerUnit;
  const bodyTop = Math.min(openY, closeY);
  const bodyBottom = Math.max(openY, closeY);
  return (
    <g>
      <line x1={cx} y1={highY} x2={cx} y2={lowY} stroke={color} strokeWidth={1} />
      <rect
        x={x + 1} y={bodyTop}
        width={width - 2}
        height={Math.max(1, bodyBottom - bodyTop)}
        fill={isUp ? color : 'transparent'}
        stroke={color} strokeWidth={1}
      />
    </g>
  );
}

export function IndexKlinePanel(props: IndexKlinePanelProps) {
  const filtered = filterByDateRange(props.data, props.chartDateRange);
  const filteredMap = new Map(filtered.map(d => [d.date, d]));

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>上证指数 K 线 + MA + BOLL</h3>
      </div>

      <div className="line-toggles">
        {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map(key => (
          <button
            key={key}
            className={`toggle-btn ${props.maVisibility[key] ? 'active' : ''}`}
            onClick={() => props.onToggleMa(key)}
          >
            {props.maVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
            {key === 'boll' ? 'BOLL' : key.toUpperCase()}
          </button>
        ))}
      </div>

      <ChartDateRangeControl
        value={props.chartDateRange}
        defaultStart={props.defaultStart}
        defaultEnd={props.defaultEnd}
        onChange={props.onChangeDateRange}
      />

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip
              formatter={(value: any, name: string) => {
                if (value == null) return ['--', name];
                if (typeof value === 'number') return [value.toFixed(2), name];
                return [value, name];
              }}
              labelFormatter={(label: string) => {
                const point = filteredMap.get(label);
                if (!point) return label;
                return `${label} | O:${point.open.toFixed(2)} H:${point.high.toFixed(2)} L:${point.low.toFixed(2)} C:${point.close.toFixed(2)}`;
              }}
            />
            <Legend />
            <Bar dataKey="close" shape={CandleShape} isAnimationActive={false} legendType="none" />
            {props.maVisibility.ma5 && <Line type="monotone" dataKey="ma5" stroke="#ef4444" dot={false} strokeWidth={1.5} name="MA5" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma10 && <Line type="monotone" dataKey="ma10" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="MA10" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma20 && <Line type="monotone" dataKey="ma20" stroke="#2563eb" dot={false} strokeWidth={1.5} name="MA20" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma60 && <Line type="monotone" dataKey="ma60" stroke="#7c3aed" dot={false} strokeWidth={1.5} name="MA60" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.boll && (
              <>
                <Line type="monotone" dataKey="boll_upper" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 上轨" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="boll_mid" stroke="#eab308" dot={false} strokeWidth={1.2} name="BOLL 中轨" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="boll_lower" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 下轨" isAnimationActive={false} connectNulls={false} />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 修改 App.tsx**

在 `web/src/App.tsx` 顶部 imports 添加：

```ts
import { IndexKlinePanel } from './panels/IndexKlinePanel';
```

将 "上证指数 K 线 + MA + BOLL" panel（约第 1173-1239 行）整段替换为：

```tsx
<IndexKlinePanel
  data={indexDataWithMA}
  maVisibility={indexMaVisibility}
  onToggleMa={toggleIndexMa}
  chartDateRange={chartDateRange}
  onChangeDateRange={setChartDateRange}
  defaultStart={selectedJob?.start_date || ''}
  defaultEnd={selectedJob?.end_date || ''}
/>
```

- [ ] **Step 3: 运行测试 + 浏览器手动验证 + 提交**

```bash
git add web/src/panels/IndexKlinePanel.tsx web/src/App.tsx
git commit -m "refactor(panels): extract IndexKlinePanel from App.tsx (Recharts)"
```

---

### Task 11: Phase 1 验证

- [ ] **Step 1: 全量测试**

Run: `cd web && npm run test`

Expected: 9 个测试通过（2 已有 + 3 filterByDateRange + 4 buildSeries）。

- [ ] **Step 2: 全量构建**

Run: `cd web && npm run build`

Expected: TS 编译通过，无错误。

- [ ] **Step 3: 浏览器手动验证**

Run: `cd web && npm run dev`

提交一个回测，确认 5 个 panel 全部正常显示，行为与重构前完全一致：
- 权益曲线（含缩放/拖拽/线条切换/买卖点）
- 个股 K 线 + MA + BOLL（含 BOLL 切换）
- 个股副图（MACD/KDJ/Volume/Amount 切换）
- 上证指数 K 线 + MA + BOLL
- 指数副图

- [ ] **Step 4: 检查 App.tsx 行数**

Run: `wc -l web/src/App.tsx`

Expected: 大约 1100-1200 行（已从 1394 净减 ~200）。

---

## Phase 2：useKlineChart hook

### Task 12: 实现 useKlineChart (完整版)

**Files:**
- Create: `web/src/charts/useKlineChart.ts`

- [ ] **Step 1: 创建 useKlineChart.ts**

创建 `web/src/charts/useKlineChart.ts`：

```ts
import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';
import type { KlineRow, MaVisibility, TradeMarker } from './buildSeries';

export interface UseKlineChartOptions {
  container: HTMLDivElement | null;
  data: KlineRow[];
  maVisibility: MaVisibility;
  trades: TradeMarker[];
}

export interface HoverInfo {
  date: string;
  o: number;
  h: number;
  l: number;
  c: number;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
}

export interface UseKlineChartReturn {
  fitContent: () => void;
  setVisibleRange: (start: string, end: string) => void;
  hoverInfo: HoverInfo | null;
}

function toLineData(
  data: KlineRow[],
  key: 'ma5' | 'ma10' | 'ma20' | 'ma60' | 'boll_upper' | 'boll_mid' | 'boll_lower'
) {
  return data
    .map(d => ({ time: d.date, value: d[key] as number | null }))
    .filter((p): p is { time: string; value: number } => p.value !== null);
}

export function useKlineChart(options: UseKlineChartOptions): UseKlineChartReturn {
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<{
    candle: ISeriesApi<'Candlestick'>;
    ma5: ISeriesApi<'Line'>;
    ma10: ISeriesApi<'Line'>;
    ma20: ISeriesApi<'Line'>;
    ma60: ISeriesApi<'Line'>;
    bollUpper: ISeriesApi<'Line'>;
    bollMid: ISeriesApi<'Line'>;
    bollLower: ISeriesApi<'Line'>;
  } | null>(null);

  // 1. Create chart + all series on mount
  useEffect(() => {
    if (!options.container) return;
    const chart = createChart(options.container, {
      width: options.container.clientWidth,
      height: 400,
      layout: { background: { color: '#ffffff' }, textColor: '#1f2937' },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#d1d5db' },
      timeScale: { borderColor: '#d1d5db', timeVisible: false },
      localization: { locale: 'zh-CN', dateFormat: 'yyyy-MM-dd' },
    });
    chartRef.current = chart;

    const candle = chart.addCandlestickSeries({
      upColor: '#ef4444', downColor: '#22c55e',
      borderUpColor: '#ef4444', borderDownColor: '#22c55e',
      wickUpColor: '#ef4444', wickDownColor: '#22c55e',
    });
    const ma5 = chart.addLineSeries({ color: '#ef4444', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma10 = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma20 = chart.addLineSeries({ color: '#2563eb', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma60 = chart.addLineSeries({ color: '#7c3aed', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollUpper = chart.addLineSeries({ color: '#a855f7', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollMid = chart.addLineSeries({ color: '#eab308', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollLower = chart.addLineSeries({ color: '#a855f7', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });

    seriesRef.current = { candle, ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower };

    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: options.container!.clientWidth });
    });
    ro.observe(options.container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [options.container]);

  // 2. Sync K line + MA/BOLL data
  useEffect(() => {
    if (!seriesRef.current || !options.data.length) return;
    const { candle, ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower } = seriesRef.current;
    candle.setData(
      options.data.map(d => ({ time: d.date, open: d.open, high: d.high, low: d.low, close: d.close }))
    );
    ma5.setData(toLineData(options.data, 'ma5'));
    ma10.setData(toLineData(options.data, 'ma10'));
    ma20.setData(toLineData(options.data, 'ma20'));
    ma60.setData(toLineData(options.data, 'ma60'));
    bollUpper.setData(toLineData(options.data, 'boll_upper'));
    bollMid.setData(toLineData(options.data, 'boll_mid'));
    bollLower.setData(toLineData(options.data, 'boll_lower'));
  }, [options.data]);

  // 3. Sync visibility
  useEffect(() => {
    if (!seriesRef.current) return;
    const { ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower } = seriesRef.current;
    ma5.applyOptions({ visible: options.maVisibility.ma5 });
    ma10.applyOptions({ visible: options.maVisibility.ma10 });
    ma20.applyOptions({ visible: options.maVisibility.ma20 });
    ma60.applyOptions({ visible: options.maVisibility.ma60 });
    bollUpper.applyOptions({ visible: options.maVisibility.boll });
    bollMid.applyOptions({ visible: options.maVisibility.boll });
    bollLower.applyOptions({ visible: options.maVisibility.boll });
  }, [options.maVisibility]);

  // 4. Sync markers
  useEffect(() => {
    if (!seriesRef.current) return;
    const markers: SeriesMarker<Time>[] = options.trades.map(t => ({
      time: t.date,
      position: t.side === 'buy' ? 'belowBar' : 'aboveBar',
      color: t.side === 'buy' ? '#22c55e' : '#ef4444',
      shape: t.side === 'buy' ? 'arrowUp' : 'arrowDown',
      text: t.side === 'buy' ? 'B' : 'S',
    }));
    seriesRef.current.candle.setMarkers(markers);
  }, [options.trades]);

  // 5. Hover info via crosshair
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);
  useEffect(() => {
    if (!chartRef.current) return;
    const handler = (param: MouseEventParams) => {
      if (!param.time || !seriesRef.current) {
        setHoverInfo(null);
        return;
      }
      const date = param.time as string;
      const row = options.data.find(d => d.date === date);
      if (!row) { setHoverInfo(null); return; }
      setHoverInfo({
        date, o: row.open, h: row.high, l: row.low, c: row.close,
        ma5: row.ma5 ?? null, ma10: row.ma10 ?? null,
        ma20: row.ma20 ?? null, ma60: row.ma60 ?? null,
      });
    };
    chartRef.current.subscribeCrosshairMove(handler);
    return () => chartRef.current?.unsubscribeCrosshairMove(handler);
  }, [options.data]);

  // 6. Imperative API
  const fitContent = () => chartRef.current?.timeScale().fitContent();
  const setVisibleRange = (start: string, end: string) => {
    const idx0 = options.data.findIndex(d => d.date >= start);
    const idx1 = options.data.findIndex(d => d.date > end);
    if (idx0 === -1 || idx1 === -1) return;
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: idx0, to: idx1 });
  };

  return { fitContent, setVisibleRange, hoverInfo };
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd web && npm run build`

Expected: 编译通过，无 TS 错误（`lightweight-charts` 类型正确导出）。

- [ ] **Step 3: 提交**

```bash
git add web/src/charts/useKlineChart.ts
git commit -m "feat(charts): implement useKlineChart hook with LC integration"
```

---

### Task 13: useKlineChart 单元测试

**Files:**
- Create: `web/src/charts/useKlineChart.test.tsx`

- [ ] **Step 1: 创建测试**

创建 `web/src/charts/useKlineChart.test.tsx`：

```tsx
import { render, screen } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it } from 'vitest';
import { useKlineChart } from './useKlineChart';
import { buildKlineSeries } from './buildSeries';

const sampleCandles = [
  { date: '20240101', open: 10, high: 11, low: 9.5, close: 10.5, volume: 1000 },
  { date: '20240102', open: 10.5, high: 11.2, low: 10.3, close: 11, volume: 1200 },
  { date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900 },
];

const sampleData = buildKlineSeries(sampleCandles);
const maVisibility = { ma5: true, ma10: true, ma20: true, ma60: true, boll: true };

function Harness({ data, trades = [] }: { data: typeof sampleData; trades?: { date: string; side: 'buy' | 'sell' }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useKlineChart({ container: ref.current, data, maVisibility, trades });
  return <div ref={ref} data-testid="kline-host" style={{ width: 800, height: 400 }} />;
}

describe('useKlineChart', () => {
  it('mounts a canvas inside the container', () => {
    return new Promise<void>((resolve) => {
      render(<Harness data={sampleData} />);
      setTimeout(() => {
        const host = screen.getByTestId('kline-host');
        expect(host.querySelector('canvas')).toBeTruthy();
        resolve();
      }, 50);
    });
  });

  it('handles empty trades without errors', () => {
    expect(() => render(<Harness data={sampleData} trades={[]} />)).not.toThrow();
  });
});
```

- [ ] **Step 2: 运行测试**

Run: `cd web && npm run test -- useKlineChart`

Expected: 2 个测试 PASS。

- [ ] **Step 3: 运行全量测试确认无回归**

Run: `cd web && npm run test`

Expected: 11 个测试通过（9 已有 + 2 新增）。

- [ ] **Step 4: 提交**

```bash
git add web/src/charts/useKlineChart.test.tsx
git commit -m "test(charts): add useKlineChart hook test"
```

---

## Phase 3：替换 K 线 panel 为 LC

### Task 14: StockKlinePanel 切到 useKlineChart

**Files:**
- Modify: `web/src/panels/StockKlinePanel.tsx`

- [ ] **Step 1: 重写 StockKlinePanel.tsx**

将整个 `web/src/panels/StockKlinePanel.tsx` 替换为：

```tsx
import { useMemo, useRef } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { buildKlineSeries, buildTradeMarkers, type KlineRow, type TradeMarker } from '../charts/buildSeries';
import { useKlineChart } from '../charts/useKlineChart';

export interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;
}

export interface PriceRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  pnl?: number;
  pnlcomm?: number;
  barlen?: number;
  size?: number;
}

export interface StockKlinePanelProps {
  data: PriceRow[];
  trades?: { date: string; pnl: number; pnlcomm: number; barlen: number; size: number }[];
  maVisibility: MaVisibility;
  onToggleMa: (key: keyof MaVisibility) => void;
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
}

function fmt(v: number | null) {
  return v == null ? '--' : v.toFixed(2);
}

export function StockKlinePanel(props: StockKlinePanelProps) {
  const ref = useRef<HTMLDivElement>(null);

  // Build kline series data (MA/BOLL appended)
  const klineData: KlineRow[] = useMemo(() => buildKlineSeries(props.data), [props.data]);

  // Build trade markers (preserve even/odd semantics)
  const markers: TradeMarker[] = useMemo(
    () => buildTradeMarkers(
      (props.trades ?? []).map(t => ({
        date: t.date, pnl: t.pnl ?? 0, pnlcomm: t.pnlcomm ?? 0, barlen: t.barlen ?? 0, size: t.size ?? 0,
      }))
    ),
    [props.trades]
  );

  const { hoverInfo } = useKlineChart({
    container: ref.current,
    data: klineData,
    maVisibility: props.maVisibility,
    trades: markers,
  });

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>回测股票 K 线 + MA + BOLL</h3>
      </div>

      <div className="line-toggles">
        {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map(key => (
          <button
            key={key}
            className={`toggle-btn ${props.maVisibility[key] ? 'active' : ''}`}
            onClick={() => props.onToggleMa(key)}
          >
            {props.maVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
            {key === 'boll' ? 'BOLL' : key.toUpperCase()}
          </button>
        ))}
      </div>

      <ChartDateRangeControl
        value={props.chartDateRange}
        defaultStart={props.defaultStart}
        defaultEnd={props.defaultEnd}
        onChange={props.onChangeDateRange}
      />

      <div ref={ref} className="chart-container" style={{ height: 400, position: 'relative' }} data-testid="kline-container">
        {hoverInfo && (
          <div
            className="kline-tooltip"
            style={{
              position: 'absolute', top: 8, left: 8, zIndex: 10,
              background: 'rgba(31,41,55,0.9)', color: '#fff', padding: '6px 10px',
              borderRadius: 4, fontSize: 12, lineHeight: 1.5, pointerEvents: 'none',
            }}
            data-testid="kline-tooltip"
          >
            <div>{hoverInfo.date}</div>
            <div>O {fmt(hoverInfo.o)} H {fmt(hoverInfo.h)} L {fmt(hoverInfo.l)} C {fmt(hoverInfo.c)}</div>
            <div>MA5 {fmt(hoverInfo.ma5)} MA10 {fmt(hoverInfo.ma10)} MA20 {fmt(hoverInfo.ma20)} MA60 {fmt(hoverInfo.ma60)}</div>
          </div>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 浏览器手动验证**

Run: `cd web && npm run dev`

提交一个回测，确认：
- 个股 K 线使用 LC 渲染（缩放、拖拽、十字光标）
- 买卖点 marker 显示
- 鼠标 hover 时 tooltip 显示 OHLC + MA5/10/20/60
- MA/BOLL 切换按钮控制 series 显隐
- `chartDateRange` 输入框不影响 K 线（仅影响副图与权益曲线）

- [ ] **Step 3: 更新 App.tsx 的 StockKlinePanel 调用**

将 App.tsx 中 StockKlinePanel 调用（约 Task 9 引入处）从：

```tsx
<StockKlinePanel
  data={priceDataWithMA}
  ...
/>
```

改为：

```tsx
<StockKlinePanel
  data={result.price_data}
  trades={result.trades}
  ...
/>
```

`priceDataWithMA` 仍被副图（`stockIndicatorData`）使用，不删除。

- [ ] **Step 4: 提交**

```bash
git add web/src/panels/StockKlinePanel.tsx
git commit -m "refactor(StockKlinePanel): migrate to lightweight-charts"
```

---

### Task 15: IndexKlinePanel 切到 useKlineChart

**Files:**
- Modify: `web/src/panels/IndexKlinePanel.tsx`

- [ ] **Step 1: 重写 IndexKlinePanel.tsx**

将整个 `web/src/panels/IndexKlinePanel.tsx` 替换为：

```tsx
import { useMemo, useRef } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { buildKlineSeries, type KlineRow } from '../charts/buildSeries';
import { useKlineChart } from '../charts/useKlineChart';
import { type DateRange } from '../charts/filterByDateRange';
import type { MaVisibility, PriceRow } from './StockKlinePanel';

export interface IndexKlinePanelProps {
  data: PriceRow[];
  maVisibility: MaVisibility;
  onToggleMa: (key: keyof MaVisibility) => void;
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
}

function fmt(v: number | null) {
  return v == null ? '--' : v.toFixed(2);
}

export function IndexKlinePanel(props: IndexKlinePanelProps) {
  const ref = useRef<HTMLDivElement>(null);
  const klineData: KlineRow[] = useMemo(() => buildKlineSeries(props.data), [props.data]);

  const { hoverInfo } = useKlineChart({
    container: ref.current,
    data: klineData,
    maVisibility: props.maVisibility,
    trades: [],
  });

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>上证指数 K 线 + MA + BOLL</h3>
      </div>

      <div className="line-toggles">
        {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map(key => (
          <button
            key={key}
            className={`toggle-btn ${props.maVisibility[key] ? 'active' : ''}`}
            onClick={() => props.onToggleMa(key)}
          >
            {props.maVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
            {key === 'boll' ? 'BOLL' : key.toUpperCase()}
          </button>
        ))}
      </div>

      <ChartDateRangeControl
        value={props.chartDateRange}
        defaultStart={props.defaultStart}
        defaultEnd={props.defaultEnd}
        onChange={props.onChangeDateRange}
      />

      <div ref={ref} className="chart-container" style={{ height: 400, position: 'relative' }} data-testid="index-kline-container">
        {hoverInfo && (
          <div
            className="kline-tooltip"
            style={{
              position: 'absolute', top: 8, left: 8, zIndex: 10,
              background: 'rgba(31,41,55,0.9)', color: '#fff', padding: '6px 10px',
              borderRadius: 4, fontSize: 12, lineHeight: 1.5, pointerEvents: 'none',
            }}
            data-testid="index-kline-tooltip"
          >
            <div>{hoverInfo.date}</div>
            <div>O {fmt(hoverInfo.o)} H {fmt(hoverInfo.h)} L {fmt(hoverInfo.l)} C {fmt(hoverInfo.c)}</div>
            <div>MA5 {fmt(hoverInfo.ma5)} MA10 {fmt(hoverInfo.ma10)} MA20 {fmt(hoverInfo.ma20)} MA60 {fmt(hoverInfo.ma60)}</div>
          </div>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 更新 App.tsx 的 IndexKlinePanel 调用**

将 App.tsx 中 IndexKlinePanel 调用从：

```tsx
<IndexKlinePanel
  data={indexDataWithMA}
  ...
/>
```

改为：

```tsx
<IndexKlinePanel
  data={result.index_data}
  ...
/>
```

- [ ] **Step 3: 浏览器手动验证 + 提交**

```bash
git add web/src/panels/IndexKlinePanel.tsx web/src/App.tsx
git commit -m "refactor(IndexKlinePanel): migrate to lightweight-charts"
```

---

### Task 16: StockKlinePanel 集成测试

**Files:**
- Create: `web/src/panels/StockKlinePanel.test.tsx`

- [ ] **Step 1: 创建集成测试**

创建 `web/src/panels/StockKlinePanel.test.tsx`：

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StockKlinePanel } from './StockKlinePanel';
import { buildTradeMarkers } from '../charts/buildSeries';

const sampleCandles = [
  { date: '20240101', open: 10, high: 11, low: 9.5, close: 10.5, volume: 1000 },
  { date: '20240102', open: 10.5, high: 11.2, low: 10.3, close: 11, volume: 1200 },
  { date: '20240103', open: 11, high: 11.5, low: 10.8, close: 10.9, volume: 900 },
  { date: '20240104', open: 10.9, high: 11, low: 10.5, close: 10.7, volume: 800 },
  { date: '20240105', open: 10.7, high: 10.9, low: 10.4, close: 10.6, volume: 700 },
];

const sampleTrades = [
  { date: '20240102', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
  { date: '20240105', pnl: 0, pnlcomm: 0, barlen: 0, size: 0 },
];

const defaultMaVisibility = { ma5: true, ma10: true, ma20: true, ma60: true, boll: true };

describe('StockKlinePanel', () => {
  it('mounts a kline container (lightweight-charts renders canvas)', () => {
    return new Promise<void>((resolve) => {
      render(
        <StockKlinePanel
          data={sampleCandles}
          trades={sampleTrades}
          maVisibility={defaultMaVisibility}
          onToggleMa={() => {}}
          chartDateRange={null}
          onChangeDateRange={() => {}}
          defaultStart="20240101"
          defaultEnd="20240105"
        />
      );
      setTimeout(() => {
        const container = screen.getByTestId('kline-container');
        expect(container.querySelector('canvas')).toBeTruthy();
        resolve();
      }, 50);
    });
  });

  it('renders MA/BOLL toggle buttons', () => {
    render(
      <StockKlinePanel
        data={sampleCandles}
        maVisibility={defaultMaVisibility}
        onToggleMa={() => {}}
        chartDateRange={null}
        onChangeDateRange={() => {}}
        defaultStart="20240101"
        defaultEnd="20240105"
      />
    );
    expect(screen.getByRole('button', { name: /MA5/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /BOLL/i })).toBeTruthy();
  });

  it('buildTradeMarkers still alternates buy/sell (preserves semantics)', () => {
    expect(buildTradeMarkers(sampleTrades)).toEqual([
      { date: '20240102', side: 'buy' },
      { date: '20240105', side: 'sell' },
    ]);
  });
});
```

- [ ] **Step 2: 运行测试**

Run: `cd web && npm run test -- StockKlinePanel`

Expected: 3 个测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add web/src/panels/StockKlinePanel.test.tsx
git commit -m "test(panels): add StockKlinePanel integration test"
```

---

### Task 17: IndexKlinePanel 集成测试

**Files:**
- Create: `web/src/panels/IndexKlinePanel.test.tsx`

- [ ] **Step 1: 创建测试**

创建 `web/src/panels/IndexKlinePanel.test.tsx`：

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { IndexKlinePanel } from './IndexKlinePanel';

const sampleCandles = [
  { date: '20240101', open: 3000, high: 3050, low: 2980, close: 3020, volume: 1e9 },
  { date: '20240102', open: 3020, high: 3080, low: 3010, close: 3060, volume: 1.1e9 },
  { date: '20240103', open: 3060, high: 3100, low: 3050, close: 3080, volume: 1.2e9 },
];

const defaultMaVisibility = { ma5: true, ma10: true, ma20: true, ma60: true, boll: true };

describe('IndexKlinePanel', () => {
  it('mounts a kline container for index chart', () => {
    return new Promise<void>((resolve) => {
      render(
        <IndexKlinePanel
          data={sampleCandles}
          maVisibility={defaultMaVisibility}
          onToggleMa={() => {}}
          chartDateRange={null}
          onChangeDateRange={() => {}}
          defaultStart="20240101"
          defaultEnd="20240103"
        />
      );
      setTimeout(() => {
        const container = screen.getByTestId('index-kline-container');
        expect(container.querySelector('canvas')).toBeTruthy();
        resolve();
      }, 50);
    });
  });

  it('renders MA/BOLL toggle buttons', () => {
    render(
      <IndexKlinePanel
        data={sampleCandles}
        maVisibility={defaultMaVisibility}
        onToggleMa={() => {}}
        chartDateRange={null}
        onChangeDateRange={() => {}}
        defaultStart="20240101"
        defaultEnd="20240103"
      />
    );
    expect(screen.getByRole('button', { name: /MA20/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /BOLL/i })).toBeTruthy();
  });
});
```

- [ ] **Step 2: 运行测试 + 提交**

```bash
git add web/src/panels/IndexKlinePanel.test.tsx
git commit -m "test(panels): add IndexKlinePanel integration test"
```

---

### Task 18: App.tsx 清理 K 线相关遗留

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 删除局部 CandleShape 与 kline points**

从 `web/src/App.tsx` 删除：
- `klineBuyPoints` useMemo（约第 542 行）
- `klineSellPoints` useMemo（约第 543 行）

（注：`CandleShape`/`BuyMarker`/`SellMarker` 在 Task 6/9/10 已迁入 panel，此处仅删除 panel 内的引用变量）

- [ ] **Step 2: 确认 CandleShape 不再被 App.tsx 引用**

Run: `cd web && grep -n "CandleShape" src/App.tsx`

Expected: 无输出。

- [ ] **Step 3: 运行全量测试 + 浏览器验证**

```bash
cd web && npm run test
```

提交一个回测，确认 5 个 panel 全部正常，无 JS 报错。

- [ ] **Step 4: 提交**

```bash
git add web/src/App.tsx
git commit -m "refactor(App): remove kline points leftover after panel extraction"
```

---

### Task 19: Phase 3 验证

- [ ] **Step 1: 全量测试**

Run: `cd web && npm run test`

Expected: 16 个测试通过（2 + 3 + 4 + 2 + 3 + 2 = 16）。

- [ ] **Step 2: 全量构建**

Run: `cd web && npm run build`

Expected: TS 编译通过。

- [ ] **Step 3: 检查 K 线 panel 浏览器效果**

Run: `cd web && npm run dev`

逐项验证：
- 个股 K 线：滚轮缩放流畅、拖拽平移流畅、十字光标跟手
- 个股 K 线：买卖点 ▲▼ 显示
- 个股 K 线：hover 时 HTML tooltip 显示日期 + OHLC + MA5/10/20/60
- 个股 K 线：MA5/10/20/60、BOLL 切换按钮即时显隐
- 个股 K 线：`chartDateRange` 输入框**不影响 K 线**
- 上证指数 K 线：以上各项均成立
- 副图：仍响应 `chartDateRange`
- 权益曲线：缩放按钮 + 拖拽工作

- [ ] **Step 4: 检查 App.tsx 行数**

Run: `wc -l web/src/App.tsx`

Expected: 约 1100-1150 行。

---

## Phase 4：清理与文档

### Task 20: 替换 priceDataWithMA / indexDataWithMA 为 buildKlineSeries

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 引入 buildKlineSeries**

在 `web/src/App.tsx` 顶部 imports 添加：

```ts
import { buildKlineSeries } from './charts/buildSeries';
```

- [ ] **Step 2: 替换 priceDataWithMA**

将 `web/src/App.tsx` 中 `priceDataWithMA` useMemo（约第 372-398 行）替换为：

```ts
const priceDataWithMA = useMemo(
  () => buildKlineSeries(result?.price_data ?? []),
  [result]
);
```

- [ ] **Step 3: 替换 indexDataWithMA**

将 `web/src/App.tsx` 中 `indexDataWithMA` useMemo（约第 461-479 行）替换为：

```ts
const indexDataWithMA = useMemo(
  () => buildKlineSeries(result?.index_data ?? []),
  [result]
);
```

- [ ] **Step 4: 运行测试 + 浏览器验证 + 提交**

```bash
cd web && npm run test
```

```bash
git add web/src/App.tsx
git commit -m "refactor(App): delegate priceDataWithMA / indexDataWithMA to buildKlineSeries"
```

---

### Task 21: 清理未使用的 imports

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 查找未使用的 imports**

检查 `web/src/App.tsx` 顶部的 Recharts imports。Task 6-10 已将 K 线 panel 切到 LC，App.tsx 不再直接使用 `ComposedChart` / `Bar` / `ReferenceDot`（这些仅在 panel 内部用）。

从 imports 中删除：
- `Bar`（如未在其他 panel JSX 中使用）
- `ComposedChart`（如未使用）
- `ReferenceDot`（如未使用）

保留：`LineChart`, `Line`, `CartesianGrid`, `XAxis`, `YAxis`, `Legend`, `Tooltip`, `ResponsiveContainer`（仍用于 EquityPanel 和副图）。

- [ ] **Step 2: 运行测试 + 构建**

```bash
cd web && npm run test
cd web && npm run build
```

Expected: 全部通过。

- [ ] **Step 3: 提交**

```bash
git add web/src/App.tsx
git commit -m "chore(App): remove unused Recharts imports after panel extraction"
```

---

### Task 22: 创建 web/src/charts/README.md

**Files:**
- Create: `web/src/charts/README.md`

- [ ] **Step 1: 创建 README**

创建 `web/src/charts/README.md`：

````markdown
# web/src/charts/

K 线图与配套数据工具模块。

## 工具函数

### `filterByDateRange(rows, range)`
统一日期范围过滤，替代 `App.tsx` 中 5 处 `filteredXxx` 重复 useMemo。

### `buildKlineSeries(candles)`
在 OHLC 蜡烛数据上追加 MA5/10/20/60 + BOLL(20, 2) 指标列，返回 `KlineRow[]`。

### `buildTradeMarkers(trades)`
按偶/奇索引把 `trades` 转成 LC marker `{ date, side: 'buy' | 'sell' }[]`，保留 `App.tsx` 中 `buildTradeMarkerMap` 的旧语义。

## Hook：`useKlineChart`

封装 TradingView Lightweight Charts v4.2 的生命周期。

### 入参
```ts
{
  container: HTMLDivElement | null;
  data: KlineRow[];
  maVisibility: { ma5: boolean; ma10: boolean; ma20: boolean; ma60: boolean; boll: boolean };
  trades: TradeMarker[];
}
```

### 返回
```ts
{
  fitContent: () => void;
  setVisibleRange: (start: string, end: string) => void;
  hoverInfo: { date, o, h, l, c, ma5, ma10, ma20, ma60 } | null;
}
```

### 颜色规范（A 股惯例）
| 元素 | Hex |
|---|---|
| 涨 | `#ef4444` |
| 跌 | `#22c55e` |
| MA5 | `#ef4444` |
| MA10 | `#f59e0b` |
| MA20 | `#2563eb` |
| MA60 | `#7c3aed` |
| BOLL 上下轨 | `#a855f7` |
| BOLL 中轨 | `#eab308` |

## 推迟到未来
- K线 ↔ 副图 crosshair / timeScale 同步：需将副图也迁到 LC（架构上 LC + Recharts 不可桥接）
- K线 响应 `chartDateRange` 输入：可调用 `setVisibleRange`，但与 LC 内建平移冲突
````

- [ ] **Step 2: 提交**

```bash
git add web/src/charts/README.md
git commit -m "docs(charts): add README for charts module"
```

---

### Task 23: 更新项目根 CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 添加 K 线重构说明**

在 `CLAUDE.md` 中"Web 分析台"小节（约第 60-70 行）末尾添加：

```markdown
- K 线由 `lightweight-charts` v4 渲染（`web/src/charts/useKlineChart.ts`）；副图与权益曲线仍用 Recharts。详见 `docs/kline-chart-refactor.md`。
```

- [ ] **Step 2: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: add kline chart refactor pointer to CLAUDE.md"
```

---

### Task 24: 最终验证

- [ ] **Step 1: 全量测试**

Run: `cd web && npm run test`

Expected: 16 个测试通过。

- [ ] **Step 2: 全量构建**

Run: `cd web && npm run build`

Expected: TS 编译通过。

- [ ] **Step 3: CandleShape 不再存在**

Run: `cd web && grep -rn "CandleShape" src/`

Expected: 无输出。

- [ ] **Step 4: klineBuyPoints / klineSellPoints 不再存在**

Run: `cd web && grep -rn "klineBuyPoints\|klineSellPoints" src/`

Expected: 无输出。

- [ ] **Step 5: App.tsx 行数**

Run: `cd web && wc -l src/App.tsx`

Expected: 约 1100-1150 行（从 1394 净减 ~250）。

- [ ] **Step 6: 浏览器最终冒烟测试**

Run: `cd web && npm run dev`

完整回测流程：提交 → 等待完成 → 验证 5 个 panel 全部正常 + K线交互流畅 + tooltip 显示。

---

## 完成标准

全部 24 个任务完成后：
- 16 个测试通过（2 已有 + 3 + 4 + 2 + 3 + 2）
- `App.tsx` 净减 ~250 行
- 个股 K 线 + 上证指数 K 线改用 Lightweight Charts
- 副图、权益曲线不变
- 工具函数与 panel 组件已抽取，集成测试覆盖
- 文档完整

可发起 PR：`feat(web): migrate kline chart to lightweight-charts`
