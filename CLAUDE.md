# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

个人量化交易系统 — 低频波段策略，基于 Backtrader 框架，使用 AkShare 获取 A 股日线数据。持仓周期 3~10 个交易日，无需实时盯盘。

## Commands

```bash
# 安装依赖
pip install akshare backtrader pandas numpy

# 运行默认回测（平安银行 000001，2020-2023）
python backtest/run_backtest.py

# 参数化回测
python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000
```

无构建步骤。使用 `.venv/` 虚拟环境（已 gitignore）。

## Architecture

**数据流：** AkShare API → DataFrame 标准化 → Backtrader PandasData feed → Cerebro 引擎 → 策略执行 → 收益报告

- `strategies/` — 策略实现。策略类继承 `bt.Strategy`，参数用 Backtrader `params` 元组定义。
- `backtest/` — 回测入口。负责数据获取、网络失败时降级为合成数据、CLI 参数解析。

当前唯一策略：`SwingStrategy`（双均线 MA10/MA20 + 布林带 20 日 2 倍标准差）。

## Conventions

- Python 3，4 空格缩进
- 函数/变量 `snake_case`，策略类 `PascalCase`
- Conventional Commits：`feat:`, `fix:`, `refactor:` 等
- 生成数据放 `data/`，日志放 `logs/`，均已 gitignore
- 不提交 API 密钥、券商凭证、下载的数据集

## Testing

尚无自动化测试。验证方式：运行 `python backtest/run_backtest.py` 确认正常完成（真实数据或合成数据降级）。添加测试时使用 pytest，放在 `tests/` 目录，文件命名 `test_*.py`。
