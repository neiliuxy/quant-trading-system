# K线图 + MA 均线 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在权益曲线下方新增独立 K 线图，叠加 MA5/10/20/60 均线和买卖点，支持 MA 切换

**Architecture:** 后端新增 PriceDataAnalyzer 收集 OHLC 数据通过 API 传递；前端 precompute 价格→像素映射和 MA 值，用 ComposedChart + Bar custom shape 渲染蜡烛图，Line 渲染均线，ReferenceDot 标记买卖点

**Tech Stack:** Python Backtrader (Analyzer), TypeScript React + Recharts (ComposedChart, Bar shape, Line)

---

### Task 1: 后端 — 新增 PriceDataAnalyzer + BacktestResult.price_data

**Files:**
- Modify: `backtest/service.py`

- [ ] **Step 1: 在 TradeListAnalyzer 后添加 PriceDataAnalyzer 类**

在 `backtest/service.py` 的 `TradeListAnalyzer` 类之后（约第 102 行之后），`_market_score_payload` 函数之前插入：

```python
class PriceDataAnalyzer(bt.Analyzer):
    """收集每根 bar 的 OHLC 数据，用于前端 K 线图渲染"""
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

- [ ] **Step 2: BacktestResult dataclass 添加 price_data 字段**

修改 `BacktestResult` dataclass（约第 53-66 行），在 `market_scores` 之后添加 `price_data` 字段：

```python
@dataclass
class BacktestResult:
    symbol: str
    start: str
    end: str
    initial_cash: float
    final_value: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    market_scores: list[dict[str, Any]] = field(default_factory=list)
    market_score_summary: dict[str, float] = field(default_factory=dict)
    price_data: list[dict[str, Any]] = field(default_factory=list)
