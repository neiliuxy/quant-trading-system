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