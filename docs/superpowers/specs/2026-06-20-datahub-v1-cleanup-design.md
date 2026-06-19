# DataHub v1 收尾清理设计

## Goal

DataHub v1 已落地并测试全绿（154 passed）。本设计收尾 v1：清除 `backtest/data_loader.py`
在迁移过程中留下的死代码与重复逻辑，让成交额/重试容错代码只剩 `datahub/sources.py` 一个
真相源，并修复"容错测试指向非活跃副本"的覆盖缺口。

这是一次纯删除 + 测试迁移，不改变任何数据路径的运行时行为。

## Background

迁移把 `backtest/data_loader.py` 的公开 `load_*` 函数改成了 DataHub 薄包装，但旧的函数体
和内部辅助函数没有删除，导致：

- 3 个 `load_*` 函数被新包装覆盖（Python 后定义胜出），旧函数体成为死代码。
- 成交额容错逻辑（`_retry_akshare` / `_is_empty_data_error` / `_fetch_sse_turnover` /
  `_fetch_szse_turnover`）在 `data_loader.py` 与 `datahub/sources.py` 各有一份；运行时只走
  `datahub/sources.py`，`data_loader.py` 那份仅靠测试吊命。
- `test_data_loader_strategy_feeds.py` 里的重试/空数据测试 monkeypatch 的是
  `data_loader.py` 的非活跃副本，等于容错逻辑的测试测错了对象。
- 一批只在旧函数里使用的辅助（`_get_stock_name` / `_sanitize_filename_part` /
  `_parse_filename` / `_CACHE_DIR` / `_AKSHARE_COLUMN_MAP` / `_read_cached_frame`）已无运行时
  调用方。

已核实：`datahub/sources.py` 的活跃副本完整保留了 SSE/SZSE 成交额容错（空数据返回 None
跳过该日、SSL/网络错误重试 3 次、空数据错误立即跳过不重试、全空才报 `empty_data`），
`test_datahub_sources.py::test_market_turnover_skips_days_with_missing_turnover` 已覆盖跳过
行为。因此不存在行为回归，本设计只清理债务。

## Scope

In scope:

- 从 `backtest/data_loader.py` 删除死代码与重复辅助，清理无用 import，更新模块 docstring。
- 把指向死副本的容错测试迁移到 `tests/test_datahub_sources.py`，指向活跃副本。
- 删除等价覆盖已存在的冗余测试。
- 全量测试保持绿色。

Out of scope:

- 跨进程文件锁（见 Non-goals）。
- 录制型 golden 兼容测试（见 Non-goals）。
- 修改 `datahub/` 包、`server/`、`backtest/service.py`、`backtest/run_backtest.py` 的任何
  逻辑。本设计只碰 `backtest/data_loader.py` 与测试文件。
- 改变任何数据路径的运行时行为。

## Deletions From `backtest/data_loader.py`

删除以下死代码（运行时无人调用，已通过 grep 核实）：

- 3 个被新包装覆盖的旧函数体：`load_shanghai_composite`（约 145 行）、
  `load_security_etf_data`（约 223 行）、`load_market_turnover_data`（约 308 行）。
- 无运行时调用、无测试引用的辅助：`_get_stock_name`、`_sanitize_filename_part`、
  `_parse_filename`、`_CACHE_DIR`。
- 与 `datahub/sources.py` 重复、仅靠测试吊命的辅助：`_retry_akshare`、
  `_is_empty_data_error`、`_fetch_sse_turnover`、`_fetch_szse_turnover`、`_read_cached_frame`、
  `_AKSHARE_COLUMN_MAP`。

清理因此变为无用的 import：`akshare as ak`、`glob`、`time`。保留 `os`、`re`、`pandas`、
`datetime`（date helper 仍使用）。

更新模块 docstring：现版本声称"旧的内部辅助保留以供既有测试与 CLI 兼容性使用"，迁移
完成后已不成立，改为准确描述文件职责（date helper + DataHub 薄包装）。

## What Stays In `backtest/data_loader.py`

- date helper：`_format_date`、`_shift_years`、`get_default_date_range`、
  `resolve_date_range`（被 `backtest/service.py`、`backtest/stock_selector.py`、
  `backtest/run_backtest.py`、scripts、`tests/test_integration.py` 复用）。
