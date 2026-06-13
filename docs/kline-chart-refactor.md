# K 线图重构方案 — TradingView Lightweight Charts

> 范围：将 `web/src/App.tsx` 中由 Recharts 拼凑的两处 K 线图（个股回测 K 线、上证指数 K 线）替换为 TradingView Lightweight Charts，解决显示细腻度、缩放/平移流畅度、十字光标、买卖点对齐的痛点。**仅触及 K 线相关代码**（Surgical Changes）。
>
> **已确认决策**（来自头脑风暴）：
> - K线 ↔ 副图 双向同步 → **推迟到未来**（架构上 LC + Recharts 不可桥接；完整方案需把副图也迁 LC）
> - 买卖点 marker → LC 内建 `setMarkers` + `arrowUp/Down`
> - K线首次加载 → `fitContent()` 全量显示
> - Tooltip → 自定义 HTML overlay：OHLC + MA5/10/20/60
> - 测试 → 含集成测试（需阶段 1.4 抽取 panel）
> - 回退策略 → 不设回退（只进不退）

---

## 一、背景与目标

### 1.1 现状

`quantx` 是基于 Backtrader 的低频波段策略系统，Web 端用 React + Recharts 展示回测结果。`App.tsx` 渲染 4 个图表 panel：

| Panel | 类型 | 实现 |
|---|---|---|
| 权益曲线 + 市场评分 | 多折线 | Recharts `LineChart` |
| 个股 K 线 + MA + BOLL | 蜡烛 + 折线 | Recharts `ComposedChart` + 自定义 `CandleShape` |
| 个股副图（MACD/KDJ/Vol/Amount） | 柱 + 折线 | Recharts `ComposedChart` |
| 上证指数 K 线 + MA + BOLL | 蜡烛 + 折线 | Recharts `ComposedChart` + `CandleShape` |
| 指数副图 | 柱 + 折线 | Recharts `ComposedChart` |

### 1.2 核心痛点

经过 `web/src/App.tsx:64-138, 553-572` 的代码审计，K 线相关问题清单：

1. **`CandleShape` 是手算像素的 hack**（`App.tsx:64-99`）
   - 通过 `pxPerUnit = height / close` 推算高低开收对应的 y 坐标
   - 一旦 y 轴自动缩放或加副图，y 坐标变化导致蜡烛错位
   - 维护成本高，且与 Recharts 内部坐标系强耦合

2. **拖拽缩放仅作用于权益曲线**（`App.tsx:553-572`）
   - `onMouseDown` / `onMouseMove` / `onMouseUp` 手撸实现
   - `800px` 硬编码估算宽度（`App.tsx:562`）
   - K 线无法使用此功能

3. **5 处重复的 `chartDateRange` 过滤**
   - `filteredData` / `filteredPriceData` / `filteredStockIndicatorData` / `filteredIndexData` / `filteredIndicatorData`
   - 同一份过滤逻辑散落在 `App.tsx:344-538`

4. **MA / BOLL 计算在两处重复**
   - `priceDataWithMA`（`App.tsx:372-398`）
   - `indexDataWithMA`（`App.tsx:461-479`）
   - 计算完全相同的 MA5/10/20/60 + BOLL(20, 2)

5. **副图指标数据逻辑 90% 重复**
   - `stockIndicatorData`（`App.tsx:412-449`）
   - `indexIndicatorData`（`App.tsx:490-528`）

6. **买卖点 marker 脆弱**（`App.tsx:542-543, 1073-1090`）
   - 用 `ReferenceDot` + 三角 `polygon` shape
   - 即使在 289960e commit 修复了一类对齐问题，仍依赖 Recharts 的坐标推断

7. **`App.tsx` 1394 行**，混合图表渲染 / 数据派生 / 任务轮询 / 表单状态，可读性差。

### 1.3 目标

