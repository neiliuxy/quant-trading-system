# 上证指数 K 线 + 技术指标板块 — 设计文档

**日期**: 2026-06-03
**状态**: 已确认

## 目标

在回测结果页面新增两个板块：

1. **上证指数 K 线 + MA + BOLL**：每个交易日一根蜡烛，叠加 MA5/10/20/60 四条均线，叠加布林带（上轨/中轨/下轨）三条线。每条 MA 和 BOLL 都可以独立 toggle。
2. **上证指数技术指标子图**：同时只显示一个指标，可通过下拉菜单在 MACD / KDJ / 交易量 / 交易额 之间切换。默认显示 MACD。

数据周期与回测周期一致，**不**默认跟随其他图表的局部缩放（用户没改 `chartDateRange` 时显示完整回测周期；用户改了之后会跟随——因为日期范围过滤器是全局状态）。

## 页面布局

从上到下 4 个 panel：

1. 权益曲线 & 市场评分（**已有，不动**）
2. 股票 K 线 + MA + 买卖点（**已有，不动**）
3. **新增**：上证指数 K 线 + MA + BOLL
4. **新增**：上证指数技术指标（下拉切换）

不删除任何现有板块。股票 K 线 + MA 板块保留，作为「个股本身走势」的视图；新增的「上证指数」板块作为大盘参考标尺。

## 后端改动

### `backtest/data_loader.py`

扩展 `load_shanghai_composite` 让它返回的 DataFrame 额外带 `amount` 列。

- 新增常量 `INDEX_STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']`
- `_AKSHARE_COLUMN_MAP` 增加 `'成交额': 'amount'`
- 缓存命中校验从 `set(df.columns) != set(STANDARD_COLUMNS)` 改为 `set(df.columns) != set(INDEX_STANDARD_COLUMNS)`
- 列集合不匹配的文件**跳过但不删除**——保留旧缓存作为回滚保险，触发重新下载并写入新格式文件
- `STANDARD_COLUMNS`（股票的 6 列）保持不变，**不要**为了复用常量把它升级到 7 列——股票侧没有 amount，强行共用会破坏现有逻辑

### `backtest/service.py`

`run_backtest_service` 在调用 Cerebro 之前加载指数数据，**不**经过 Backtrader 管线：

```python
df = load_market_data(req.symbol, req.start, req.end)
index_df = load_shanghai_composite(req.start, req.end)

index_data: list[dict] = []
if index_df is not None and not index_df.empty:
    for _, row in index_df.iterrows():
        index_data.append({
            'date': row['date'].strftime('%Y%m%d'),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume']),
            'amount': float(row['amount']),
        })

# Cerebro 流程完全不变 —— datas[0] 仍然只有股票
data = bt.feeds.PandasData(dataname=df, datetime=0)
cerebro = bt.Cerebro()
cerebro.adddata(data)
# ... 策略、分析器都和现在一样
```

**`BacktestResult` 新增字段：**

```python
index_data: list[dict[str, Any]] = field(default_factory=list)
```

`to_dict()` 自动序列化，前端 JSON 可见。**不**新增 `IndexDataAnalyzer`——直接用 `index_df` 转 list 更简洁，零侵入 Cerebro。

### 不修改的部分

- `load_market_data`（股票数据加载）—— 不动
- `PriceDataAnalyzer`（股票 OHLCV 收集）—— 不动
- 任何策略类（`strategies/*.py`）—— 不动
- `server/api.py` —— 不动，JSON 序列化自动透传新字段
- `server/db.py` —— 不动，结果存的是 `artifact_path` 指向的 JSON 文件

## 前端改动

### `web/src/types.ts`

```typescript
BacktestResult 增加：
  index_data: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    amount: number;
  }>;
```

### `web/src/App.tsx`

**新增状态：**

