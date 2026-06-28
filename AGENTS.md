# AGENTS.md
quant-trading-system 是一个面向 A 股日线的低频量化回测系统，核心能力包括：策略注册与回测、市场过滤评分、DataHub 数据缓存、FastAPI 后端任务系统、
React/Vite Web 分析台、Walk-forward Optimization。

## 目录结构
  quant-trading-system/
  ├── strategies/      # 策略实现与注册表
  ├── backtest/        # 回测编排、CLI 入口、指标/成本/Walk-forward
  ├── datahub/         # 统一数据门面：数据源、缓存、刷新任务、元数据
  ├── market/          # 市场评分系统：趋势、情绪、量能
  ├── indicators/      # 自定义 Backtrader 指标，如 RSRS
  ├── server/          # FastAPI 后端：API、SQLite、任务队列、执行器
  ├── web/             # React + Vite + TypeScript 前端
  ├── scripts/         # 辅助脚本、诊断脚本、策略搜索脚本
  ├── tests/           # Python pytest 测试
  ├── docs/            # 架构、策略、设计与执行计划文档
  ├── data/            # 本地缓存、SQLite、回测结果，通常不提交
  └── logs/            # 运行日志，通常不提交

## 核心模块

  strategies/ 是策略层。每个策略通过 StrategySpec 声明策略 ID、名称、参数、策略类和所需额外数据。注册入口是 strategies/registry.py:1，当前包含
  b1_strategy、swing_ma_boll、bollinger_reversal、citic_wave、sector_rotation。

  backtest/ 是回测服务层。CLI 入口在 backtest/run_backtest.py:1，Web/API 使用的编排入口在 backtest/service.py:1。它负责加载数据、解析策略、运行
  Backtrader、收集权益曲线/交易/价格序列/市场评分结果。

  datahub/ 是数据访问层。核心类 DataHub 在 datahub/service.py:1，负责根据数据请求读取缓存或调用数据源，并维护刷新任务与缓存元数据。

  server/ 是后端服务层。应用入口是 server/main.py:1，主要 API 在 server/api.py:1。后端提供策略列表、股票搜索、回测任务、结果查询、市场过滤对比、
  WFO、DataHub 缓存管理等接口。任务和结果元数据通过 SQLite 管理，任务逻辑在 server/jobs.py:1。

  web/ 是前端分析台。主容器是 web/src/App.tsx:1，API 封装在 web/src/api.ts:1。前端负责回测表单、策略参数动态渲染、任务轮询、K 线图、权益曲线、市场评
  分、WFO 结果和数据管理页面。

## 主数据流

  Web UI / CLI
    ↓
  选择股票、时间区间、策略和参数
    ↓
  server/api.py 或 backtest/run_backtest.py
    ↓
  BacktestRequest
    ↓
  backtest/service.py
    ↓
  DataHub 加载行情与策略额外 feed
    ↓
  可选 market analyzer 生成市场评分
    ↓
  Backtrader Cerebro 执行策略
    ↓
  Analyzer 收集权益曲线、交易、价格数据
    ↓
  结果写入 data/results/*.json
    ↓
  SQLite 记录任务状态与摘要
    ↓
  前端轮询任务并展示结果

## 注意
- 总是用codegraph查看代码仓库

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

  技术栈

  Python: Backtrader, pandas, numpy, AkShare, FastAPI, Pydantic, SQLite
  Frontend: React, Vite, TypeScript, i18next, lightweight-charts, Recharts
  Testing: pytest, Vitest, Testing Library, Playwright

## 扩展方式

  新增策略通常只需要三步：在 strategies/ 新增策略类，定义 StrategySpec，再注册到 strategies/registry.py。后端 /api/strategies 会自动暴露策略元数据，
  前端策略参数表单也会按 StrategySpec.params 动态生成。

  新增数据源应优先接入 datahub/，通过标准化、缓存和元数据记录统一管理。策略如果需要额外数据 feed，应在 StrategySpec.required_data 中声明，由回测服务
  统一加载。

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