| 目标 | 度量 |
|---|---|
| K 线显示细腻、专业 | 缩略图与 TradingView 同款视觉 |
| 流畅缩放 / 平移 | 鼠标滚轮缩放、拖拽平移、十字光标跟手 |
| 买卖点精确对齐 K 线 | 三角形 marker 与蜡烛实体边缘贴合 |
| 保持现有功能不回归 | 副图、MA 切换、BOLL 切换、日期范围筛选、缩放按钮 |
| 代码净减 | `App.tsx` 净减 100+ 行 |
| 测试持续通过 | 现有 2 个 vitest 测试 + 新增 hook 测试 |

---

## 二、选型

### 2.1 候选方案对比

| 方案 | 体积 | 性能 | 蜡烛原生 | 缩放/平移 | 中文文档 | 维护活跃度 | License |
|---|---|---|---|---|---|---|---|
| **TradingView Lightweight Charts** | ~45KB gzip | ⭐⭐⭐⭐⭐ Canvas | ✅ | ✅ 内建 | ⚠️ 英文 | ⭐⭐⭐⭐⭐ | Apache 2.0 |
| KLineChart | ~50KB gzip | ⭐⭐⭐⭐⭐ Canvas | ✅ | ✅ 内建 | ✅ 完善 | ⭐⭐⭐⭐ | Apache 2.0 |
| ECharts candlestick | ~330KB | ⭐⭐⭐⭐ | ✅ | `dataZoom` | ✅ 完善 | ⭐⭐⭐⭐⭐ | Apache 2.0 |
| react-stockcharts | 较大 | ⭐⭐⭐ D3 | ✅ | ✅ | ⚠️ 英文 | ⭐⭐⭐ | MIT |

### 2.2 决策：TradingView Lightweight Charts

**理由**：

1. **专业度**：同款 TradingView 渲染引擎，业内视觉标杆
2. **体积最小**：~45KB，比现有 Recharts 还小
3. **零交互代码**：缩放、平移、十字光标、自适应开箱即用
4. **API 稳定**：Apache 2.0，TradingView 官方维护
5. **React 集成简单**：参考官方教程 ~30 行代码即可嵌入
6. **中文社区可触达**：虽然是英文文档，但 API 简洁，附 KLineChart 国产备选

**KLineChart 作为备选**：若团队更倾向中文文档 + 内置 TA 指标（MA/MACD/KDJ/BOLL），可平滑切换。两者 API 风格不同，迁移成本中等。

### 2.3 范围外决策

**不引入 Lightweight Charts 替代以下场景**（CLAUDE.md "Surgical Changes"）：

- ❌ 权益曲线（多折线）—— 继续用 Recharts
- ❌ MACD / KDJ / Volume / Amount 副图 —— 继续用 Recharts
- ❌ 不重写权益曲线的拖拽缩放 —— 当前可工作，ROI 低
- ❌ 不实现 K线 ↔ 副图 crosshair / timeScale 双向同步（LC 与 Recharts 无跨实例协议；详见 §2.4）

### 2.4 推迟到未来迭代的能力

经头脑风暴确认，下列能力**架构上可行但本期不实现**，留待后续 spec：

- **K线 ↔ 副图 crosshair / timeScale 同步**：完整路径是把副图也迁到 LC（用 `addHistogramSeries` + 独立 `priceScaleId`），与 K 线共一个 chart 实例。Recharts 副图无 `subscribeCrosshairMove` 公共 API，无法做 LC → Recharts 跨实例同步。
- **K线响应 `chartDateRange` 输入框**：可调用 hook 暴露的 `setVisibleRange()`，但与 LC 内建平移/缩放冲突，本期不接。
- **K线 工具栏（时间周期切换 / 指标添加）**：本项目数据固定日线，无此需求。

---

## 三、架构设计

### 3.1 模块划分

新增目录 `web/src/charts/`，职责单一：

```
web/src/charts/
├── filterByDateRange.ts    # 统一日期过滤（替代 5 处重复）
├── buildSeries.ts          # 计算 MA / BOLL 序列（含 trades 合并）
├── useKlineChart.ts        # LC 实例生命周期 hook
├── useKlineChart.test.tsx  # hook 单元测试
└── README.md               # 简述 hook 用法
```

