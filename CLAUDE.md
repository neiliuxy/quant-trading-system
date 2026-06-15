# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

个人量化交易系统 — 低频波段策略，基于 Backtrader 框架，使用 AkShare 获取 A 股日线数据。
持仓周期 3~10 个交易日，无需实时盯盘。
支持多策略注册表架构、可选市场评分过滤器、FastAPI + React 的 Web 分析台。

## Commands

```bash
# 安装依赖
pip install -r requirements.txt

# 运行 CLI 回测（平安银行 000001，2020-2023）
python backtest/run_backtest.py

# 参数化 CLI 回测
python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000

# 运行全部测试
python -m pytest -q tests/

# 启动 Web 后端（端口 8000）
python server/main.py

# 启动 Web 前端（新终端，端口 5173）
cd web && npm run dev
```

无构建步骤。使用 `.venv/` 虚拟环境（已 gitignore）。

## Architecture

### 数据流

AkShare API → DataFrame 标准化 → Backtrader PandasData feed → Cerebro 引擎 → 策略执行 → 收益报告

### 目录结构

```
strategies/     # 策略实现。多策略注册表架构，通过 registry.py 动态加载
  base.py         — StrategySpec / StrategyParamSpec 数据类
  swing_ma_boll.py      — SwingStrategy（双均线+布林带）
  bollinger_reversal.py — BollingerReversalStrategy（布林带均值回归）
  b1_strategy.py        — B1Strategy（三均线+ADX+RSI 综合策略）
  registry.py           — 策略注册表，统一管理所有策略

backtest/       # 回测入口。负责任务执行、数据加载、CLI 参数解析
  run_backtest.py   — CLI 入口
  data_loader.py    — 数据获取及合成数据降级
  service.py        — 回测服务（供 server 调用）
  stock_selector.py — 选股逻辑

market/         # 市场评分系统（趋势/情绪/量能三层评分，可选过滤器）

server/         # FastAPI Web 后端
  main.py   — 入口
  api.py    — REST API（策略列表、回测提交、结果查询）
  db.py     — SQLite 数据库
  executor.py — 回测任务异步执行
  jobs.py   — 定期任务
  models.py — Pydantic 模型

web/            # React + Vite 前端（策略选择、参数配置、结果展示）

tests/          # 自动化测试（pytest）
scripts/        # 辅助脚本
data/           # 缓存数据（CSV、SQLite），已 gitignore
logs/           # 运行日志，已 gitignore
docs/           # 文档
```

### 策略系统

每个策略通过 `StrategySpec` 声明参数和实现类，通过 `registry.py` 注册表统一管理。
Web UI 和 API 通过注册表动态获取策略元数据、渲染参数表单。
新增策略只需三步：写策略类 → 定义 `StrategySpec` → 在 `registry.py` 注册。

### Web 分析台

- 后端：FastAPI（`server/main.py`），端口 8000
- 前端：React/Vite（`web/`），端口 5173
- 数据库：SQLite（`data/quantx.sqlite`），保存回测任务和结果
- 功能：策略选择、参数配置、任务历史、收益曲线、交易列表、市场评分
- K 线由 `lightweight-charts` v4 渲染（`web/src/charts/useKlineChart.ts`）；副图与权益曲线仍用 Recharts。详见 `docs/kline-chart-refactor.md`。

## Conventions

- Python 3，4 空格缩进
- 函数/变量 `snake_case`，策略类 `PascalCase`
- Conventional Commits：`feat:`, `fix:`, `refactor:` 等
- 生成数据放 `data/`，日志放 `logs/`，均已 gitignore
- 不提交 API 密钥、券商凭证、下载的数据集
- 依赖统一管理在 `requirements.txt`

## Testing

使用 pytest，测试文件位于 `tests/`，命名 `test_*.py`。
现有测试覆盖：策略信号生成、市场评分指标、回测服务、API 接口、集成测试。
运行全部测试：`python -m pytest -q tests/`
