# 中信证券（600030）策略回测报告

## 结论
- 这份报告分成两部分：一部分是既有多策略历史基线，另一部分是本次针对 `600030` 新增的 `citic_wave` 专用参数搜索。两者不是同一轮联合排名。
- 历史基线中，`swing_ma_boll` 仍然是全样本历史结果最强的方案：全样本收益 `32.48%`，验证期收益 `5.34%`，全样本最大回撤 `27.44%`。
- 本次 `citic_wave` 搜索的最佳组合为 `breakout_window=60, stop_loss_pct=0.05, atr_multiplier=1.5, max_hold_days=30`，验证期收益 `10.51%`，全样本收益 `11.20%`，全样本最大回撤 `16.97%`。
- 相比旧基线，`citic_wave` 在验证期收益和回撤控制上更好，但没有达到专用策略的全样本收益目标，也没有取代 `swing_ma_boll` 作为整体历史表现最佳结果。

## `citic_wave` 专用搜索结果
- 策略：`citic_wave`
- 搜索区间：全样本 `20210531` 至 `20260529`；训练期 `20210531` 至 `20241231`；验证期 `20250101` 至 `20260529`
- 搜索网格：
  - `breakout_window` in `[40, 60]`
  - `stop_loss_pct` in `[0.05, 0.06, 0.08]`
  - `atr_multiplier` in `[1.5, 2.0, 2.5]`
  - `max_hold_days` in `[20, 30, 40]`
- 排名规则：验证期收益降序，验证期最大回撤升序，全样本收益降序，全样本最大回撤升序
- 最优参数：`breakout_window=60, stop_loss_pct=0.05, atr_multiplier=1.5, max_hold_days=30`
- 并列说明：`stop_loss_pct=0.06` 与 `0.08` 在本次搜索中的回测指标与上面组合相同，仅因固定参数排序落在其后
- 全样本收益：`11.20%`
- 验证期收益：`10.51%`
- 全样本最大回撤：`16.97%`
- 是否达到目标：`否`
- 目标检查：
  - 验证期收益目标 `> 10%`：达到，实际 `10.51%`
  - 全样本最大回撤目标 `<= 20%`：达到，实际 `16.97%`
  - 全样本收益目标 `> 20%`：未达到，实际 `11.20%`
- 额外说明：本次 54 组参数中，没有任何组合同时满足“全样本收益 `> 20%`、验证期收益 `> 10%`、全样本最大回撤 `<= 20%`”三项约束
- 全样本收益最高的组合：`breakout_window=60, stop_loss_pct=0.05, atr_multiplier=1.5, max_hold_days=40`
  - 全样本收益：`20.29%`
  - 全样本最大回撤：`18.80%`
  - 验证期收益：`2.25%`

## 与旧基线对比
- 旧基线：`swing_ma_boll`
- 旧基线全样本收益：`32.48%`
- 旧基线验证期收益：`5.34%`
- 旧基线全样本最大回撤：`27.44%`
- `citic_wave` 对比结果：
  - 验证期收益高 `5.17` 个百分点（`10.51%` vs `5.34%`）
  - 全样本最大回撤低 `10.47` 个百分点（`16.97%` vs `27.44%`）
  - 全样本收益低 `21.28` 个百分点（`11.20%` vs `32.48%`）
- 结论：`citic_wave` 在独立验证窗口和回撤控制上优于旧基线，但由于全样本收益明显更低，当前不能替代 `swing_ma_boll` 作为整体最佳历史结果

## 回测设置
- 标的：中信证券（600030）
- 初始资金：100,000 元
- 数据区间：`20210531` 至 `20260529`，共 1205 个交易日
- 训练期：`20210531` 至 `20241231`，共 867 个交易日
- 验证期：`20250101` 至 `20260529`，共 338 个交易日
- 数据来源：项目 `data/` 缓存优先，缺失时由 AkShare 拉取
- 本次 `citic_wave` 搜索输出：`data/results/citic_wave_search.txt`

## 历史基线策略结果（旧搜索上下文）
- 下表来自此前的多策略基线搜索，用来提供历史参照，不代表与 `citic_wave` 同一轮联合排序

| 策略 | 市场过滤 | 参数 | 训练收益 | 验证收益 | 验证回撤 | 验证交易 | 验证胜率 | 全样本收益 | 全样本回撤 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=1.5, risk_percent=0.95` | 28.61% | 5.34% | 12.23% | 5 | 20.00% | 32.48% | 27.44% |
| `b1_strategy` | False | `index_ma=120, short_ma=10, long_ma=40, j_threshold=10, vol_window=60, vol_max=1.0, amp_ratio=0.8, vol_ratio=0.8, max_pct_change=0.03, bbuphold_days=1` | 0.00% | 2.47% | 8.13% | 1 | 100.00% | 2.21% | 8.13% |
| `bollinger_reversal` | False | `boll_period=40, boll_devfactor=1.5` | 0.00% | 0.01% | 0.00% | 5 | 80.00% | 0.01% | 0.01% |

## 历史基线 Top 5 组合（旧搜索上下文）
- 下表同样来自旧的多策略基线搜索，仅用于说明当时的历史排名结果

| 排名 | 策略 | 市场过滤 | 参数 | 验证收益 | 验证回撤 | 验证交易 | 全样本收益 | 全样本回撤 |
|---:|---|---:|---|---:|---:|---:|---:|---:|
| 1 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=1.5, risk_percent=0.95` | 5.34% | 12.23% | 5 | 32.48% | 27.44% |
| 2 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=20, boll_devfactor=1.5, risk_percent=0.95` | 4.40% | 12.48% | 5 | 32.21% | 27.30% |
| 3 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=1.5, risk_percent=0.75` | 4.34% | 9.95% | 5 | 27.20% | 22.50% |
| 4 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=20, boll_devfactor=2.0, risk_percent=0.95` | 3.89% | 13.67% | 5 | 30.03% | 27.20% |
| 5 | `swing_ma_boll` | False | `fast_ma=10, slow_ma=40, boll_period=30, boll_devfactor=2.0, risk_percent=0.95` | 3.89% | 13.67% | 5 | 29.24% | 28.98% |

## 解释与风险
- 本次 `citic_wave` 搜索按验证期收益优先选参，不按全样本最高收益选参，以降低参数搜索过拟合
- `bollinger_reversal` 源码中 `buy()` 未指定仓位，Backtrader 默认只买 1 股，因此收益接近 0；这是当前策略实现限制
- B1 结果保留为历史基线参考，服务层当前已支持按策略必需辅助数据源加载回测
- 回测未计入手续费、滑点、涨跌停无法成交等约束，结论只代表历史数据上的策略表现
- 如果策略收益低于买入持有，说明策略可能降低仓位或波动，但不一定提高收益

## 输出文件
- 精简全样本排名：`data/results/citic_securities_strategy_search_results.csv`
- 全部训练/验证结果：`data/results/citic_securities_strategy_search_all_train_valid.csv`
- `citic_wave` 参数搜索明细：`data/results/citic_wave_search.txt`