```

- [ ] **Step 3: run_backtest_service 中注册 analyzer 并提取数据**

在 `run_backtest_service` 函数中（约第 152 行），在现有 `cerebro.addanalyzer` 调用之后添加一行注册 `PriceDataAnalyzer`：

```python
cerebro.addanalyzer(PriceDataAnalyzer, _name='price')
```

然后在构建 `BacktestResult` 时（约第 169-183 行），添加 `price_data` 参数：

```python
return BacktestResult(
    symbol=req.symbol,
    start=req.start,
    end=req.end,
    initial_cash=req.cash,
    final_value=final_value,
    total_return_pct=float(total_return_pct),
    max_drawdown_pct=float(drawdown.get('max', {}).get('drawdown', 0.0) or 0.0),
    trade_count=total_closed,
    win_rate_pct=float(win_rate_pct),
    equity_curve=strategy.analyzers.equity.get_analysis(),
    trades=trades,
    market_scores=score_rows,
    market_score_summary=score_summary,
    price_data=strategy.analyzers.price.get_analysis(),
)
```

- [ ] **Step 4: 验证后端改动**

运行：`cd D:/Workspace/quantx/quant-trading-system && source .venv/Scripts/activate && python backtest/run_backtest.py --symbol 000001 --start 20230101 --end 20231231`

预期：回测正常完成，无报错。

- [ ] **Step 5: 提交**

```bash
git add backtest/service.py
git commit -m "feat: add PriceDataAnalyzer and price_data field to BacktestResult"
```

---

### Task 2: 前端 — types.ts 添加 price_data 类型

**Files:**
- Modify: `web/src/types.ts`

- [ ] **Step 1: BacktestResult 接口添加 price_data 字段**

在 `web/src/types.ts` 的 `BacktestResult` 接口中（第 57 行 `market_score_summary` 之后）添加：

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

- [ ] **Step 2: 提交**

```bash
git add web/src/types.ts
git commit -m "feat: add price_data type to BacktestResult interface"
```

---

### Task 3: 前端 — App.tsx 添加 K 线图和 MA 均线

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: 添加 imports**

在 `web/src/App.tsx` 顶部，将 `LineChart` 导入改为 `ComposedChart, Bar`（因为 K 线需要 `ComposedChart` 叠加 Bar + Line）：

```typescript
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ComposedChart,
  Bar,
  ReferenceDot,
} from 'recharts';
```

（`LineChart` 保留——权益曲线部分仍然用 `LineChart`）

- [ ] **Step 2: 添加 MaVisibility 接口和状态**

在现有 `LineVisibility` 接口（约第 76 行）之后添加：

```typescript
interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
}
```

在现有 `lineVisibility` 状态（约第 96 行）之后添加：

```typescript
const [maVisibility, setMaVisibility] = useState<MaVisibility>({
  ma5: true,
  ma10: true,
  ma20: true,
  ma60: true,
});
```

与 `toggleLineVisibility` 并列（约第 324 行之后）添加：

```typescript
const toggleMaVisibility = (ma: keyof MaVisibility) => {
  setMaVisibility(prev => ({
    ...prev,
    [ma]: !prev[ma],
  }));
};
```

- [ ] **Step 3: 添加 MA 计算和 K 线数据处理**

在现有 `filteredData` useMemo 之后（约第 235 行之后）添加：

```typescript
const priceDataWithMA = useMemo(() => {
  if (!result?.price_data?.length) return [];

  const data = result.price_data;

  // 计算简单移动平均
  function calcMA(period: number): (number | null)[] {
    return data.map((_, i) => {
      if (i < period - 1) return null;
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[i - j].close;
      return parseFloat((sum / period).toFixed(2));
    });
  }

  const ma5 = calcMA(5);
  const ma10 = calcMA(10);
  const ma20 = calcMA(20);
  const ma60 = calcMA(60);

  // 价格范围（用于蜡烛图映射）
  const lows = data.map(d => d.low);
  const highs = data.map(d => d.high);
  const minPrice = Math.min(...lows) * 0.98;
  const maxPrice = Math.max(...highs) * 1.02;
  const priceRange = maxPrice - minPrice || 1;

  // 构建交易日标记（买卖点）
  const tradeMap = new Map<string, { buy?: boolean; sell?: boolean }>();
  result.trades.forEach((trade, index) => {
    if (!tradeMap.has(trade.date)) {
      tradeMap.set(trade.date, {});
    }
    const marker = tradeMap.get(trade.date)!;
    if (index % 2 === 0) {
      marker.buy = true;
    } else {
      marker.sell = true;
    }
  });

  return data.map((d, i) => ({
    ...d,
    ma5: ma5[i],
    ma10: ma10[i],
    ma20: ma20[i],
    ma60: ma60[i],
    // 预计算 0-1 归一化 y 坐标（0 = 顶部，1 = 底部）
    // 用于蜡烛图 custom shape
    highY: (maxPrice - d.high) / priceRange,
    lowY: (maxPrice - d.low) / priceRange,
    openY: (maxPrice - d.open) / priceRange,
    closeY: (maxPrice - d.close) / priceRange,
    ...tradeMap.get(d.date),
  }));
}, [result]);
```

- [ ] **Step 4: 添加 CandleShape 渲染函数**

在 `App` 组件外部（`export default function App()` 之前）添加一个工厂函数，生成蜡烛图形状：

```typescript
function createCandleShape(chartHeight: number) {
  return function CandleShape(props: any) {
    const { x, y, width, payload } = props;
    const { open, high, low, close, highY, lowY, openY, closeY } = payload;
    if (open === undefined) return null;

    const isUp = close >= open;
    const color = isUp ? '#ef4444' : '#22c55e';
    const cx = x + width / 2;
    const h = chartHeight;

    const wickTop = h * highY;
    const wickBottom = h * lowY;
    const bodyTop = h * (isUp ? closeY : openY);
    const bodyBottom = h * (isUp ? openY : closeY);

    return (
      <g>
        <line x1={cx} y1={wickTop} x2={cx} y2={wickBottom} stroke={color} strokeWidth={1} />
        <rect
          x={cx - 3}
          y={bodyTop}
          width={6}
          height={Math.max(1, bodyBottom - bodyTop)}
          fill={isUp ? color : 'transparent'}
          stroke={color}
          strokeWidth={1}
        />
      </g>
    );
  };
}
```

- [ ] **Step 5: 在权益曲线面板下方添加 K 线图面板**

在权益曲线的 `</section>` 闭合标签之后（约第 738 行 `</section>` 之前的那行）、交易记录 `<section>` 之前，插入 K 线图面板：

```tsx
{result?.price_data?.length > 0 && (
  <section className="panel">
    <div className="chart-header">
      <h3>K 线图 & MA 均线</h3>
    </div>

    <div className="line-toggles">
      <button
        className={`toggle-btn ${maVisibility.ma5 ? 'active' : ''}`}
        onClick={() => toggleMaVisibility('ma5')}
      >
        {maVisibility.ma5 ? <Eye size={14} /> : <EyeOff size={14} />}
        MA5
      </button>
      <button
        className={`toggle-btn ${maVisibility.ma10 ? 'active' : ''}`}
        onClick={() => toggleMaVisibility('ma10')}
      >
        {maVisibility.ma10 ? <Eye size={14} /> : <EyeOff size={14} />}
        MA10
      </button>
      <button
        className={`toggle-btn ${maVisibility.ma20 ? 'active' : ''}`}
        onClick={() => toggleMaVisibility('ma20')}
      >
        {maVisibility.ma20 ? <Eye size={14} /> : <EyeOff size={14} />}
        MA20
      </button>
      <button
        className={`toggle-btn ${maVisibility.ma60 ? 'active' : ''}`}
        onClick={() => toggleMaVisibility('ma60')}
      >
        {maVisibility.ma60 ? <Eye size={14} /> : <EyeOff size={14} />}
        MA60
      </button>
    </div>

    <div className="chart-container">
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={priceDataWithMA}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" minTickGap={32} />
          <YAxis domain={['auto', 'auto']} />
          <Tooltip />
          <Legend />
          <Bar
            dataKey="close"
            shape={createCandleShape(400)}
            isAnimationActive={false}
            legendType="none"
          />
          {maVisibility.ma5 && (
            <Line
              type="monotone"
              dataKey="ma5"
              stroke="#ef4444"
              dot={false}
              strokeWidth={1.5}
              name="MA5"
              isAnimationActive={false}
              connectNulls={false}
            />
          )}
          {maVisibility.ma10 && (
            <Line
              type="monotone"
              dataKey="ma10"
              stroke="#f59e0b"
              dot={false}
              strokeWidth={1.5}
              name="MA10"
              isAnimationActive={false}
              connectNulls={false}
            />
          )}
          {maVisibility.ma20 && (
            <Line
              type="monotone"
              dataKey="ma20"
              stroke="#2563eb"
              dot={false}
              strokeWidth={1.5}
              name="MA20"
              isAnimationActive={false}
              connectNulls={false}
            />
          )}
          {maVisibility.ma60 && (
            <Line
              type="monotone"
              dataKey="ma60"
              stroke="#7c3aed"
              dot={false}
              strokeWidth={1.5}
              name="MA60"
              isAnimationActive={false}
              connectNulls={false}
            />
          )}
          {priceDataWithMA.map((point, index) => (
            point.buy && (
              <ReferenceDot
                key={`kline-buy-${index}`}
                x={point.date}
                y={point.close}
                r={5}
                fill="#22c55e"
                stroke="#16a34a"
                strokeWidth={2}
              />
            )
          ))}
          {priceDataWithMA.map((point, index) => (
            point.sell && (
              <ReferenceDot
                key={`kline-sell-${index}`}
                x={point.date}
                y={point.close}
                r={5}
                fill="#ef4444"
                stroke="#dc2626"
                strokeWidth={2}
              />
            )
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>

    <div className="trade-legend">
      <div className="trade-legend-item">
        <div className="trade-legend-dot buy"></div>
        <span>买入点</span>
      </div>
      <div className="trade-legend-item">
        <div className="trade-legend-dot sell"></div>
        <span>卖出点</span>
      </div>
    </div>
  </section>
)}
```

- [ ] **Step 6: 添加 K 线图 tooltip 格式化**

在 K 线图的 `<ComposedChart>` 内（`<Tooltip />` 替换为）：

```tsx
<Tooltip
  formatter={(value: any, name: string) => {
    if (name === 'MA5') return [value?.toFixed(2), 'MA5'];
    if (name === 'MA10') return [value?.toFixed(2), 'MA10'];
    if (name === 'MA20') return [value?.toFixed(2), 'MA20'];
    if (name === 'MA60') return [value?.toFixed(2), 'MA60'];
    return [value, name];
  }}
  labelFormatter={(label: string) => {
    const point = priceDataWithMA.find(d => d.date === label);
    if (!point) return label;
    return `${label} | O:${point.open?.toFixed(2)} H:${point.high?.toFixed(2)} L:${point.low?.toFixed(2)} C:${point.close?.toFixed(2)}`;
  }}
/>
```

- [ ] **Step 7: 运行前端验证**

前提：后端已运行 `python server/main.py`。

```bash
cd D:/Workspace/quantx/quant-trading-system/web && npm run dev
```

在浏览器打开 `http://localhost:5173`，运行一次回测（如平安银行 000001），确认：
1. 权益曲线下方出现 K 线图
2. 蜡烛颜色正确（红涨绿跌）
3. MA5/10/20/60 四条线可见
4. 点击 toggle 按钮可以切换各 MA 线
5. 买卖点标记正确

- [ ] **Step 8: 提交**

```bash
git add web/src/App.tsx web/src/styles.css
git commit -m "feat: add kline chart with MA5/10/20/60 overlay and toggle controls"
```

---

### 自检清单

- [x] Spec 覆盖：price_data 后端收集 ✓、K线蜡烛渲染 ✓、MA 计算 ✓、4 条 MA 线切换 ✓、买卖点标记 ✓
- [x] 无占位符：所有步骤包含完整代码
- [x] 类型一致：`price_data` 字段名在后端 dataclass 和前端 types.ts 中一致；`MaVisibility` 的 key 名 `ma5/ma10/ma20/ma60` 与数据处理中的字段名一致