```typescript
interface IndexMaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;        // 新增
}

const [indexMaVisibility, setIndexMaVisibility] = useState<IndexMaVisibility>({
  ma5: true,
  ma10: true,
  ma20: true,
  ma60: true,
  boll: false,          // 默认关，避免和 MA 重叠视觉过载
});
const [selectedIndicator, setSelectedIndicator] = useState<
  'macd' | 'kdj' | 'volume' | 'amount'
>('macd');
```

**`useMemo` 计算（前端算所有指标）：**

| 函数 | 输入 | 输出 |
|---|---|---|
| `indexDataWithMA` | `result.index_data` | 加 `ma5/10/20/60` + `boll_upper/mid/lower`（中轨=MA20） |
| `indexDataWithMacd` | `indexDataWithMA` | 加 `dif, dea, macd`（EMA12/26/9 标准算法） |
| `indexDataWithKdj` | `indexDataWithMA` | 加 `k, d, j`（9 日 RSV → K=2/3·K_prev+1/3·RSV，D 类似，J=3K-2D） |
| `filteredIndexData` | 上述结果 | 按 `chartDateRange` 切片 |

**`filteredIndexData` 的特征：**
- 用 `date` 字符串匹配/切片，**不**用数组下标
- 跟现有的 `filteredPriceData` 用同一份 `chartDateRange` 状态
- 股票侧缺失日期的指数点照常显示（指数几乎不会缺日期）

**指标公式实现：**

```typescript
function calcEMA(values: number[], period: number): (number | null)[] {
  // 简单 EMA：前 period-1 个返回 null，第 period 个用 SMA 作为种子
  const k = 2 / (period + 1);
  const result: (number | null)[] = [];
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { result.push(null); continue; }
    if (prev === null) {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += values[i - j];
      prev = sum / period;
    } else {
      prev = values[i] * k + prev * (1 - k);
    }
    result.push(prev);
  }
  return result;
}

function calcMACD(closes: number[]) {
  const ema12 = calcEMA(closes, 12);
  const ema26 = calcEMA(closes, 26);
  const dif = ema12.map((v, i) => v !== null && ema26[i] !== null ? v - ema26[i]! : null);
  // DEA 是 DIF 的 9 日 EMA
  const difValues = dif.map(v => v ?? 0);
  const deaRaw = calcEMA(difValues, 9);
  const dea = dea.map((v, i) => dif[i] !== null ? deaRaw[i] : null);
  // MACD 柱 = (DIF - DEA) × 2
  const macd = dif.map((v, i) => v !== null && dea[i] !== null ? (v - dea[i]!) * 2 : null);
  return { dif, dea, macd };
}
```

KDJ 和 BOLL 用类似的纯函数实现。BOLL：`upper = MA20 + 2σ`，`lower = MA20 - 2σ`，`mid = MA20`（σ 是 20 日收盘价标准差）。

### UI 布局

**新增 Panel 3 — 上证指数 K 线 + MA + BOLL：**

```
┌─ 上证指数 K 线 + MA + BOLL ─────────────────────────────┐
│ [MA5] [MA10] [MA20] [MA60] [BOLL]   ← 5 个 toggle       │
│ <日期范围输入>（复用现有 chartDateRange 状态）          │
│ <ResponsiveContainer>                                  │
│   <ComposedChart>                                       │
│     <Bar dataKey="close" shape={CandleShape}/>          │
│     {ma5 && <Line dataKey="ma5" stroke="#ef4444"/>}     │
│     {ma10 && <Line dataKey="ma10" stroke="#f59e0b"/>}   │
│     {ma20 && <Line dataKey="ma20" stroke="#2563eb"/>}   │
│     {ma60 && <Line dataKey="ma60" stroke="#7c3aed"/>}   │
│     {boll &&                                            │
│       <Line dataKey="boll_upper" stroke="#a855f7"/>     │
│       <Line dataKey="boll_mid" stroke="#eab308"/>       │
│       <Line dataKey="boll_lower" stroke="#a855f7"/>}    │
│   </ComposedChart>                                      │
│ </ResponsiveContainer>                                  │
│                                                         │
│ 蜡烛：阳线 #ef4444 阴线 #22c55e（同股票 K 线配色）      │
│ 买卖点：不绘制（上证指数是参考标尺，不是被交易对象）     │
└─────────────────────────────────────────────────────────┘
```

