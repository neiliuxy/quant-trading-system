# 📈 个人量化交易系统

> 低频波段策略，支持日线级操作，无需盯盘，适合上班族。

## 🎯 策略理念

- **持仓周期**：3~10 个交易日
- **核心逻辑**：双均线 + 布林带组合，判断趋势方向过滤假信号
- **操作频率**：低频，无需实时盯盘

## 🗂️ 目录结构

```
.
├── strategies/       # 策略实现
├── backtest/         # 回测框架与报告
├── data/             # 历史数据存储
├── config/            # 配置文件
├── docs/              # 策略文档
└── logs/              # 运行日志
```

## 🚀 快速开始

```bash
pip install akshare backtrader
python backtest/run_backtest.py
```

## 📌 当前策略

### 双均线 + 布林带波段策略

- **快速均线**：MA10
- **慢速均线**：MA20
- **布林带**：20日周期，2倍标准差
- **买入信号**：MA10 上穿 MA20 + 价格在布林中轨之上
- **卖出信号**：MA10 下穿 MA20 或 跌破布林下轨

详见 [docs/strategy_swing.md](docs/strategy_swing.md)
