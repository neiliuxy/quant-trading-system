# 股票初筛（Stock Screener）实施 Plan — 第一版

> 最后更新：2026-06-28
> 配套需求文档：`docs/stock-screener-plan-request.md`
> 状态：**已实现**（T1–T10 全部完成，241 测试通过）。

---

## 1. 需求理解（锁定后的第一版边界）

第一版是**选股**，不是回测：给定一个日期（默认今天）和一个股票池，用**该日期当时的真实状态**把池子筛成 TopN 候选，输出评分、排名、入选理由。

- 做：单日初筛、6 层漏斗、MVP 过滤 + MVP 评分、候选池产物、API、最小 Web 页
- 不做：历史区间「初筛+回测」对照实验（原需求 D 项）、历史 ST/历史成分数据源、分钟级、实盘下单

未来函数问题在第一版**不存在** —— 因为只为「当下」选股，用当下状态是正确的；它只在「拿今天的状态去筛历史日期」时才出现，而那件事不做。

## 2. 现有可复用模块（已核实）

| 能力 | 位置 | 复用方式 |
|---|---|---|
| 市场评分 0~1 | `market/market_analyzer.py:184` `get_market_score(start,end,config)` | 第 1 层市场门槛直接调，取 `total_score` |
| 单只日线取数 + 缓存 | `datahub/service.py:42` `DataHub.get_dataset(DatasetRequest)` | 批量取数复用，单实例循环 |
| 日期解析 | `backtest/data_loader.py:51` `resolve_date_range` | 直接用 |
| 任务范式（线程+artifact+SQLite） | `server/wfo_executor.py` + `server/jobs.py:170` `create_wfo_run` + `api.py:5725-5822` | screener 任务同构照搬 |
| 前端任务轮询 | `web/src/App.tsx` JobStatus 轮询 | 复用轮询骨架 |

**不能复用** `backtest/stock_selector.py`：它做的是「对沪深300前50只各跑一遍完整回测、按收益排名」，是「先回测后排名」，与「先漏斗筛选后交给策略」相反，且无任何 ST/上市/成交额/趋势过滤。screener 核心**全新写**。它内部直接 `import akshare` 取成分股、无缓存的逻辑，收编进 datahub。

## 3. 模块拆分

新建顶层包 `screening/`（回答特别问题 Q1）：不放 `backtest/`（它是回测，合并会重演 stock_selector 的混淆）、不放 `datahub/`（数据访问层）、不放 `market/`（市场级评分，screener 是个股级）。独立成包，与 `market/` 平级，过滤/评分逻辑与策略逻辑物理隔离。

```
screening/
  __init__.py
  config.py        # ScreenerRequest / ScreenerFilterConfig / ScreenerScoreConfig / ScreenerResult (dataclass)
  universe.py      # load_universe(mode, symbol|custom_list) -> list[code]
  indicators.py    # pandas: ma / 斜率 / 区间收益（与 backtrader SMA 口径对齐）
  filters.py       # 单条过滤函数 -> (passed: bool, reason: str)
  scoring.py       # 5 个评分维度 -> 子分，加权求和
  service.py       # run_screening(request) -> ScreenerResult（6 层漏斗编排）
  run_screener.py  # CLI 入口（可选，T10）
```

## 4. 数据模型设计（datahub 层补全 — 已确认方向）

### 4.1 修 `stock_daily` 的 amount（阻塞项，低成本）

`datahub/sources.py:66-67` 有 bug：选出 7 列（含成交额）却只赋 6 个列名 → `Length mismatch` → 静默降级到腾讯源 → amount 被丢。修复让成交额留下。

- `datahub/models.py`：新增 `STOCK_DAILY_COLUMNS = OHLCV_COLUMNS + ("amount",)`（**不动** `OHLCV_COLUMNS`，它被 etf/turnover 共用）
- `datahub/sources.py:fetch_stock_daily`：列赋值改为 7 列含 amount；tx 备用源把成交额映到 amount（现在错误地 rename 成 volume）
- `datahub/registry.py`：`stock_daily` 的 `columns` → `STOCK_DAILY_COLUMNS`
- `datahub/service.py:33`：`SCHEMA_VERSION` `"v1"→"v2"`，让无 amount 的旧缓存失效重拉（否则 `normalize_frame:24` 抛 `schema_invalid`）
- **必须验证**：`backtest/service.py:208` 用 `PandasData(dataname=df, datetime=0)`，新增 amount 尾列。backtrader 默认忽略未声明列，预期安全，但要跑回测测试确认。