**新增 Panel 4 — 上证指数技术指标：**

```
┌─ 上证指数 技术指标 ─── [下拉: MACD ▼] ──────────────────┐
│ <ResponsiveContainer>                                  │
│   <ComposedChart>                                       │
│     {selectedIndicator === 'macd' && (                 │
│       <Bar dataKey="macd">  /* 红绿柱 */                │
│       <Line dataKey="dif" stroke="..."/>               │
│       <Line dataKey="dea" stroke="..."/>               │
│     )}                                                  │
│     {selectedIndicator === 'kdj' && (                  │
│       <Line dataKey="k" stroke="#f3f4f6"/>             │
│       <Line dataKey="d" stroke="#facc15"/>             │
│       <Line dataKey="j" stroke="#a855f7"/>             │
│       <ReferenceLine y={80}/> <ReferenceLine y={20}/>  │
│     )}                                                  │
│     {selectedIndicator === 'volume' && (               │
│       <Bar dataKey="volume" /* 涨红跌绿 */ />          │
│     )}                                                  │
│     {selectedIndicator === 'amount' && (                │
│       <Bar dataKey="amount" /* 涨红跌绿，单位亿元 */ />│
│     )}                                                  │
│   </ComposedChart>                                      │
│ </ResponsiveContainer>                                  │
└─────────────────────────────────────────────────────────┘
```

### 颜色规范

- 蜡烛：阳线 `#ef4444`，阴线 `#22c55e`（与股票 K 线一致）
- MA5 `#ef4444`、MA10 `#f59e0b`、MA20 `#2563eb`、MA60 `#7c3aed`（与股票 MA 配色一致，方便用户对位识别）
- BOLL 上轨 `#a855f7`、中轨 `#eab308`、下轨 `#a855f7`
- MACD：DIF `#facc15`、DEA `#f97316`、柱状图阳柱 `#ef4444` 阴柱 `#22c55e`（与同花顺/东方财富一致）
- KDJ：K `#f3f4f6`、D `#facc15`、J `#a855f7`
- 交易量/交易额：阳柱 `#ef4444` 阴柱 `#22c55e`，颜色按当日涨跌（close vs open）

### 工具提示（Tooltip）

K 线子图工具提示显示日期 + O/H/L/C 4 个值，与现有股票 K 线 tooltip 行为一致。指标子图工具提示显示对应字段名 + 数值。

### 复用与样式

- 复用现有 `CandleShape` 函数（`App.tsx:77-111`）
- 复用 `line-toggles` / `toggle-btn` 样式（`styles.css:102-135`）
- 复用 `chart-date-range` / `chart-header` 容器样式
- 不需要新增 CSS——所有视觉元素都用现有 class

## 错误处理

**1. `load_shanghai_composite` 返回 `None`（AkShare 三次重试都失败）**
- 后端：`index_data = []`，回测正常完成，不抛错
- 前端：`index_data.length === 0` 时不渲染图表，显示「上证指数数据加载失败，请重试回测」+ 重新运行按钮

**2. 缓存 schema 不匹配（旧文件没 amount 列）**
- 扫描缓存时列集合检查失败 → 跳过该文件
- 继续找其他匹配缓存，都没有则触发重新下载
- **不**主动删除旧文件（保守策略，避免误删）

**3. 指数数据 < 股票交易日数**
- 个别日期停牌/休市差异
- 前端按 `date` 字符串匹配，缺失日期的指数点不存在
- 该日期的 BOLL/MA/MACD/KDJ 值在该行不存在（不是 `null`，是整行没数据）
- 已渲染的天数不受影响，线段自然断开

**4. 指标公式初期数据不足**
- BOLL 需要 20 天、MACD 需要 26+9=35 天、KDJ 需要 9 天
- 统一返回 `null`（不是 `0`，否则线会从 0 起跳）
- Line 组件用 `connectNulls={false}`，Bar 用空 height（Recharts 默认不画）