### 3.2 数据流

```
result.price_data / result.index_data
        │
        ▼
   buildSeries(data, trades)        # 计算 MA/BOLL + 合并买卖点
        │
        ▼
   useKlineChart({                  # 渲染到 canvas
     data, maVisibility, trades
   })
        │
        ▼
   <div ref={klineRef} />           # DOM 容器
```

副图（MACD/KDJ/Volume/Amount）数据流不变：

```
priceDataWithMA
        │
        ▼
   stockIndicatorData (memo)
        │
        ▼
   Recharts ComposedChart
```

### 3.3 hook API 设计

```ts
// useKlineChart.ts
interface KlineRow {
  date: string;           // 'YYYYMMDD'
  open: number;
  high: number;
  low: number;
  close: number;
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  boll_upper?: number | null;
  boll_mid?: number | null;
  boll_lower?: number | null;
}

interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;
}

interface TradeMarker {
  date: string;           // 'YYYYMMDD'
  side: 'buy' | 'sell';
}

export function useKlineChart(options: {
  container: HTMLDivElement | null;
  data: KlineRow[];
  maVisibility: MaVisibility;
  trades: TradeMarker[];
}): {
  fitContent: () => void;
  setVisibleRange: (start: string, end: string) => void;
};
```

**关键 API 映射**：

| 需求 | LC API |
|---|---|
| 蜡烛 | `chart.addCandlestickSeries()` |
| MA 折线 | `chart.addLineSeries()` × 4 |
| BOLL 上下轨 | `chart.addLineSeries()` × 2 |
| BOLL 中轨 | `chart.addLineSeries()` × 1 |
| 买卖点 | `candleSeries.setMarkers([...])` |
| 自适应 | `chart.timeScale().fitContent()` |
| 范围控制 | `chart.timeScale().setVisibleLogicalRange()` |
| 十字光标 | `crosshair: { mode: CrosshairMode.Normal }` |
| 缩放/平移 | LC 内建，无需任何代码 |

### 3.4 颜色与样式规范（A 股惯例）

| 元素 | 颜色 | Hex |
|---|---|---|
| 上涨蜡烛 | 红 | `#ef4444` |
| 下跌蜡烛 | 绿 | `#22c55e` |
| MA5 | 红 | `#ef4444` |
| MA10 | 橙 | `#f59e0b` |
| MA20 | 蓝 | `#2563eb` |
| MA60 | 紫 | `#7c3aed` |
| BOLL 上轨 | 紫 | `#a855f7` |
| BOLL 中轨 | 黄 | `#eab308` |
| BOLL 下轨 | 紫 | `#a855f7` |

与现有 Recharts 配色保持一致（`App.tsx:1019-1071`）。

---

## 四、分阶段实施

### 阶段 0：依赖 + 测试基础设施

**改动**：

1. `web/package.json` 新增：
   ```json
   "lightweight-charts": "^4.2.0"
   ```

2. `web/src/test/setup.ts` 末尾追加：
   ```ts
   // Lightweight Charts needs ResizeObserver in jsdom
   globalThis.ResizeObserver = class {
     observe() {}
     unobserve() {}
     disconnect() {}
   } as any;
   ```

3. `npm install`

**验证**：
- `cd web && npm run test` —— 已有 2 个测试通过
- `npm run dev` —— 启动 OK，无构建报错

---

### 阶段 1：抽离工具函数 + 抽取 panel（无行为变化）

#### 1.1 新建 `web/src/charts/filterByDateRange.ts`

```ts
export function filterByDateRange<T extends { date: string }>(
  rows: T[],
  range: { start: string; end: string } | null
): T[] {
  if (!range) return rows;
  return rows.filter(r => r.date >= range.start && r.date <= range.end);
}
```

#### 1.2 新建 `web/src/charts/buildSeries.ts`

