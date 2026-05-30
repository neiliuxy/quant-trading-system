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
| A 趋势 | 50% | MA20 + MA60 多状态判断 | 上证指数日线 (sh000001) | 5 档离散: 0 / 0.25 / 0.5 / 0.75 / 1.0 |
| B 情绪 | 30% | ① 涨跌家数比 ② 全A换手率 | AkShare 涨跌家数 + 换手率 | 滚动 3 年分位 → 0~1, 等权合成 |
| C 量能 | 20% | 两市成交额 | 上证+深证日线成交额合计 | 滚动 3 年分位 → 0~1 |

合成: `score = A × 0.5 + B × 0.3 + C × 0.2`, 范围 0~1

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

两个子指标等权合成:

1. **涨跌家数比**: 上涨家数 / (上涨 + 下跌家数)，取滚动 3 年分位映射到 0~1
2. **全A换手率**: 全A成交额 / 全A流通市值，取滚动 3 年分位映射到 0~1

分位计算: 当前值在过去 N 年中处于什么位置 (0% = 最低, 100% = 最高), 直接作为 0~1 分数

可配置参数: `sentiment_lookback_years=3`

### C. 量能评分 (20%)

沪深两市成交额合计，取滚动 3 年分位映射到 0~1。

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

`SwingStrategy` 新增可选参数:

```python
params = (
    ('fast_ma', 10),
    ('slow_ma', 20),
    ('risk_percent', 0.95),      # 新增: 基础仓位比例
    ('market_score_dict', {}),    # 新增: {date_str: score}
)
```

买入逻辑:

```python
if buy_condition:
    score = self.p.market_score_dict.get(current_date, 1.0)
    cash_for_trade = self.broker.getcash() * self.p.risk_percent
    size = int(cash_for_trade * score / self.data.close)
    self.buy(size=size)
```

卖出逻辑: 不变, 全部清仓。

默认 score=1.0 保证无市场数据时策略正常工作。

## 数据与缓存

`market_analyzer.py` 核心接口:

```python
def get_market_score(start, end) -> pd.DataFrame:
    """返回 date | trend_score | sentiment_score | volume_score | total_score"""
```

输出同时缓存到 `data/market_score_{YYYYMMDD}_{YYYYMMDD}.csv`, 复用现有 `data_loader` 的缓存模式。

### 数据源与降级

| 维度 | AkShare 主源 | 备用 | 失败兜底 |
|------|-------------|------|---------|
| 上证趋势 | `stock_zh_index_daily("sh000001")` | 东方财富 | score = 0.5 |
| 市场情绪 | 涨跌家数 + 换手率 (同上接口) | 乐咕乐股 | score = 0.5 |
| 两市成交额 | 上证+深证日线 | — | score = 0.5 |

任一维度失败 → 该维度降级为中性 0.5，不阻塞回测。全部失败 → 所有分 = 1.0 (等于退回原始策略无过滤)。

## 回测验证

实现后验证:

1. 单股回测对比: 有无市场过滤器的收益率/最大回撤差异
2. 批量选股对比: 沪深300 TOP50 有/无过滤的排名稳定性
3. 参数敏感性: 权重偏离 ±10% 对结果的影响

## 设计依据

研究参考:
- 华泰证券 "再论A股择时: 多维度融合" — 多维合成框架, MA20+MA60 择时组合
- 长江证券 "情绪温度计" — 换手率/成交额滚动分位 + 阈值策略
- 平安证券 "A股市场情绪的衡量与择时策略运用" — 涨跌家数/换手率作为同步指标
- 申万宏源 "市场情绪择时模型" — 结构化情绪指标构建