**5. 日期范围过滤边界**
- 用户清空 `chartDateRange`（点重置）→ 4 个图表都回到完整回测周期
- 用户手填 `20200101` 至 `20230101` → 4 个图表都切片到该范围

## 测试

**新增 `tests/test_indicators.py`**（pytest）：

| 测试 | 验证 |
|---|---|
| `test_calc_ma_5_basic` | 已知序列 MA5 前 4 天 null，第 5 天起有值 |
| `test_calc_ma_5_values` | 已知序列 MA5 第 5 天 = 5 个数平均 |
| `test_calc_macd_basic` | 序列长度 < 35 时全 null |
| `test_calc_macd_values` | 已知收盘价序列，DIF/DEA/MACD 关键日值匹配手算 |
| `test_calc_kdj_basic` | 序列长度 < 9 时全 null |
| `test_calc_kdj_known` | 已知 RSV 序列，K/D/J 第 1-3 日递推值正确 |
| `test_calc_boll_basic` | 序列长度 < 20 时全 null |
| `test_calc_boll_known` | 已知序列，mid=MA20，upper/lower=mid ± 2σ |
| `test_index_data_loading` | `load_shanghai_composite` 拉到的 df 有 7 列（含 amount） |

**现有测试不需修改**：`test_service`、`test_api`、`test_market` 等都不涉及指数板块。

## 文件改动清单

| 文件 | 改动 |
|---|---|
| `backtest/data_loader.py` | 新增 `INDEX_STANDARD_COLUMNS`，扩展 `_AKSHARE_COLUMN_MAP`，改缓存校验 |
| `backtest/service.py` | `run_backtest_service` 加载指数并加进 `BacktestResult.index_data` |
| `web/src/types.ts` | `BacktestResult` 加 `index_data` 字段 |
| `web/src/App.tsx` | 新增 2 个 panel、状态、useMemo、指标公式 |
| `tests/test_indicators.py` | 新增指标公式单测 |

## 不考虑（YAGNI）

- BOLL 参数可配置（默认 20 日 + 2σ，写死即可）
- MA 周期可配置（5/10/20/60 写死）
- 拖动缩放（K 线子图不需要，权益曲线才有这个交互）
- 多股票对比时的指数叠加
- 上证指数自身的买卖点标记
- 缓存的自动迁移脚本（下次自然重新下载即可）
- 单元测试覆盖空数组、空字符串、负数等异常输入（公式是纯数学，正常数据下不会出问题，YAGNI）

## 验证方式

1. 后端：`python backtest/run_backtest.py --symbol 000001 --start 20230101 --end 20231231`，确认 `data/quantx.sqlite` 关联的 artifact JSON 含 `index_data` 字段且每行有 `amount`
2. 前端：启动 web，打开任一回测，确认面板 3 显示蜡烛 + MA + BOLL，5 个 toggle 可切换
3. 下拉切到 KDJ → 3 条线 + 80/20 虚线；切到交易量 → 红绿柱；切到交易额 → 红绿柱（带亿元单位）
4. 改 `chartDateRange` 日期 → 4 个图表同步缩放
5. pytest：`python -m pytest -q tests/test_indicators.py` 全绿

## 风险 & 注意事项

- **缓存迁移**：`sh000001_*.csv` 老文件（无 `amount` 列）会触发重新下载。已有缓存命中后会继续写新格式。无需手动清理
- **AkShare `index_zh_a_hist` 的 `成交额` 列名**已经验证存在于返回 DataFrame 中。如果未来 AkShare 改名/删列，缓存读取会失败并触发重新下载
- **首次运行会触发 `ak.index_zh_a_hist` 网络请求**——和现有 `stock_zh_a_hist` 一样慢（3-10 秒）。UI 上回测状态会一直显示「运行中」
- **指标公式精度**：`parseFloat((value).toFixed(2))` 在前端用于截断；测试时用 Python 算同样的数，容差 ±0.01 即可