```ts
import type { BacktestResult } from '../types';
import { calcMA, calcBoll } from '../indicators';

type Candle = BacktestResult['price_data'][number];
type Trade = BacktestResult['trades'][number];

// 复用现有 buildTradeMarkerMap 的偶/奇判定语义（见 App.tsx:124-138）
export function buildKlineSeries(data: Candle[]) {
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

// 买卖点独立转换（不混入 K 线数据），保留现有偶/奇判定
export function buildTradeMarkers(trades: Trade[]) {
  return trades.map((t, i) => ({
    date: t.date,
    side: (i % 2 === 0 ? 'buy' : 'sell') as 'buy' | 'sell',
  }));
}
```

> **设计说明**：`buildKlineSeries` 只负责"算指标"，`buildTradeMarkers` 单独负责"转 marker"。两者解耦，对应 hook 的 `data` 与 `trades` 两个独立入参。
>
> **不抽取副图指标逻辑**：MACD/KDJ/Volume/Amount 副图保留在 `App.tsx`，因为它们暂不迁移到 LC，重复只在 `stockIndicatorData` vs `indexIndicatorData` 两处，**目前规模可接受**。

#### 1.3 改 `App.tsx`

- 删除 5 个 `filteredXxx` 重复 `useMemo`
- 替换为：
  ```ts
  const filteredData = useMemo(
    () => filterByDateRange(mergedData, chartDateRange),
    [mergedData, chartDateRange]
  );
  ```
- 同样替换 `filteredPriceData` / `filteredStockIndicatorData` / `filteredIndexData` / `filteredIndicatorData`

#### 1.4 抽取 panel 组件（为集成测试铺路）

> **为什么**：含集成测试需要可独立 mount 的 panel。当前 panel 是 App.tsx 内部 JSX 块，无法隔离测试。

新建 `web/src/panels/StockKlinePanel.tsx`：
```tsx
interface Props {
  data: BacktestResult['price_data'];
  trades: BacktestResult['trades'];
  maVisibility: MaVisibility;
  chartDateRange: DateRange | null;
  defaultStart: string;
  defaultEnd: string;
}

export function StockKlinePanel(props: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const klineData = useMemo(() => buildKlineSeries(props.data), [props.data]);
  const markers = useMemo(() => buildTradeMarkers(props.trades), [props.trades]);
  // 占位：阶段 3 再接 useKlineChart
  return (
    <section className="panel">
      <div className="chart-header">
        <h3>回测股票 K 线 + MA + BOLL</h3>
      </div>
      <div className="line-toggles">...</div>
      <ChartDateRangeControl ... />
      <div className="chart-container" ref={ref} style={{ height: 400 }}>
        {/* 阶段 3 替换为 useKlineChart */}
      </div>
    </section>
  );
}
```

同样抽取 `IndexKlinePanel` / `StockIndicatorPanel` / `IndexIndicatorPanel` / `EquityPanel`（5 个 panel）。`App.tsx` 改为组合这 5 个组件。

**关键边界**：panel 只接收数据 + 配置 props，**不直接调用 API**，不持有 `selectedJob` 等业务状态。

**验证**：
- `git diff --stat web/src/App.tsx` —— 应净减约 80 行（5 处 panel JSX 抽出）
- `npm run test` —— 已有 2 个测试通过
- 浏览器手动 —— 4 个 panel 视觉与交互**完全一致**（此时 K 线 panel 内部还空，等阶段 3 接入）

---

### 阶段 2：`useKlineChart` hook 实现

#### 2.1 新建 `web/src/charts/useKlineChart.ts`

**职责**：
- 接收 `container` ref + 数据 + 可见性 + trades
- 在 `useEffect` 中创建 LC `IChartApi`
- 创建 1 个 candlestick + 4~7 个 line series
- 同步数据、可见性、markers 到 chart
- 卸载时清理

