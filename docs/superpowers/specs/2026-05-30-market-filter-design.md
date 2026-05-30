# 市场宏观过滤器设计

## 目标

在个股策略运行前，先判断整体市场状态（上证趋势、情绪、量能），合成 0~1 的"市场评分"，策略买入时按评分调节仓位。评分低时少买或不买，评分高时满仓。卖出不受评分影响，全部清仓。

市场过滤器是独立模块，可复用于未来任意策略。

## 架构

```
market/                          # 新增目录
  ├── __init__.py
  ├── market_analyzer.py         # 对外: get_market_score(start, end) → DataFrame
  └── indicators.py             # 三个纯函数

strategies/swing_ma_boll.py     # 修改: 新增 market_score_df 参数, 买入时仓位 = base × score
backtest/run_backtest.py        # 修改: 回测前先调 get_market_score(), 缓存 + 传入策略
backtest/stock_selector.py      # 修改: 批量回测前共享同一份市场评分

backtest/data_loader.py         # 不改
```

### 调用顺序

```
run_backtest.py:
  1. get_market_score(start, end)   → 有缓存读缓存，无缓存计算 + 缓存到 data/
  2. load_market_data(symbol, start, end)
  3. cerebro.run()  → 策略内使用 market_score_dict
```

## 市场评分计算

### 三个子维度

| 维度 | 权重 | 指标 | 数据源 | 归一化方式 |
|------|------|------|--------|-----------|
| A 趋势 | 50% | MA20 + MA60 多状态判断 | 上证指数日线 | 5 档离散: 0 / 0.25 / 0.5 / 0.75 / 1.0 |
| B 情绪 | 30% | ① 上证日内强度 ② 短期涨跌惯性 | 上证指数日线 (OHLC 派生) | 滚动 3 年分位 → 0~1, 等权合成 |
| C 量能 | 20% | 沪深两市成交额合计 | 上证+深证日线 amount 求和 | 滚动 3 年分位 → 梯形映射 0~1 |

所有数据最终都由 `stock_zh_index_daily_em` 覆盖: 上证 `sh000001` (趋势+情绪) + 深证 `sz399001` (量能补充)。

合成: `score = A × 0.5 + B × 0.3 + C × 0.2`, 范围 0~1

所有关键参数可配置（均线周期、权重、分位窗口、阈值），默认值基于研报实践设定，后续可通过回测调优。

### A. 趋势评分 (50%)

基于 MA20("生命线") + MA60("牛熊分界线") 组合:

```
多头 (MA60 向上 + MA20 > MA60 + 价格 > MA20)  → 1.00
偏多 (MA60 向上 + MA20 > MA60)                → 0.75
中性 (MA60 走平 或 MA20/MA60 反复穿越)        → 0.50
偏空 (MA60 向下 + MA20 < MA60)                → 0.25
空头 (MA60 向下 + MA20 < MA60 + 价格 < MA20)  → 0.00
```

MA60 方向判定: `MA60(today)` vs `MA60(5 日前)`, 涨幅 > 0.3% 为"向上", 跌幅 > 0.3% 为"向下", 否则"走平"。

可配置参数: `trend_ma_fast=20`, `trend_ma_slow=60`, `trend_direction_lookback=5`, `trend_flat_threshold=0.003`

### B. 情绪评分 (30%)

两个子指标等权合成，均从同一数据源 `stock_zh_index_daily_em('sh000001')` 的上证 OHLC 推导，无需额外 API:

1. **上证日内强度** (权重 15%): `(close - open) / (high - low)`，衡量日内多空力量对比。取滚动 3 年分位映射到 0~1:
   - 高开高走、收在全天高点附近 → 强度接近 1.0，多头主导
   - 高开低走、收在全天低点附近 → 强度接近 0.0，空头主导
   - `high = low` (一字板等极端情况) → 强度 = 0.5

2. **短期涨跌惯性** (权重 15%): 过去 20 个交易日中上涨天数占比。取滚动 3 年分位映射到 0~1:
   - > 70% 的交易日收涨 → 近期多头氛围浓
   - < 30% 的交易日收涨 → 近期空头主导

