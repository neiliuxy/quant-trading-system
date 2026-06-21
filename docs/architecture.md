# QuantX 量化交易系统架构说明

> 最后更新：2026-06-21

---

## 一、系统概览

个人低频波段量化系统，针对 A 股日线数据，持仓周期 3~10 个交易日。

**技术栈**

| 层级 | 技术 |
|------|------|
| 策略引擎 | Backtrader |
| 数据层 | DataHub（统一数据门面，缓存 + AkShare 源）|
| 数据源 | AkShare（日线 OHLCV、指数、ETF、成交额）|
| 后端 | FastAPI + SQLite（WAL 模式）|
| 前端 | React + Vite + TypeScript |
| 国际化 | i18next + react-i18next（中/英双语）|
| K 线图 | lightweight-charts v4 |
| 其他图表 | Recharts |

---

## 二、目录结构

```
quant-trading-system/
├── strategies/         # 策略实现 + 注册表
├── backtest/           # 回测引擎、服务层、date helper
├── datahub/            # 数据门面：缓存/AkShare 源/刷新任务/元数据
├── market/             # 市场评分系统（趋势/情绪/量能）
├── indicators/         # 自定义 Backtrader 指标（RSRS）
├── server/             # FastAPI 后端（API、DB、任务队列）
├── web/                # React 前端
├── scripts/            # 辅助脚本
├── tests/              # pytest 测试套件
├── data/               # DataHub 缓存、SQLite、结果 JSON（gitignore）
├── logs/               # 运行日志（gitignore）
└── docs/               # 文档
```

---

## 三、核心数据流

```
用户（Web UI）
  │  POST /api/jobs
  ▼
server/api.py
  │  create_or_reuse_job()  ──── 命中缓存？→ 直接返回历史结果
  │  submit_background()
  ▼
server/executor.py（后台线程）
  ├── datahub.service.DataHub  ← 缓存命中？→ 返回；否则 AkShare → 规范化 → 写缓存
  ├── market/market_analyzer.py ← 市场评分（可选）
  ├── Backtrader Cerebro        ← 策略 + 自定义 Analyzer
  └── 输出：equity_curve / trades / price_data / drawdown
  │  mark_job_completed()
  ▼
data/results/{job_id}.json  +  SQLite job_results 表
  │  GET /api/jobs/{id}/result
  ▼
React 前端渲染图表 & KPI
```

---

## 四、策略系统

### 注册机制

新增策略三步走：

1. 继承 `bt.Strategy` 实现策略类
2. 在同模块定义 `StrategySpec`（id、名称、参数声明）
3. 在 `strategies/registry.py` 的 `_STRATEGIES` 字典中注册

Web UI 和 API 通过 `list_strategies()` / `get_strategy_spec(id)` 动态获取元数据，自动渲染参数表单，无需改前端。

### 策略参数声明

```python
# strategies/base.py
@dataclass(frozen=True)
class StrategyParamSpec:
    name: str
    label: str
    type: str        # 'int' | 'float' | 'string' | 'bool'
    default: Any

@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    description: str
    strategy_class: type
    params: list[StrategyParamSpec]
    required_data: list[str]    # 声明需要哪些额外数据 feed
```

### 已注册策略

| ID | 策略 | 类型 | 入场信号 | 离场信号 |
|----|------|------|----------|----------|
| `swing_ma_boll` | 双均线 + 布林带 | 趋势跟随 | MA10 > MA20 且价格 > 布林中轨 | MA10 < MA20 或价格 < 布林下轨 |
| `b1_strategy` | B1 趋势（三均线 + BBI）| 趋势跟随 | 7 条件联合（均线、BBI、KDJ、量能）| 追踪止损或入场低点止损 |
| `bollinger_reversal` | 布林带均值回归 | 反转 | 价格触及布林上下轨 | 均值回归至中轨 |
| `citic_wave` | 中信波浪（多过滤器）| 综合 | 4 类入场（O1 突破/O2 KDJ 抄底/O3 顶部过滤/O4 震荡反转）| ATR 追踪止损 + 最大持仓天数 |
| `sector_rotation` | 板块轮动 | 组合 | 动量评分 Top-N（均线 + 20 日收益）| 每 ~20 交易日再平衡 |