**实现要点**（伪代码）：
```ts
export function useKlineChart({ container, data, maVisibility, trades }: Options) {
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

  // 1. 创建 chart
  useEffect(() => {
    if (!container) return;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 400,
      layout: { background: { color: '#fff' }, textColor: '#1f2937' },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#d1d5db' },
      timeScale: { borderColor: '#d1d5db', timeVisible: false },
      localization: { locale: 'zh-CN', dateFormat: 'yyyy-MM-dd' },
    });
    chartRef.current = chart;

    // 创建所有 series
    const candle = chart.addCandlestickSeries({
      upColor: '#ef4444', downColor: '#22c55e',
      borderUpColor: '#ef4444', borderDownColor: '#22c55e',
      wickUpColor: '#ef4444', wickDownColor: '#22c55e',
    });
    const ma5 = chart.addLineSeries({ color: '#ef4444', lineWidth: 1, priceLineVisible: false });
    // ... 其他 series

    seriesRef.current = { candle, ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower };

    // ResizeObserver
    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth });
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [container]);

  // 2. 同步 K 线数据
  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.candle.setData(
      data.map(d => ({ time: d.date, open: d.open, high: d.high, low: d.low, close: d.close }))
    );
  }, [data]);

  // 3. 同步 MA / BOLL 数据
  useEffect(() => {
    if (!seriesRef.current || !data.length) return;
    const { ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower } = seriesRef.current;
    ma5.setData(toLineData(data, 'ma5'));
    // ... 同样处理其他
  }, [data]);

  // 4. 同步可见性
  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.ma5.applyOptions({ visible: maVisibility.ma5 });
    // ... 同样处理其他
  }, [maVisibility]);

  // 5. 同步 markers
  useEffect(() => {
    if (!seriesRef.current) return;
    const markers: SeriesMarker<Time>[] = trades.map(t => ({
      time: t.date,
      position: t.side === 'buy' ? 'belowBar' : 'aboveBar',
      color: t.side === 'buy' ? '#22c55e' : '#ef4444',
      shape: t.side === 'buy' ? 'arrowUp' : 'arrowDown',
      text: t.side === 'buy' ? 'B' : 'S',
    }));
    seriesRef.current.candle.setMarkers(markers);
  }, [trades]);

  // 6. 自定义 tooltip：OHLC + MA5/10/20/60 当时值
  // 方案：subscribeCrosshairMove → setState → 调用方在容器内渲染 HTML overlay
  const [hoverInfo, setHoverInfo] = useState<{
    date: string; o: number; h: number; l: number; c: number;
    ma5: number | null; ma10: number | null; ma20: number | null; ma60: number | null;
  } | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    const handler = (param: MouseEventParams) => {
      if (!param.time || !seriesRef.current) {
        setHoverInfo(null);
        return;
      }
      const date = param.time as string;
      const row = data.find(d => d.date === date);
      if (!row) { setHoverInfo(null); return; }
      setHoverInfo({
        date, o: row.open, h: row.high, l: row.low, c: row.close,
        ma5: row.ma5 ?? null, ma10: row.ma10 ?? null,
        ma20: row.ma20 ?? null, ma60: row.ma60 ?? null,
      });
    };
    chartRef.current.subscribeCrosshairMove(handler);
    return () => chartRef.current?.unsubscribeCrosshairMove(handler);
  }, [data]);

  // 7. 暴露给调用方的命令式 API
  const fitContent = () => chartRef.current?.timeScale().fitContent();
  const setVisibleRange = (start: string, end: string) => {
    const idx0 = data.findIndex(d => d.date >= start);
    const idx1 = data.findIndex(d => d.date > end);
    if (idx0 === -1 || idx1 === -1) return;
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: idx0, to: idx1 });
  };

  return { fitContent, setVisibleRange, hoverInfo };
}

function toLineData(data: KlineRow[], key: keyof KlineRow) {
  return data
    .map(d => ({ time: d.date, value: d[key] as number | null }))
    .filter(p => p.value !== null) as LineData[];
}
```

