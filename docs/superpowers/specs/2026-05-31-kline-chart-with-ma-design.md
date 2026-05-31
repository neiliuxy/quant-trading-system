# K线图 + MA 均线叠加 — 设计文档

**日期**: 2026-05-31
**状态**: 已确认

## 目标

在回测结果页面的权益曲线图表下方，新增一个独立的 K 线图（蜡烛图），叠加 MA5/MA10/MA20/MA60 四条均线，并标记买卖点。每条 MA 线支持独立的显示/隐藏切换。

## 后端改动

### 新增 PriceDataAnalyzer

在 `backtest/service.py` 中新增一个 Backtrader Analyzer，每条 bar 记录当日 OHLC 数据：

```python
class PriceDataAnalyzer(bt.Analyzer):
    def start(self):
        self.rows = []

    def next(self):
        self.rows.append({
            'date': self.strategy.datas[0].datetime.date(0).strftime('%Y%m%d'),
            'open': float(self.datas[0].open[0]),
            'high': float(self.datas[0].high[0]),
            'low': float(self.datas[0].low[0]),
            'close': float(self.datas[0].close[0]),
            'volume': float(self.datas[0].volume[0]),
        })

    def get_analysis(self):
        return self.rows
```

### BacktestResult 新增字段

```python
@dataclass
class BacktestResult:
    # ... 现有字段不变 ...
    price_data: list[dict[str, Any]] = field(default_factory=list)
```

`to_dict()` 自动序列化。无需改动 API 路由层——JSON 序列化自动包含新字段。

### run_backtest_service 注册 Analyzer

在 cerebro 上注册 `PriceDataAnalyzer`，运行后将结果填入 `BacktestResult.price_data`。

## 前端改动

### 类型定义（types.ts）

`BacktestResult` 接口新增字段：

```typescript
price_data: Array<{
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}>;
```

### MA 计算

在前端 `useMemo` 中计算。使用收盘价的简单移动平均（SMA）：

```typescript
function calcMA(data: PriceData[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null; // 数据不足时返回 null
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    return sum / period;
  });
}
```

### K 线蜡烛图

使用 Recharts 的 `<Bar>` 组件配合自定义 `shape` 渲染器绘制蜡烛图。

- 阳线（close >= open）：红色实体 `#ef4444`
- 阴线（close < open）：绿色实体 `#22c55e`
- 影线：`stroke` 跟随实体颜色，`strokeWidth={1}`

### 图表布局

一张 `<ComposedChart>`（不是 LineChart，因为需要叠加 Bar 和 Line）：

| 图层 | 元素 | 实现 |
|------|------|------|
| K 线蜡烛 | 每日 OHLC | `<Bar dataKey="..." shape={<CandleShape />}>` |
| MA5 | 收盘价 5 日均线 | `<Line dataKey="ma5" stroke="#ef4444">` |
| MA10 | 收盘价 10 日均线 | `<Line dataKey="ma10" stroke="#f59e0b">` |
| MA20 | 收盘价 20 日均线 | `<Line dataKey="ma20" stroke="#2563eb">` |
| MA60 | 收盘价 60 日均线 | `<Line dataKey="ma60" stroke="#7c3aed">` |
| 买入点 | 绿色圆点 | `<ReferenceDot fill="#22c55e">` |
| 卖出点 | 红色圆点 | `<ReferenceDot fill="#ef4444">` |

所有线 `dot={false}`，`isAnimationActive={false}`。

### MA 显示/隐藏控制

新增 `MaVisibility` 状态：

```typescript
interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
}
```

默认全部为 `true`。Toggle 按钮放在 K 线图上方，与现有 `line-toggles` 风格一致（Eye/EyeOff 图标）。

### 交互

- 同样支持左右拖动浏览
- 同样支持日期范围过滤（复用现有的 `chartDateRange` 状态？还是独立的？）

> **决策**：K 线图暂不实现独立的缩放/拖动/日期过滤。直接显示全量数据。简单的 K 线图不需要和权益曲线一样的复杂交互，后续有需求再加。

### 文件改动清单

| 文件 | 改动 |
|------|------|
| `backtest/service.py` | 新增 `PriceDataAnalyzer`，`BacktestResult` 加字段，注册 analyzer |
| `web/src/types.ts` | `BacktestResult` 加 `price_data` |
| `web/src/App.tsx` | 新增 K 线图面板 + MA toggle + CandleShape 组件 |
| `web/src/styles.css` | K 线图、MA toggle 相关样式 |

## 不考虑

- 成交量柱状图 — YAGNI
- K 线图独立缩放/拖动 — 后续按需添加
- 其他技术指标（布林带、MACD 等）— 本次只做 MA
- MA 参数可配置 — 固定 5/10/20/60

## 验证方式

1. 运行一次回测，确认 API 返回包含 `price_data` 字段
2. 前端确认 K 线图正确渲染（蜡烛颜色、影线、MA 线）
3. 点击 MA toggle 按钮确认各线显示/隐藏正常
4. 买卖点标记位置与交易记录日期对应
