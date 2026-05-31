# 个人量化交易系统

低频波段策略，基于 Backtrader 框架，使用 AkShare 获取 A 股日线数据。
持仓周期 3~10 个交易日，无需实时盯盘。

## 目录结构

```
.
├── strategies/       # 策略实现（多策略注册表架构）
├── backtest/         # 回测框架、数据加载、运行入口
├── market/           # 市场评分系统（趋势/情绪/量能）
├── server/           # FastAPI Web 后端
├── web/              # React + Vite 前端
├── scripts/          # 辅助脚本
├── tests/            # 测试
├── data/             # 历史数据缓存
├── docs/             # 策略文档
└── logs/             # 运行日志
```

## 快速开始

```bash
pip install -r requirements.txt
python backtest/run_backtest.py
```

支持 CLI 参数：

```bash
python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000 --no-market-filter
```

## 策略

系统支持多策略架构，通过策略注册表动态加载。每个策略声明自己的参数，Web UI 根据选中策略动态渲染参数表单。

### SwingStrategy — 双均线 + 布林带

- **买入**：MA10 上穿 MA20 + 价格在布林中轨之上
- **卖出**：MA10 下穿 MA20 或 跌破布林下轨
- **参数**：`fast_ma`（默认 10）、`slow_ma`（默认 20）、`boll_period`（默认 20）、`boll_devfactor`（默认 2.0）

详见 [docs/strategy_swing.md](docs/strategy_swing.md)。

### BollingerReversalStrategy — 布林带均值回归

- **买入**：价格跌破布林下轨后回升
- **卖出**：价格回到布林中轨或上轨
- **参数**：`boll_period`（默认 20）、`boll_devfactor`（默认 2.0）

新增策略，用于测试多策略架构。

### 市场过滤器（可选）

回测时可通过 `--no-market-filter` 禁用的三层评分模块：

- **趋势 (A)** — 上证指数 MA60 方向 + 多空分层（0/0.25/0.5/0.75/1.0）
- **情绪 (B)** — 日内强度 + 短期涨跌惯性的滚动分位等权合成
- **量能 (C)** — 两市成交额的滚动分位梯形映射

## Web 分析台

本地开发见 [docs/web-dashboard.md](docs/web-dashboard.md)。

后端使用 FastAPI，前端使用 React/Vite，历史任务和摘要结果保存在 SQLite 中。

### 功能

- **策略选择**：Web UI 提供策略下拉菜单，支持动态参数表单
- **参数配置**：根据选中策略自动渲染对应参数输入框
- **任务历史**：保存所有回测任务，支持重新运行
- **结果展示**：收益曲线、交易列表、市场评分等详细分析

### 启动

```bash
# 后端
python server/main.py

# 前端（新终端）
cd web && npm run dev
```

访问 http://localhost:5173

## 测试

```bash
python -m pytest -q tests/
```

## 架构

### 策略系统

每个策略通过 `StrategySpec` 声明自己的参数和实现类：

```python
SWING_MA_BOLL_SPEC = StrategySpec(
    id='swing_ma_boll',
    name='Swing MA + Bollinger',
    strategy_class=SwingStrategy,
    params=(
        StrategyParamSpec('fast_ma', 'Fast MA', 'int', 10),
        StrategyParamSpec('slow_ma', 'Slow MA', 'int', 20),
        ...
    ),
)
```

策略注册表 (`strategies/registry.py`) 管理所有可用策略，API 和 Web UI 通过注册表获取策略元数据。

### 数据流

1. Web UI 选择策略和参数 → 
2. FastAPI 接收 `strategy_id` 和 `strategy_params` → 
3. 后端通过注册表解析策略 → 
4. 回测服务执行策略 → 
5. 结果保存到 SQLite 并返回给前端

### 缓存键

回测结果缓存键包含 `strategy_id` 和 `strategy_params`，确保不同策略配置产生独立的缓存。