- 列常量：`STANDARD_COLUMNS`、`INDEX_STANDARD_COLUMNS`（保留的 wrapper 测试断言它们；
  公开 API 也在引用 `INDEX_STANDARD_COLUMNS`）。
- `_make_datahub`。
- 4 个薄包装：`load_market_data`、`load_shanghai_composite`、`load_security_etf_data`、
  `load_market_turnover_data`（名字与签名不变，`stock_selector` / scripts / CLI 继续可用）。
- `load_data`。

## Test Relocation

### `tests/test_data_loader_strategy_feeds.py` → `tests/test_datahub_sources.py`

迁移并 retarget 到 `datahub.sources` 活跃副本：

- `test_fetch_sse_turnover_returns_none_on_empty_akshare_data` —— monkeypatch
  `datahub.sources.ak.stock_sse_deal_daily` 抛 Length mismatch，断言
  `datahub.sources._fetch_sse_turnover(...)` 返回 None。
- `test_empty_data_error_does_not_retry` —— 断言空数据错误下
  `stock_sse_deal_daily` 只被调用一次（不重试）。
- `test_network_error_does_retry` —— monkeypatch `datahub.sources.time.sleep`，断言
  SSL/连接错误重试满 3 次。

删除（等价覆盖已存在于 `tests/test_datahub_cache.py`）：

- `test_read_cached_frame_accepts_equivalent_columns_and_reorders` —— 缓存读取 + 列重排
  已由 `test_datahub_cache.py::test_reads_legacy_cache_and_trims_to_requested_range` 覆盖。

保留（测活跃 wrapper，走 `_LoaderFakeHub`）：

- `test_load_security_etf_data_normalizes_index_columns`
- `test_load_market_turnover_data_returns_price_like_frame`
- `test_load_market_turnover_data_uses_trading_dates_only`
- `test_load_market_turnover_skips_days_with_missing_data`
- `test_load_market_data_wrapper_matches_datahub_result`
- `_LoaderFakeHub` helper（被上述保留测试使用）

### `tests/test_data_loader_index.py`

- `test_akshare_amount_mapping_exists` —— 迁到 `tests/test_datahub_sources.py`，断言
  `datahub.sources._AKSHARE_COLUMN_MAP['成交额'] == 'amount'`。
- `test_index_standard_columns_includes_amount` —— 原地保留（`INDEX_STANDARD_COLUMNS` 留在
  `data_loader.py`），import 行去掉 `_AKSHARE_COLUMN_MAP`。

## Verification

- `python -m pytest -q tests/` 全绿。净变化：删除 1 个冗余测试（`_read_cached_frame`），
  迁移 4 个测试（3 个容错 + 1 个列映射），迁移后仍存在。
- 重跑删除符号的 grep，确认 `backtest/data_loader.py` 之外零残留引用。
- `backtest/data_loader.py` 的公开 API（4 个 `load_*` + `load_data` + `resolve_date_range`
  等 date helper + 列常量）签名与行为不变，`stock_selector` / `service` / `run_backtest` /
  scripts / 现有测试均不受影响。

## Non-goals

- **跨进程文件锁**：spec 与实现均写明这是单进程原型，`CacheStore.lock_for` 只防同进程
  并发。加 `filelock` 是给不存在的多进程场景上依赖。该限制已在
  `docs/superpowers/plans/2026-06-19-datahub-implementation.md` 的 Known Limitations 记录，
  本设计不引入文件锁。
- **录制型 golden 兼容测试**：原 spec 点名要"对比迁移前行为"，但旧 loader 函数体在本次
  收尾中删除，参照物消失；现有 FakeHub wrapper 测试已覆盖列/日期 dtype/行序/代表值，且
  `datahub/sources.py` 行为已验证与旧版一致。视为已覆盖，不额外录制 fixture。

## Acceptance Criteria

- `backtest/data_loader.py` 不再包含与 `datahub/sources.py` 重复的成交额/重试逻辑；活跃
  副本仅 `datahub/sources.py` 一份。
- `backtest/data_loader.py` 不再包含运行时无人调用的死代码（旧 `load_*` 函数体与孤儿辅助）。
- 重试/空数据容错测试指向 `datahub.sources` 活跃副本，不再指向 `data_loader.py` 死副本。
- `backtest/data_loader.py` 公开 API（函数名、签名、返回行为）保持不变，现有外部调用方
  无需改动。
- `python -m pytest -q tests/` 全绿。