#### 2.2 新建 `web/src/charts/useKlineChart.test.tsx`

```tsx
import { render, screen } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it } from 'vitest';
import { useKlineChart } from './useKlineChart';

const sample = [
  { date: '20240101', open: 10, high: 11, low: 9.5, close: 10.5, ma5: 10.2 },
  { date: '20240102', open: 10.5, high: 11.2, low: 10.3, close: 11, ma5: 10.5 },
];

function Harness({ data, maVisibility }: any) {
  const ref = useRef<HTMLDivElement>(null);
  useKlineChart({ container: ref.current, data, maVisibility, trades: [] });
  return <div ref={ref} data-testid="kline-host" />;
}

describe('useKlineChart', () => {
  it('mounts a canvas inside the container', () => {
    render(<Harness data={sample} maVisibility={{ ma5: true, ma10: true, ma20: true, ma60: true, boll: true }} />);
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        const host = screen.getByTestId('kline-host');
        expect(host.querySelector('canvas')).toBeTruthy();
        resolve();
      }, 50);
    });
  });
});
```

**注意**：jsdom 不会真的渲染 canvas 像素，只验证 DOM 存在。`lightweight-charts` 模块通过 `vi.mock` 在 `setup.ts` 中替换为假实现（提供 `createChart` 返回 `{ addCandlestickSeries: () => ({ setData: () => {}, setMarkers: () => {} }), addLineSeries: () => ({ setData: () => {}, applyOptions: () => {} }), timeScale: () => ({ fitContent: () => {}, setVisibleLogicalRange: () => {} }), applyOptions: () => {}, remove: () => {}, subscribeCrosshairMove: () => {} }`），保证 hook 跑完不报错。

**验证**：
- `npm run test` —— hook 测试通过
- `npm run dev` 浏览器手动 —— 临时用 hook 渲染一个 mock K 线，确认 LC 加载、可见

---

### 阶段 3：替换 K 线 panel

#### 3.1 个股 K 线 panel（`App.tsx:965-1105`）

**改前**：Recharts `ComposedChart` + `CandleShape` + 4 条 `Line` + `ReferenceDot` × N（`App.tsx:1073-1090`）

**改后**：
```tsx
const klineRef = useRef<HTMLDivElement>(null);

const klineData = useMemo(
  () => buildKlineSeries(result.price_data),
  [result]
);

const { hoverInfo } = useKlineChart({
  container: klineRef.current,
  data: klineData,
  maVisibility,
  trades: buildTradeMarkers(result.trades),  // 偶/奇判定保留
});

// JSX
<section className="panel">
  <div className="chart-header">
    <h3>回测股票 K 线 + MA + BOLL</h3>
  </div>

  {/* MA / BOLL 切换按钮保持原样 */}
  <div className="line-toggles">...</div>

  <ChartDateRangeControl value={chartDateRange} ... />

  <div className="chart-container" ref={klineRef} style={{ height: 400, position: 'relative' }}>
    {hoverInfo && (
      <div className="kline-tooltip">
        <div>{hoverInfo.date}</div>
        <div>O {hoverInfo.o.toFixed(2)} H {hoverInfo.h.toFixed(2)} L {hoverInfo.l.toFixed(2)} C {hoverInfo.c.toFixed(2)}</div>
        <div>MA5 {fmt(hoverInfo.ma5)} MA10 {fmt(hoverInfo.ma10)} MA20 {fmt(hoverInfo.ma20)} MA60 {fmt(hoverInfo.ma60)}</div>
      </div>
    )}
  </div>
</section>
```

#### 3.2 上证指数 K 线 panel（`App.tsx:1173-1239`）

同样改法，使用 `result.index_data`。

#### 3.3 删除

- `CandleShape`（`App.tsx:64-99`，36 行）
- `klineBuyPoints` / `klineSellPoints` memo（`App.tsx:542-543`）
- K 线版本的 `filteredPriceData` / `filteredIndexData` 中针对 K 线部分的过滤（**但保留给副图使用**，见 §3.4 联动表）
- 相关 imports：`Bar`、`ComposedChart`、`ReferenceDot`（若仅 K 线使用）