### 4.2 新增 `stock_profile`（快照型，方案 A）

个股静态/状态信息，一行一只股票，`columns = (date, code, name, list_date, is_st)`，`date` = 取数日（全行同值），`symbol_required=False`，TTL 设长（如 7 天）。

- 源：`stock_zh_a_spot_em`（全市场快照，含名称→可判 ST，且复用为输出里的股票名）+ 上市日期源
- ⚠️ **Spike**：上市日期的 akshare 接口签名需先验证（`stock_individual_info_em` 单只太慢，需找全市场上市日期源）。这是唯一不确定点，若源不稳，「上市>180天」过滤可作为唯一可降级的 MVP 项。

### 4.3 新增 `index_constituents`（快照型）

`columns = (date, code, weight)`，`symbol` = 指数代码（`000300`/`000905`），源 `index_stock_cons_weight_csindex`（收编自 stock_selector）。全 A 池 = `stock_profile` 快照的全部 code。

> 快照型如何套现有「symbol+区间」模型：请求时 `start=end=筛选日`，`date` 列填该日，cache 覆盖判断 `start<=req.start and end>=req.end` 天然成立，长 TTL 避免重拉。这就是方案 A。

### 4.4 配置模型（`screening/config.py`）

```python
@dataclass ScreenerRequest:
    date: str                      # YYYYMMDD，默认今天
    universe_mode: str             # 'predefined' | 'custom' | 'full_market'
    universe_symbol: str | None    # '000300' / '000905'
    custom_list: list[str] | None
    filter_config: ScreenerFilterConfig
    score_config: ScreenerScoreConfig
    top_n: int = 30
    market_gate_mode: str = 'hard' # 'hard' | 'soft' | 'off'
    market_gate_threshold: float = 0.4

@dataclass ScreenerFilterConfig:  # 各过滤阈值，参数化
    min_listing_days=180; min_avg_turnover=1e8; turnover_window=20
    min_data_completeness=0.9; data_window=60
    require_close_gt_ma20=True; require_ma20_gt_ma60=True
    require_ma60_slope_up=True; require_outperform_index=True
    benchmark='000300'; return_window=60

@dataclass ScreenerScoreConfig:   # 5 维权重，可配
    w_relative_strength=0.3; w_trend_quality=0.25; w_drawdown=0.15
    w_vol_price=0.15; w_liquidity=0.15
```

## 5. 服务层设计（`screening/service.py:run_screening`）

6 层漏斗，顺序执行，每层记录通过/淘汰与原因：

1. **市场门槛** — `get_market_score(date,date)` 取 `total_score`；`hard` 模式低于阈值直接返回空候选；`soft` 模式作为总分加权项；`off` 跳过。（回答 Q：硬门槛 vs 加权 → 两者皆可，配置切换，默认 hard）
2. **股票池** — `universe.load_universe()` 得 codes
3. **风险/可交易性过滤** — 非 ST、上市>180天、近20日均成交额>1亿、近60日数据完整度（`filters.py`）
4. **趋势过滤** — `close>ma20`、`ma20>ma60`、`ma60` 斜率向上、近60日跑赢沪深300（`indicators.py` 算，只用 ≤date 数据）
5. **强弱评分** — 对通过 3+4 的股票算 5 维子分，加权求和（`scoring.py`）
6. **输出** — 按总分排序取 top_n，组装 `ScreenerResult` artifact

**批量取数**：复用单个 `DataHub` 实例循环 `get_dataset`（避免 stock_selector 每次 `init_db` 的开销）。沪深300（300只）可接受；全 A 标注「慢」，并发/分批列为扩展项，第一版不过度优化。

**防未来函数（第一版唯一相关的口径问题）**：所有指标请求 `end=筛选日`，ma/收益只用截止当日数据；`indicators.py` 的 ma 用「N 日 close 简单均值」与 backtrader `SMA` 口径对齐，保证筛选通过的股票若后续回测指标一致。