### 市场评分对仓位的影响

市场评分（0~1）通过 `market_score_dict`（日期→评分）传入策略，按比例缩放下单资金：

```python
size = int(broker.cash * risk_percent * market_score / price)
```

评分 1.0 → 满仓；评分 0.5 → 半仓；评分 0.0 → 不开仓。

---

## 五、市场评分系统

### 三维度加权

| 维度 | 权重 | 计算逻辑 |
|------|------|----------|
| 趋势 | 50% | 上证 MA20/MA60 方向，输出离散值 {0, 0.25, 0.5, 0.75, 1.0} |
| 情绪 | 30% | 日内强度（收盘-开盘）/ 振幅 + 短期上涨天比例，滚动百分位 |
| 量能 | 20% | 沪深合并成交量百分位，梯形映射（过热和过冷都降分）|

### 缓存策略

评分结果缓存为 CSV，缓存键 = SHA256(日期范围 + MarketConfig 参数)。命中缓存直接读取，否则重新计算并写入 `data/`。

---

## 六、数据加载层

`backtest/data_loader.py` 统一管理所有数据获取，逻辑如下：

1. 按 `symbol + start + end` 查找本地 CSV 缓存
2. 命中则直接读取；未命中则调用 AkShare
3. 列名标准化（中文 → 英文：日期→date、开盘→open 等）
4. 写入 CSV 缓存后返回 DataFrame

提供的数据源函数：

| 函数 | 数据内容 |
|------|----------|
| `load_market_data(symbol, start, end)` | 个股日线 OHLCV |
| `load_shanghai_composite(start, end)` | 上证指数（含成交额）|
| `load_market_turnover_data(start, end)` | 全市场成交额（SSE）|
| `load_security_etf_data(start, end)` | 证券板块 ETF |

---

## 七、回测服务层

`backtest/service.py` 是回测的核心编排层。

**主要数据结构**

```python
@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    start: str          # YYYYMMDD
    end: str
    cash: float
    use_market_filter: bool
    risk_percent: float
    strategy_id: str
    strategy_params: dict

@dataclass
class BacktestResult:
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    equity_curve: list      # [{date, value, cash}]
    trades: list            # [{entry_date, exit_date, pnl, bars_held}]
    market_scores: list     # [{date, total_score, ...}]
    price_data: list        # [{date, open, high, low, close, volume}]
    index_data: list        # 上证同期 K 线
```

**自定义 Analyzer**

| Analyzer | 收集内容 |
|----------|----------|
| `EquityCurveAnalyzer` | 每 bar 的账户市值 + 现金 |
| `TradeListAnalyzer` | 每笔已平仓交易（PnL、持仓 bar 数）|
| `PriceDataAnalyzer` | 每 bar 的 OHLCV，供前端 K 线图使用 |

---

## 八、后端服务层

### API 路由（server/api.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stocks?q=` | 股票模糊搜索（代码 + 名称）|
| GET | `/api/strategies` | 获取所有策略元数据 |
| POST | `/api/jobs` | 创建/复用回测任务 |
| GET | `/api/jobs` | 获取任务列表（最近 50 条）|
| GET | `/api/jobs/{id}` | 获取单个任务状态 |
| GET | `/api/jobs/{id}/result` | 获取回测结果 JSON |
| POST | `/api/jobs/{id}/rerun` | 强制重跑（忽略缓存）|
| POST | `/api/jobs/{id}/compare-market-filter` | 对比开/关市场过滤器的结果 |
| DELETE | `/api/jobs/{id}` | 删除单个任务 |
| DELETE | `/api/jobs` | 清空所有任务 |

### 任务缓存机制

```python
run_key = SHA256(
    symbol + start + end + cash + use_market_filter +
    strategy_id + strategy_params +
    market_config_hash[:8] +
    git_short_sha  # 代码版本
)
```