**注意**：`BuyMarker` / `SellMarker`（`App.tsx:100-122`）仍用于权益曲线，**保留**。

#### 3.4 联动策略

| 控件 | 作用 |
|---|---|
| 鼠标滚轮 | LC 内建缩放 K 线 |
| 鼠标拖拽 | LC 内建平移 K 线 |
| MA / BOLL 切换按钮 | 通过 `maVisibility` 切换 LC series 可见性 |
| `ChartDateRangeControl` 输入 | **不影响 K 线**（LC 自管视图）；**仅过滤副图** |
| "缩小/放大/重置" 按钮 | **不作用于 K 线**；**仅作用于权益曲线**（保留现状） |
| K线 hover 十字光标 | 触发 hook 的 `hoverInfo`，panel 渲染 HTML tooltip（OHLC + MA5/10/20/60） |

> **取舍**：选择"K 线不响应 `chartDateRange`"，避免与 LC 内建平移冲突。如用户反馈需要"按日期跳转到 K 线"，后续再加 `setVisibleRange` 联动。

**验证**：
- `git diff --stat web/src/App.tsx` —— 应净减约 80 行
- `npm run test` —— 通过
- 浏览器手动：
  - 个股 K 线：滚轮缩放、拖拽平移、十字光标
  - 上证指数 K 线：同上
  - 买卖点对齐 K 线
  - MA5/10/20/60、BOLL 切换显隐
  - 副图仍响应 `chartDateRange`
  - K线 hover 时 HTML tooltip 显示日期 + OHLC + MA5/10/20/60

---

### 阶段 4：清理与文档

#### 4.1 代码清理

- 删除 `CandleShape`（如未删）
- 删除未使用的 imports（`Bar`, `ComposedChart` 如不再使用）
- 合并 `priceDataWithMA` / `indexDataWithMA` —— 现在都通过 `buildKlineSeries` 替代
- 删除 `klineBuyPoints` / `klineSellPoints`（如未删）

#### 4.2 文档

新建 `web/src/charts/README.md`（约 30 行）：
- hook 用法示例
- 颜色规范表
- 与 LC 官方 API 的对应关系

更新 `CLAUDE.md`（项目根目录）顶部：
> Web 分析台 K 线由 `lightweight-charts` 渲染，副图与权益曲线仍用 Recharts。详见 `docs/kline-chart-refactor.md`。

#### 4.3 验证

- `grep -rn "CandleShape" web/src/` —— 无结果
- `grep -rn "filteredPriceData" web/src/` —— 仅副图处使用
- `wc -l web/src/App.tsx` —— 应从 1394 降至 ~1140
- `npm run build` —— 无 TS 报错

---

## 五、文件清单

| 路径 | 动作 | 行数估算 |
|---|---|---|
| `web/package.json` | 修改 | +1 |
| `web/src/test/setup.ts` | 修改 | +5（含 `vi.mock('lightweight-charts')`） |
| `web/src/charts/filterByDateRange.ts` | 新建 | ~10 |
| `web/src/charts/buildSeries.ts` | 新建 | ~35 |
| `web/src/charts/useKlineChart.ts` | 新建 | ~180 |
| `web/src/charts/useKlineChart.test.tsx` | 新建 | ~60 |
| `web/src/panels/EquityPanel.tsx` | 新建 | ~120 |
| `web/src/panels/StockKlinePanel.tsx` | 新建 | ~110 |
| `web/src/panels/StockIndicatorPanel.tsx` | 新建 | ~80 |
| `web/src/panels/IndexKlinePanel.tsx` | 新建 | ~100 |
| `web/src/panels/IndexIndicatorPanel.tsx` | 新建 | ~80 |
| `web/src/panels/StockKlinePanel.test.tsx` | 新建 | ~80 |
| `web/src/panels/IndexKlinePanel.test.tsx` | 新建 | ~80 |
| `web/src/charts/README.md` | 新建 | ~30 |
| `web/src/App.tsx` | 修改 | 净减 ~250（5 panel 抽出 + K 线切 LC） |
| `CLAUDE.md` | 修改 | +2 |