## 6. API 设计（`server/`，照 WFO 范式）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/screener` | 提交任务：同步校验配置→`create_screener_run` 写 SQLite→`submit_screener_background` 起线程→返回 `{id,status,...}` |
| GET | `/api/screener/{id}` | 状态：`{id,status,date,universe,total_in,total_passed,error}` |
| GET | `/api/screener/{id}/result` | 读 artifact JSON（候选全量） |

- 新文件 `server/screener_executor.py`（镜像 `wfo_executor.py`：线程跑 `run_screening`，完成写 `data/screener/<id>.json`，更新 SQLite）
- `server/jobs.py`：加 `create_screener_run` / `get_screener_run`（镜像 `create_wfo_run:170`）
- `server/db.py`：加 `screener_runs` 表 DDL（id, run_key, status, date, universe, config_json, total_in, total_passed, artifact_path, error）
- `server/models.py`：`ScreenerCreateRequest` pydantic
- 「单股入选原因」（原需求 E 第4点）：第一版由前端从 result artifact 取，不单开 endpoint（YAGNI），`/candidate/{code}` 列为扩展

**候选池存储（回答 Q2）**：SQLite 行（任务元数据）+ JSON artifact（嵌套的逐股过滤标记/子分/理由），与现有 backtest job、WFO run 完全一致。不用 SQLite-per-stock（第一版过度），不用裸缓存文件（需任务追踪）。

### artifact JSON 结构

```json
{
  "date":"20260628","universe_mode":"predefined","universe":"000300",
  "market_score":{"total":0.72,"trend":0.0,"sentiment":0.0,"volume":0.0},
  "market_gate_passed":true,"total_in_universe":300,"total_passed_filters":47,
  "filter_config":,"score_config":{},"top_n":30,
  "candidates":[{
    "code":"600519","name":"贵州茅台","universe":"000300",
    "filters":{"not_st":true,"listing_days":true,"turnover":true,"data_complete":true,
               "close_gt_ma20":true,"ma20_gt_ma60":true,"ma60_slope_up":true,"outperform_index":true},
    "scores":{"relative_strength":0.81,"trend_quality":0.76,"drawdown":0.65,"vol_price":0.70,"liquidity":0.90},
    "total_score":0.78,"rank":1,
    "reason":"近60日跑赢沪深300 12%，均线多头排列，缩量回调"
  }]
}
```

## 7. 前端最小可用方案（`web/src/`）

- `ScreenerForm.tsx`：日期 + 股票池下拉（沪深300/中证500/自定义列表）+ TopN +（可选）权重
- `ScreenerResult.tsx`：市场评分横幅 + 漏斗计数（池内/通过/候选）+ 候选表（排名、代码、名称、总分、5 维子分、入选理由）+ 每行「去回测」链接（跳现有回测页，带入 code）
- `api.ts` 加 `createScreener/getScreenerStatus/getScreenerResult`；`types.ts` 加类型；`App.tsx` 加 Tab + 轮询（复用 JobStatus 模式）

## 8. 回测集成方案（第一版仅留数据边界）

第一版**不做**回测联动代码。但候选池 artifact 是纯数据（code 列表 + 日期），天然可被消费 —— 这就是 screener 与策略的**解耦契约**（回答 Q3）：screener 永不 import 策略类，下游只拿「某日的一串 code」。后续「对候选跑回测/对照实验」是独立阶段，届时新增一个读 artifact → 批量 `run_backtest_service` 的脚本即可，不回头改 screener。

**关于「如何验证初筛真有用」（回答 Q4）**：诚实地说，第一版**无法证明** —— 因为对照实验依赖 point-in-time 历史数据，已被排除。第一版只交付「选股工具」本身；有效性验证是后续阶段（需历史 ST/历史成分）。这是已接受的取舍，明确标注，不留半成品接口。

## 9. 测试方案（`tests/`）

| 文件 | 覆盖 |
|---|---|
| `test_screening_filters.py` | 每条过滤：ST 名称、上市不足、低成交额、数据缺失、ma 关系（合成 frame） |
| `test_screening_scoring.py` | 子分单调性、权重合成 |
| `test_screening_service.py` | 漏斗端到端（mock DataHub stub 池+日线）：各层计数、排序、**无未来泄漏断言**（指标只用 ≤date） |
| `test_screener_api.py` | 提交/状态/结果（镜像 `test_wfo_executor` + `test_server_api`） |
| `test_datahub_sources.py`（扩） | stock_daily 含 amount；stock_profile / index_constituents fetch+normalize（mock akshare） |

