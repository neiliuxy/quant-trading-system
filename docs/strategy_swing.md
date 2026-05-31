# SwingStrategy — 双均线 + 布林带波段策略

## 概述

趋势跟踪型波段策略，使用双均线交叉作为主信号，布林带作为确认和止损参考。
持仓周期通常 3~10 个交易日，适用于 A 股日线级别交易。

## 信号规则

### 买入条件

- **MA10 上穿 MA20**（金叉）
- **收盘价在布林中轨之上**（确认上升趋势）

同时满足时，根据市场评分调整仓位比例（如果启用了市场过滤器）。

### 卖出条件

满足以下任一条件即卖出：
- **MA10 下穿 MA20**（死叉）
- **收盘价跌破布林下轨**（趋势转弱或超买回落）

## 参数

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `fast_ma` | int | 10 | 快速均线周期 |
| `slow_ma` | int | 20 | 慢速均线周期 |
| `boll_period` | int | 20 | 布林带计算周期 |
| `boll_devfactor` | float | 2.0 | 布林带标准差倍数 |
| `risk_percent` | float | 0.95 | 单笔交易资金比例 |

## 实现

策略类 `SwingStrategy` 继承自 `bt.Strategy`，使用 Backtrader 内置指标：

```python
self.ma_fast = bt.ind.SMA(period=self.p.fast_ma)
self.ma_slow = bt.ind.SMA(period=self.p.slow_ma)
self.boll = bt.ind.BollingerBands(period=self.p.boll_period, devfactor=self.p.boll_devfactor)
```

代码位置：`strategies/swing_ma_boll.py`

## 注册方式

通过策略注册表（`strategies/registry.py`）以 `StrategySpec` 格式注册：

```python
SWING_MA_BOLL_SPEC = StrategySpec(
    id='swing_ma_boll',
    name='Swing MA + Bollinger',
    description='Trend-following moving-average strategy with Bollinger confirmation.',
    strategy_class=SwingStrategy,
    params=(...),
)
```

在前端策略下拉菜单中显示为 "Swing MA + Bollinger"。