分位计算: 当前值在过去 N 年中处于什么位置 (0% = 历史最低, 100% = 历史最高), 直接作为 0~1 分数。

可配置参数: `sentiment_lookback_years=3`, `sentiment_short_term_window=20`

*注: AkShare 截至 2026-05-30 未提供"全A涨跌家数日频历史"单一接口（`stock_board_change_em()` 为实时快照，不支持回测）。选择指数 OHLC 派生的两个代理指标，数据源单一稳定，能覆盖"日内多空力度"和"短期情绪惯性"两个维度。后续若 AkShare 新增历史涨跌家数接口，可替换为更精准的指标。*

### C. 量能评分 (20%)

沪深两市成交额合计，取滚动 3 年分位。

成交活跃但不过热 (分位 40%~80%) → 高分；地量 (分位 < 20%) 或过热 (分位 > 90%) → 低分。

映射函数 (梯形):
```
分位 40%-80%  → 1.0
分位 20%-40%  → 线性 0.5→1.0
分位 80%-90%  → 线性 1.0→0.4
分位 <20%      → 0.2
分位 >90%      → 0.2
```

可配置参数: `volume_lookback_years=3`

## 策略集成

### 日期契约

- `market_score_dict` 的 key 格式固定为 `YYYYMMDD` 字符串（与 `data_loader` 中 `resolve_date_range` 返回格式一致）
- Backtrader 侧日期对齐: `self.datas[0].datetime.date(0).strftime('%Y%m%d')`
- 缓存文件 `data/market_score_{YYYYMMDD}_{YYYYMMDD}.csv` 中的 date 列也存储为 `YYYYMMDD` 字符串

### 缺失值策略

Backtrader 交易日与市场评分日期一一对应。若某日不在 `market_score_dict` 中:

1. **滚动前向填充**: 用最近 5 个交易日内最后已知的评分值
2. **超窗口仍缺失**: score = 0.5（中性保守，不是 0 也不是 1.0）

这保证了短暂的数据间断不会静默关闭过滤器。

### 策略参数

`SwingStrategy` 新增可选参数:

```python
params = (
    ('fast_ma', 10),
    ('slow_ma', 20),
    ('risk_percent', 0.95),      # 新增: 基础仓位比例
    ('market_score_dict', {}),    # 新增: {date_str: score}
)
```

### 买入逻辑

```python
def _lookup_market_score(self, current_date: str) -> float:
    """查当日市场评分。key 格式 YYYYMMDD。
    前向填充最多 5 个交易日，超窗口返回 0.5。
    """
    # 先精确匹配
    if current_date in self.p.market_score_dict:
        return self.p.market_score_dict[current_date]

    # 前向填充: 往前找最近 5 个交易日内最后已知的评分
    # _last_score_date 在 next() 遍历中持续跟踪最近一次命中的日期
    if self._last_score_date:
        days_gap = self._count_trading_days(self._last_score_date, current_date)
        if days_gap <= 5:
            return self._last_known_score

    return 0.5  # 兜底中性

current_date = self.datas[0].datetime.date(0).strftime('%Y%m%d')

if buy_condition:
    score = self._lookup_market_score(current_date)
    self._last_known_score = score
    self._last_score_date = current_date
    cash_for_trade = self.broker.getcash() * self.p.risk_percent
    size = int(cash_for_trade * score / self.data.close)
    self.buy(size=size)
```

### 卖出逻辑

不变，全部清仓。卖出不受市场评分影响（卖出纪律不应因"市场好"而延迟）。

### 边界与兼容性

| 场景 | 行为 |
|------|------|
| score = 0.0 | size = 0, 跳过本次买入（但策略仍在运行，等待后续信号） |
| score = 1.0 | 全额买入（等于当天市场极度乐观） |
| market_score_dict = None (参数未传) | _lookup_market_score 短路返回 1.0，等价于无过滤 |
| market_score_dict = {} (空字典, 显式传入) | 所有查表 miss → 前向填充失败 → 0.5 兜底 |
| 回测区间内部分日期缺失 | 前向填充 (5 日窗口) → 0.5 兜底 |
| 首次买入前无任何评分数据 | 查表 miss → 无前向填充 → 0.5 |