重点防：未来函数、窗口口径不一致、停牌/缺失数据致异常 → 全部用合成数据 + mock，不打真实网络。

## 10. 风险点与决策项

- **R1 amount 改 schema**：连带缓存失效 + backtrader feed。缓解：bump SCHEMA_VERSION + 跑回测测试。低风险但必验。
- **R2 上市日期数据源**：akshare 接口待 spike。缓解：ST/名称从全市场快照便宜获取；list_date 不稳时「上市>180天」可降级。
- **R3 全 A 性能**：5000 只循环慢。缓解：第一版先沪深300/自定义，全 A 标注慢、并发列扩展。
- **决策项（已拍板）**：快照型用方案 A；第一版只单日选股，不做历史对照。
- **待确认的小项**：市场门槛默认 `hard` + 阈值 0.4 是否合适？评分默认权重（强度0.3/趋势0.25/回撤0.15/量价0.15/流动性0.15）是否认可？（可后调，不阻塞开工）

## 11 & 12. 分阶段实施步骤（Task Breakdown，按 MVP 优先级）

| # | 任务 | 文件 | MVP | 验证 |
|---|---|---|---|---|
| **T1** | 修 stock_daily amount + bump schema | `datahub/models.py,sources.py,registry.py,service.py` | ✅ | 回测测试通过 + 新拉数据有 amount |
| **T2** | stock_profile 快照（名称/ST/上市日）+ spike akshare 源 | `datahub/registry.py,sources.py,models.py` | ✅ | mock 源单测；真实拉一次校验列 |
| **T3** | index_constituents 快照 + 全A源 | `datahub/registry.py,sources.py` | ✅ | 沪深300 成分拉取非空 |
| **T4** | config + universe + indicators | `screening/config.py,universe.py,indicators.py` | ✅ | universe 各 mode 返回码；ma 口径对齐 SMA |
| **T5** | MVP 过滤 | `screening/filters.py` + `tests/test_screening_filters.py` | ✅ | 各过滤单测绿 |
| **T6** | MVP 评分 | `screening/scoring.py` + `tests/test_screening_scoring.py` | ✅ | 子分+权重单测绿 |
| **T7** | 6 层漏斗服务 + artifact | `screening/service.py` + `tests/test_screening_service.py` | ✅ | 端到端计数/排序/无泄漏断言 |
| **T8** | API：表+jobs+executor+3 端点 | `server/db.py,jobs.py,screener_executor.py,api.py,models.py` + `tests/test_screener_api.py` | ✅ | 提交→轮询→取结果链路绿 |
| **T9** | Web 最小页 | `web/src/ScreenerForm.tsx,ScreenerResult.tsx,api.ts,types.ts,App.tsx` | ✅（可薄） | 手动：填表→出候选表 |
| **T10** | CLI + 文档 | `screening/run_screener.py`,`docs/` | ⬜ 可选 | `python screening/run_screener.py` 出候选 |

依赖：T1→(T2,T3 并行)→T4→(T5,T6 并行)→T7→T8→T9。最快上线核心 = T1–T8；T9 给最小界面；T10 可后补。

## 特别问题速查

| 问题 | 结论 |
|---|---|
| 初筛模块放哪个目录 | 新建顶层 `screening/` 包，与 `market/` 平级，与策略/回测物理解耦 |
| 候选池如何存储 | SQLite 任务行 + JSON artifact，复用现有 backtest/WFO 范式 |
| 如何避免初筛与策略耦合 | screener 永不 import 策略类，只输出「某日一串 code」作为契约 |
| 如何验证初筛真有用 | 第一版无法证明（依赖 point-in-time 历史数据，已排除），属后续阶段 |
| 第一版最小范围裁到多少 | 单日选股：输入日期+股票池 → MVP 过滤+评分 → TopN 候选+理由，不做历史对照 |

---

## 实现记录

### 新增文件