**总新增 ~990 行，删除 ~280 行，净增 ~710 行**。其中：
- 真实功能代码 ~+450（hook + 5 panel + utilities）
- 测试代码 ~+220（mock + 集成测试 + 单测）
- 文档 ~+30
- `App.tsx` 净减 ~250（1394 → ~1140）

---

## 六、风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| Lightweight Charts v4→v5 破坏性升级 | 低 | 锁定 `^4.2.0`，等 v5 稳定再评估 |
| jsdom 缺 `ResizeObserver` / canvas 像素验证 | 中 | `setup.ts` 注入 mock；hook 测试断言 DOM 存在 + 集成测试 mock LC |
| 现有 K 线视觉差异 | 中 | 显式颜色映射（涨红跌绿），先小范围手动验证再合并 |
| 集成测试 mock LC 的复杂度 | 中 | 阶段 1.4 已抽 panel；阶段 2 单独 mock `lightweight-charts` 模块 |
| 性能（千根 K 线） | 低 | LC 官方基准 5K 蜡烛 @ 60fps；本项目最多 ~1500 根 |
| 移动端触摸 | 低 | 本项目为桌面研究台，暂不考虑；LC v4 已支持触屏 |
| 国际化（locale） | 低 | `localization.locale = 'zh-CN'`，`dateFormat = 'yyyy-MM-dd'` |

---

## 七、明确不做（避免范围蔓延）

为贯彻 CLAUDE.md "Simplicity First"：

- ❌ 不重写权益曲线的拖拽缩放
- ❌ 不迁移 MACD / KDJ / Volume 副图到 LC
- ❌ 不实现 K线 ↔ 副图 crosshair / timeScale 双向同步（推迟到未来）
- ❌ 不引入 react-stockcharts / KLineChart 作对比
- ❌ 不做策略对比图的 K 线化
- ❌ 不加新交互（双击自适应、十字线锁定、键盘快捷键）
- ❌ 不动 `buildTradeMarkerMap` 用奇偶判定买卖的"历史行为"
- ❌ 不重写状态管理（保留 `useState` + `useMemo`）
- ❌ 不设回退方案（决策：只进不退；如真出问题则修 hook，不回退 Recharts）

---

## 八、验证清单

每个阶段完成后必跑：

1. `cd web && npm run test` —— 全部通过
   - 阶段 1：已有 2 个测试 + 5 个 panel mount 测试
   - 阶段 2：hook 单测 + LC mock
   - 阶段 3：panel 集成测试（验证 mount 后 canvas + tooltip 出现）
2. `npm run dev` 浏览器手动：
   - 个股 K 线：缩放 / 拖拽 / 十字线流畅
   - 上证指数 K 线：同上
   - 买卖点对齐 K 线
   - MA / BOLL 切换
   - 副图响应 `chartDateRange`
   - 权益曲线缩放按钮、拖拽工作
   - K线 hover：HTML tooltip 显示 OHLC + MA5/10/20/60
3. `git diff --stat web/src/App.tsx` —— 行数符合预期
4. `npm run build` —— 无 TS 报错
5. `grep -n "CandleShape" web/src/` —— 阶段 4 后无结果

---

## 九、参考

- TradingView Lightweight Charts 文档：https://tradingview.github.io/lightweight-charts
- React 集成教程：https://tradingview.github.io/lightweight-charts/tutorials/react/simple
- GitHub 仓库：https://github.com/tradingview/lightweight-charts
- 颜色规范（A股）：红涨 `#ef4444` / 绿跌 `#22c55e`

---

**建议执行顺序**：阶段 0 → 1 → 2 → 3 → 4，每阶段独立可合并。