## 数据与缓存

### 接口契约

```python
# market_analyzer.py

def get_market_score(start: str, end: str) -> pd.DataFrame:
    """
    获取市场评分 DataFrame。

    Args:
        start: 起始日期, YYYYMMDD
        end:   结束日期, YYYYMMDD

    Returns:
        含 date | trend_score | sentiment_score | volume_score | total_score 五列
        date 列为 YYYYMMDD 格式字符串
        缺失日期不填充 (由调用方处理日历对齐)
    """
```

### 具体数据源

| 维度 | AkShare 主函数 | 参数 | 字段 | 备用 | 验证状态 |
|------|---------------|------|------|------|---------|
| 上证趋势 | `stock_zh_index_daily_em(symbol='sh000001', start_date=start, end_date=end)` | start/end 为 `YYYYMMDD` | date, open, close, high, low, volume, amount | 腾讯 `stock_zh_index_daily_tx` | ✅ 已验证 |
| 上证情绪 | 同上 `stock_zh_index_daily_em('sh000001')` | 同上 | open, close, high, low (日内强度+惯性均由 OHLC 派生) | 同上 | ✅ 已验证 |
| 深证成交额 | `stock_zh_index_daily_em(symbol='sz399001', start_date=start, end_date=end)` | 同上 | amount | 同上 | ⚠️ 实现时验证 |
| 上证成交额 | 同上证趋势接口 | 同上 | amount (与深证合并为两市成交额) | — | ✅ 已验证 |

### 降级策略

**方向: fail-closed / fail-neutral，不 fail-open。** 数据异常时宁可保守少买，不静默放大仓位。

```
维度级:
  任一维度数据拉取失败 → 该维度 score = 0.5 + WARNING 日志

全局级:
  全部维度均失败 → 抛出 MarketDataError，回测停止
  (不做静默降级，因为此时数据源已整体不可用，继续运行产生的是假结果)
```

| 场景 | 行为 |
|------|------|
| 仅趋势失败 | 趋势分 = 0.5, 情绪+量能正常计算 |
| 仅情绪失败 | 情绪分 = 0.5, 趋势+量能正常计算 |
| 仅量能失败 | 量能分 = 0.5, 趋势+情绪正常计算 |
| 全部失败 | 抛出 `MarketDataError`，回测中止 |

### 缓存

```
data/
  └── market_score_{start}_{end}.csv    # date,trend_score,sentiment_score,volume_score,total_score
```

date 列为 `YYYYMMDD` 字符串。缓存无自动过期，用户可手动删除重新拉取。

## 回测验证

### 核心指标

| 指标 | 对比方式 | 判定标准 |
|------|---------|---------|
| **收益率** | 有过滤 vs 无过滤 | 不要求更高，但要求最大回撤显著降低 |
| **最大回撤** | 有过滤 vs 无过滤 | 期望降低 15%+ |
| **交易次数** | 有过滤 vs 无过滤 | 应减少 (只在高评分时出手) |
| **胜率** | 有过滤 vs 无过滤 | 期望提升 (过滤掉逆势假信号) |
| **持仓暴露 (日均仓位%)** | 有过滤 vs 无过滤 | 应与评分正相关 |
| **盈亏比** | 有过滤 vs 无过滤 | 期望提升 |

### 分段验证

必须做**样本内/样本外**分割，避免过拟合:

1. **训练期** (前 60% 数据): 用于参数敏感性分析，不作为最终结论
2. **验证期** (后 40% 数据): 评估过滤器的真实效果

### 批量验证

1. 沪深 300 TOP50 成分股批量回测，有/无过滤对比
2. 不同市场环境分段统计 (牛市/熊市/震荡各区间拆分)
3. 权重 ±10% 敏感性分析

## 设计依据

研究参考:
- 华泰证券 "再论A股择时: 多维度融合" — 多维合成框架, MA20+MA60 择时组合
- 长江证券 "情绪温度计" — 换手率/成交额滚动分位 + 阈值策略
- 平安证券 "A股市场情绪的衡量与择时策略运用" — 涨跌家数/换手率作为同步指标
- 申万宏源 "市场情绪择时模型" — 结构化情绪指标构建