| 路径 | 用途 |
|---|---|
| `screening/__init__.py` | 包标识 |
| `screening/config.py` | ScreenerRequest / ScreenerFilterConfig / ScreenerScoreConfig / ScreenerResult / CandidateResult / CandidateScore / MarketScoreSnapshot dataclass + `to_dict()` artifact 序列化 |
| `screening/universe.py` | `load_universe()` 调度 predefined / custom / full_market;`enrich_names()` 用 stock_profile 回填名称 |
| `screening/indicators.py` | `sma` / `slope_pct` / `return_pct` / `data_completeness` / `avg_amount` / `slice_to_date`,与 backtrader SMA 口径一致 |
| `screening/filters.py` | MVP 过滤:ST/上市/成交额/完整度/ma20/ma20>ma60/ma60斜率/跑赢基准;`apply_filters()` 总入口 |
| `screening/scoring.py` | 5 维评分:相对强度/趋势质量/回撤/量价/流动性;`compute_total_score()` 加权求和 |
| `screening/scoring_aggregate.py` | `aggregate_and_rank()` 排序 + 赋 rank |
| `screening/service.py` | `run_screening()` 6 层漏斗编排 + `to_dict()` |
| `screening/run_screener.py` | CLI 入口 |
| `server/screener_executor.py` | 镜像 `server/wfo_executor.py`,线程跑 `run_screening`,写 artifact,更新 SQLite |
| `tests/screening/test_filters.py` | 12 个过滤单测 |
| `tests/screening/test_scoring.py` | 10 个评分单测 |
| `tests/screening/test_service.py` | 7 个端到端测试(含无未来泄漏断言) |
| `tests/screening/test_api.py` | 6 个 API 端到端测试 |
| `web/src/ScreenerPage.tsx` | 前端最小页面(表单 + 候选表 + 评分明细) |

### 修改文件

| 路径 | 改动 |
|---|---|
| `datahub/models.py` | 新增 `STOCK_DAILY_COLUMNS` / `STOCK_PROFILE_COLUMNS` / `INDEX_CONSTITUENT_COLUMNS` |
| `datahub/registry.py` | 新增 `stock_profile` 和 `index_constituents` 两个 dataset_type 注册 |
| `datahub/sources.py` | `fetch_stock_daily` 修复 amount 列丢弃 bug(主源 7 列、备用源拆 volume/amount);新增 `fetch_stock_profile`(从 `stock_info_a_code_name` 快路径 + `stock_zh_a_spot_em` 慢备用);新增 `fetch_index_constituents`(从 `index_stock_cons_weight_csindex`) |
| `datahub/service.py` | `SCHEMA_VERSION = "v2"` 让旧缓存失效重拉 |
| `server/db.py` | 新增 `screener_runs` 表 DDL |
| `server/jobs.py` | 新增 `create_screener_run` / `get_screener_run` / `update_screener_run_status` / `mark_screener_run_completed`(镜像 WFO 命名) |
| `server/api.py` | 新增 3 个 endpoint:`POST /api/screener` / `GET /api/screener/{id}` / `GET /api/screener/{id}/result` |
| `web/src/types.ts` | 新增 `ScreenerRun` / `ScreenerCandidate` / `ScreenerResult` / `ScreenerMarketScore` 类型 |
| `web/src/api.ts` | 新增 `createScreener` / `getScreenerStatus` / `getScreenerResult` |
| `web/src/App.tsx` | 加第三个 view 'screener',侧边栏 tab 切换 |
| `web/src/i18n/locales/zh.json` / `en.json` | 新增 `nav.screener` + `screener.*` 翻译 |

### 测试结果

241/241 通过(原 206 + 新增 35)。

### 已接受的取舍

1. **amount 列**:原 `fetch_stock_daily` 有 bug(选 7 列赋 6 列名),静默降级到腾讯备用源丢失成交额。修复后 stock_daily 完整返回 7 列。
2. **list_date 降级**:akshare 无批量上市日期源,`stock_profile` 不含该字段。MVP 过滤项「上市>180天」改为用 `stock_daily` 缓存最早交易日反推(估计值,已在 docstring 注明)。详见 T2 决策记录。
3. **历史回测对照未做**:第一版只做单日选股,「对历史日期初筛+回测对照」属于依赖 point-in-time 历史数据的另一阶段(详见需求文档 D 项,Plan Q4 速查)。

### 后续阶段(超出第一版)

- 历史 ST / 历史成分数据源(用于历史对照实验)
- 全 A 池并发/分批取数(目前循环 `get_dataset`,300 只可接受,5000+ 需并发)
- 单股入选原因独立 endpoint(目前由前端从 artifact 拼)
- 行业/主题股票池扩展(架构已留 `universe_mode = predefined` 通路)