相同参数 + 相同代码版本 → 命中缓存，直接复用历史结果，不重新运行 Backtrader。`force=True` 时跳过缓存。

### 数据库（server/db.py）

SQLite，WAL 模式，外键约束开启。

**jobs 表**

```
id, run_key (UNIQUE), status
symbol, start_date, end_date, cash
use_market_filter, risk_percent
strategy_id, strategy_params_json
code_version, cache_hit, error
created_at, updated_at
索引：(run_key, status)、created_at DESC
```

**job_results 表**

```
job_id (PK, FK→jobs.id CASCADE DELETE)
final_value, total_return_pct, max_drawdown_pct
trade_count, win_rate_pct
artifact_path  → data/results/{job_id}.json
```

结果 JSON 存磁盘，`artifact_path` 作为指针。

---

## 九、前端结构

### 组件树

```
App.tsx                    # 主容器：状态管理、轮询、布局
├── RunForm.tsx            # 回测参数表单（策略选择、参数动态渲染）
│   └── StockSelect.tsx    # 股票自动补全
├── ChartDateRangeControl  # K 线时间范围滑块
├── StrategyGuide.tsx      # 策略说明文档
└── panels/
    ├── EquityPanel.tsx    # 权益曲线 + 市场评分（Recharts）
    ├── StockKlinePanel.tsx     # 个股 K 线（lightweight-charts）
    ├── StockIndicatorPanel.tsx # 个股副图（MACD/KDJ/量能）
    ├── IndexKlinePanel.tsx     # 指数 K 线（lightweight-charts）
    └── IndexIndicatorPanel.tsx # 指数副图
```

### 状态与轮询

- `App.tsx` 每 1.5 秒轮询 `GET /api/jobs/{id}`，状态变为 `completed` 或 `failed` 后停止
- 市场过滤器对比通过 `comparisonJob` 状态并行展示两条权益曲线

### 技术指标计算

`web/src/indicators.ts` 在客户端实时计算 MA、布林带、MACD、KDJ，供图表组件消费，不依赖后端下发指标数据。

---

## 十、自定义指标

`indicators/rsrs.py` — RSRS（阻力支撑相对强度）

对最近 N 根 K 线做线性回归：`high = α + β·low + ε`，返回标准化斜率 `β / std(ε)`。

| 值域 | 信号 |
|------|------|
| > 0.7 | 多头 |
| -0.7 ~ 0.7 | 中性 |
| < -0.7 | 空头 |

被 `citic_wave` 和 `sector_rotation` 策略用作市场择时过滤器。

---

## 十一、扩展指南

### 添加新策略

1. 在 `strategies/` 新建 `.py` 文件，继承 `bt.Strategy`
2. 定义模块级 `StrategySpec`，声明所有参数
3. 在 `strategies/registry.py` 的 `_STRATEGIES` 中添加条目

Web 参数表单自动生成，无需改前端代码。

### 添加新数据源

在 `backtest/data_loader.py` 添加新的 `load_*` 函数，遵循"先查 CSV 缓存，未命中则 AkShare，写缓存"模式。如果策略需要额外 feed，在 `StrategySpec.required_data` 中声明，`service.py` 会按声明自动加载。

### 添加新 API 端点

在 `server/api.py` 添加路由，通过 `server/db.py` 的 `connect()` 获取数据库连接，在 `server/models.py` 添加对应的 Pydantic 模型。

---

## 十二、配置常量

| 配置项 | 默认值 |
|--------|--------|
| 初始资金 | 100,000 CNY |
| 风险系数 | 0.95（95% 可用资金）|
| 默认策略 | swing_ma_boll |
| 默认快/慢均线 | 10 / 20 日 |
| 任务轮询间隔 | 1.5 秒 |
| 任务列表显示数 | 50 条 |
| 后端端口 | 8000 |
| 前端端口 | 5173 |
| 数据库路径 | data/quantx.sqlite |
| 结果文件路径 | data/results/{job_id}.json |
