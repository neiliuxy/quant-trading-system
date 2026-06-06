# 中信证券（600030）策略参数回测报告

## 结论
- 最佳可盈利组合：`swing_ma_boll`，市场过滤：`False`，参数：`fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=1.5, risk_percent=0.95`。
- 验证期收益 `5.34%`，最大回撤 `12.23%`，交易 `5` 笔，胜率 `20.00%`。
- 全样本收益 `32.48%`，全样本最大回撤 `27.44%`，全样本交易 `17` 笔。
- `citic_wave` 本次 54 组参数搜索中，验证期最佳组合收益 `10.51%`、全样本回撤 `16.97%`，但全样本收益只有 `11.20%`，未达到专用策略的收益目标。
- 买入持有对照：训练期 `11.72%`，验证期 `-5.10%`，全样本 `-0.23%`。

## `citic_wave` 搜索结果
- 策略：`citic_wave`
- 最优参数：`breakout_window=60, stop_loss_pct=0.05, atr_multiplier=1.5, max_hold_days=30`
- 说明：`stop_loss_pct=0.06` 与 `0.08` 的回测指标与上面组合相同，排名并列，仅按固定参数顺序落在后面。
- 全样本收益：`11.20%`
- 验证期收益：`10.51%`
- 全样本最大回撤：`16.97%`
- 是否达到目标：`否`
- 目标检查：验证期收益达标（`> 10%`），全样本最大回撤达标（`<= 20%`），但全样本收益未达标（目标 `> 20%`，实际 `11.20%`）。
- 额外说明：54 组参数中没有任何组合同时满足“全样本收益 `> 20%`、验证期收益 `> 10%`、全样本最大回撤 `<= 20%`”三项目标。全样本收益最高的组合为 `breakout_window=60, stop_loss_pct=0.05, atr_multiplier=1.5, max_hold_days=40`，全样本收益 `20.29%`、全样本最大回撤 `18.80%`，但验证期收益只有 `2.25%`。

## 与旧基线对比
- 旧基线：`swing_ma_boll`
- 旧基线全样本收益：`32.48%`
- 旧基线验证期收益：`5.34%`
- 旧基线全样本最大回撤：`27.44%`
- 对比结论：`citic_wave` 的验证期收益比旧基线高 `5.17` 个百分点，且全样本最大回撤低 `10.47` 个百分点；但全样本收益比旧基线低 `21.28` 个百分点，因此这次搜索结果不能替代 `swing_ma_boll` 作为总体最优方案。

## 回测设置
- 标的：中信证券（600030）
- 初始资金：100,000 元
- 数据区间：20210531 至 20260529，共 1205 个交易日
- 训练期：20210531 至 20241231，共 867 个交易日
- 验证期：20250101 至 20260529，共 338 个交易日
- 数据来源：项目 `data/` 缓存优先，缺失时由 AkShare 拉取
- 参数搜索：训练/验证阶段成功回测 322 组；报告中对排名靠前和各策略候选共 25 组补跑全样本指标
- 排名规则：优先验证期收益，其次验证期最大回撤，再看全样本收益

## 各策略最佳结果

| 策略 | 市场过滤 | 参数 | 训练收益 | 验证收益 | 验证回撤 | 验证交易 | 验证胜率 | 全样本收益 | 全样本回撤 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=1.5, risk_percent=0.95` | 28.61% | 5.34% | 12.23% | 5 | 20.00% | 32.48% | 27.44% |
| `b1_strategy` | False | `index_ma=120, short_ma=10, long_ma=40, j_threshold=10, vol_window=60, vol_max=1.0, amp_ratio=0.8, vol_ratio=0.8, max_pct_change=0.03, bbuphold_days=1` | 0.00% | 2.47% | 8.13% | 1 | 100.00% | 2.21% | 8.13% |
| `bollinger_reversal` | False | `boll_period=40, boll_devfactor=1.5` | 0.00% | 0.01% | 0.00% | 5 | 80.00% | 0.01% | 0.01% |

## Top 5 参数组合

| 排名 | 策略 | 市场过滤 | 参数 | 验证收益 | 验证回撤 | 验证交易 | 全样本收益 | 全样本回撤 |
|---:|---|---:|---|---:|---:|---:|---:|---:|
| 1 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=1.5, risk_percent=0.95` | 5.34% | 12.23% | 5 | 32.48% | 27.44% |
| 2 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=20, boll_devfactor=1.5, risk_percent=0.95` | 4.40% | 12.48% | 5 | 32.21% | 27.30% |
| 3 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=1.5, risk_percent=0.75` | 4.34% | 9.95% | 5 | 27.20% | 22.50% |
| 4 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=20, boll_devfactor=2.0, risk_percent=0.95` | 3.89% | 13.67% | 5 | 30.03% | 27.20% |
| 5 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=2.0, risk_percent=0.95` | 3.89% | 13.67% | 5 | 29.24% | 28.98% |

## 解释与风险
- 本报告按验证期收益选参，不按全样本最高收益选参，以降低参数搜索过拟合。
- `bollinger_reversal` 源码中 `buy()` 未指定仓位，Backtrader 默认只买 1 股，因此收益接近 0；这是当前策略实现限制。
- B1 策略源码要求上证指数作为第二数据源，本次搜索已加入指数数据；当前 `backtest.service` 没有把指数 feed 加入 Cerebro，直接用服务层跑 B1 会偏离策略设计。
- 回测未计入手续费、滑点、涨跌停无法成交等约束，结论只代表历史数据上的策略表现。
- 如果策略收益低于买入持有，说明策略可能降低仓位或波动，但不一定提高收益。

## 输出文件
- 精简全样本排名：`data/results/citic_securities_strategy_search_results.csv`
- 全部训练/验证结果：`data/results/citic_securities_strategy_search_all_train_valid.csv`
- `citic_wave` 参数搜索明细：`data/results/citic_wave_search.txt`
