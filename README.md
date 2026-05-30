# 个人量化交易系统

低频波段策略，基于 Backtrader 框架，使用 AkShare 获取 A 股日线数据。
持仓周期 3~10 个交易日，无需实时盯盘。

## 目录结构

```
.
├── strategies/       # 策略实现
├── backtest/         # 回测框架、数据加载、运行入口
├── market/           # 市场评分系统（趋势/情绪/量能）
├── tests/            # 测试
├── data/             # 历史数据缓存
├── docs/             # 策略文档
└── logs/             # 运行日志
```

## 快速开始

```bash
pip install akshare backtrader pandas numpy
python backtest/run_backtest.py
```

支持 CLI 参数：

```bash
python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000 --no-market-filter
```

## 策略

### SwingStrategy — 双均线 + 布林带

- **买入**：MA10 上穿 MA20 + 价格在布林中轨之上
- **卖出**：MA10 下穿 MA20 或 跌破布林下轨
- **参数**：`risk_percent`（默认 0.95）、`market_score_dict`（可选外部市场评分）

详见 [docs/strategy_swing.md](docs/strategy_swing.md)。

### 市场过滤器（可选）

回测时可通过 `--no-market-filter` 禁用的三层评分模块：

- **趋势 (A)** — 上证指数 MA60 方向 + 多空分层（0/0.25/0.5/0.75/1.0）
- **情绪 (B)** — 日内强度 + 短期涨跌惯性的滚动分位等权合成
- **量能 (C)** — 两市成交额的滚动分位梯形映射

## 测试

```bash
python -m pytest -q tests/
```
