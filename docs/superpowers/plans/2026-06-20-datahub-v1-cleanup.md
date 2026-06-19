# DataHub v1 收尾清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清除 `backtest/data_loader.py` 的迁移债务——删死代码、消除与 `datahub/sources.py` 重复的成交额/重试容错逻辑、把指向死副本的容错测试迁移到活跃副本，使 `datahub/sources.py` 成为唯一真相源。

**Architecture:** 纯删除 + 测试迁移，不改任何数据路径运行时行为。三步有序推进：先把迁移后的测试加到 `test_datahub_sources.py`（指向活跃副本，立即通过），再从 data_loader 测试文件移除旧测试，最后删除 `data_loader.py` 的死代码与无用 import。每步保持全量测试绿色。

**Tech Stack:** Python 3, pandas, pytest, AkShare, DataHub。

参考 spec: `docs/superpowers/specs/2026-06-20-datahub-v1-cleanup-design.md`

---

## File Map

- Modify: `tests/test_datahub_sources.py` — 新增 4 个从容错/映射迁移来的测试，指向 `datahub.sources` 活跃副本。
- Modify: `tests/test_data_loader_strategy_feeds.py` — 删除 4 个测试（3 个容错迁移走 + 1 个 `_read_cached_frame` 冗余删除），保留 5 个 wrapper 测试 + `_LoaderFakeHub`。
- Modify: `tests/test_data_loader_index.py` — 删除 `test_akshare_amount_mapping_exists`（已迁移），import 行去掉 `_AKSHARE_COLUMN_MAP`。
- Modify: `backtest/data_loader.py` — 删除 3 个旧 `load_*` 函数体 + 全部孤儿/重复辅助 + 无用 import，更新 docstring；保留 date helper、列常量、`_make_datahub`、4 个 wrapper、`load_data`。

---

### Task 1: 迁移容错/映射测试到 `test_datahub_sources.py`

**Files:**
- Modify: `tests/test_datahub_sources.py`

- [ ] **Step 1: 扩展顶部 import，加入被测的活跃副本符号**

把 `tests/test_datahub_sources.py` 顶部的：

```python
from datahub.sources import AkshareSource
```

改为：

```python
from datahub.sources import AkshareSource, _AKSHARE_COLUMN_MAP, _fetch_sse_turnover
```

- [ ] **Step 2: 在文件末尾追加 4 个迁移测试**

追加：

```python
def test_fetch_sse_turnover_returns_none_on_empty_akshare_data(monkeypatch):
    """akshare 对空 result 抛 Length mismatch 时，_fetch_sse_turnover 容错返回 None。"""
    def raise_length_mismatch(date):
        raise ValueError("Length mismatch: Expected axis has 1 elements, new values have 6 elements")

    monkeypatch.setattr("datahub.sources.ak.stock_sse_deal_daily", raise_length_mismatch)

    assert _fetch_sse_turnover("20210617") is None


def test_empty_data_error_does_not_retry(monkeypatch):
    """空数据（Length mismatch）是确定性错误，必须立即跳过、不重试。"""
    calls = {"n": 0}

    def boom(date):
        calls["n"] += 1
        raise ValueError("Length mismatch: Expected axis has 1 elements, new values have 6 elements")

    monkeypatch.setattr("datahub.sources.ak.stock_sse_deal_daily", boom)

    assert _fetch_sse_turnover("20210617") is None
    assert calls["n"] == 1  # 只调一次，无重试


def test_network_error_does_retry(monkeypatch):
    """SSL/网络类偶发错误应重试（区别于确定性的空数据错误）。"""
    calls = {"n": 0}

    def flaky(date):
        calls["n"] += 1
        raise ConnectionError("SSL: UNEXPECTED_EOF_WHILE_READING")

    monkeypatch.setattr("datahub.sources.ak.stock_sse_deal_daily", flaky)
    monkeypatch.setattr("datahub.sources.time.sleep", lambda s: None)  # 跳过 sleep 加速测试

    assert _fetch_sse_turnover("20240102") is None
    assert calls["n"] == 3  # 重试满 3 次


def test_akshare_amount_mapping_exists():
    assert _AKSHARE_COLUMN_MAP["成交额"] == "amount"
```

- [ ] **Step 3: 运行新测试，确认通过（活跃副本已具备容错逻辑）**

Run: `python -m pytest -q tests/test_datahub_sources.py`

Expected: PASS（含原有 3 个 + 新增 4 个 = 7 个测试）。

- [ ] **Step 4: Commit**

```bash
git add tests/test_datahub_sources.py
git commit -m "test(datahub): relocate turnover/retry tests to live sources"
```

---

### Task 2: 从 data_loader 测试文件移除已迁移/冗余测试

**Files:**
- Modify: `tests/test_data_loader_strategy_feeds.py`
- Modify: `tests/test_data_loader_index.py`

- [ ] **Step 1: 从 `test_data_loader_strategy_feeds.py` 删除 4 个测试**

删除以下 4 个函数（连同其 docstring/空行）：

- `test_read_cached_frame_accepts_equivalent_columns_and_reorders`（等价覆盖已在 `test_datahub_cache.py`）
- `test_fetch_sse_turnover_returns_none_on_empty_akshare_data`（已迁至 Task 1）
- `test_empty_data_error_does_not_retry`（已迁至 Task 1）
- `test_network_error_does_retry`（已迁至 Task 1）

删除后保留：`_LoaderFakeHub` helper 与 5 个 wrapper 测试（`test_load_security_etf_data_normalizes_index_columns`、`test_load_market_turnover_data_returns_price_like_frame`、`test_load_market_turnover_data_uses_trading_dates_only`、`test_load_market_turnover_skips_days_with_missing_data`、`test_load_market_data_wrapper_matches_datahub_result`）。这些保留测试不引用任何待删符号，无需改 import。

- [ ] **Step 2: 从 `test_data_loader_index.py` 删除迁移走的测试并修正 import**

把文件改为（仅保留 `test_index_standard_columns_includes_amount`，import 去掉 `_AKSHARE_COLUMN_MAP`）：

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.data_loader import INDEX_STANDARD_COLUMNS


def test_index_standard_columns_includes_amount():
    assert 'amount' in INDEX_STANDARD_COLUMNS
    assert 'date' in INDEX_STANDARD_COLUMNS
    assert 'open' in INDEX_STANDARD_COLUMNS
    assert 'close' in INDEX_STANDARD_COLUMNS
    assert 'volume' in INDEX_STANDARD_COLUMNS
    assert len(INDEX_STANDARD_COLUMNS) == 7
```

- [ ] **Step 3: 运行这两个测试文件，确认通过**

Run: `python -m pytest -q tests/test_data_loader_strategy_feeds.py tests/test_data_loader_index.py`

Expected: PASS（`test_data_loader_strategy_feeds.py` 剩 5 个；`test_data_loader_index.py` 剩 1 个）。

- [ ] **Step 4: Commit**

```bash
git add tests/test_data_loader_strategy_feeds.py tests/test_data_loader_index.py
git commit -m "test(data_loader): drop migrated/redundant tests"
```

---

### Task 3: 删除 `backtest/data_loader.py` 死代码

**Files:**
- Modify: `backtest/data_loader.py`

此时已无测试引用 `data_loader.py` 里的 `_fetch_sse_turnover` / `_retry_akshare` / `_read_cached_frame` / `_AKSHARE_COLUMN_MAP` 等符号，可安全删除。

- [ ] **Step 1: 用如下内容整体替换 `backtest/data_loader.py`**

```python
"""市场数据加载器。

公共 load_* 函数是 DataHub 的薄包装，委托 datahub.service.DataHub 取数。
date helper（resolve_date_range 等）仍供 backtest 服务层、选股器、脚本与 CLI 复用。
"""

import os
import re
from datetime import date, datetime

import pandas as pd

from datahub.models import DatasetRequest
from datahub.service import DataHub
from server.db import DEFAULT_DB_PATH, init_db

STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']
INDEX_STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']


def _format_date(value):
    """将 date/datetime/字符串日期统一成 YYYYMMDD。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime('%Y%m%d')
    if isinstance(value, date):
        return value.strftime('%Y%m%d')

    text = str(value).strip()
    if re.fullmatch(r'\d{8}', text):
        return text
    return pd.to_datetime(text).strftime('%Y%m%d')


def _shift_years(value, years):
    """按年份平移日期，处理 2 月 29 日落到非闰年的情况。"""
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def get_default_date_range(years=3):
    """返回最近 years 年的默认日期范围，格式为 (YYYYMMDD, YYYYMMDD)。"""
    end_date = date.today()
    start_date = _shift_years(end_date, -years)
    return _format_date(start_date), _format_date(end_date)


def resolve_date_range(start=None, end=None, years=3):
    """解析可选日期边界，未传时默认最近 years 年。"""
    default_start, default_end = get_default_date_range(years)
    if start is None and end is None:
        return default_start, default_end
    if start is None:
        end_text = _format_date(end)
        start_date = _shift_years(pd.to_datetime(end_text).date(), -years)
        return _format_date(start_date), end_text
    if end is None:
        return _format_date(start), default_end
    return _format_date(start), _format_date(end)


def _make_datahub() -> DataHub:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return DataHub(root_dir=project_root, conn=init_db(DEFAULT_DB_PATH))


def load_market_data(symbol, start, end):
    """DataHub 包装：加载股票日线数据（保留原签名）。"""
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest(
            dataset_type='stock_daily',
            symbol=str(symbol).zfill(6),
            start=start,
            end=end,
        )
    )
    return result.frame


def load_shanghai_composite(start, end):
    """DataHub 包装：加载上证综合指数。获取失败时返回 None 保持向后兼容。"""
    start, end = resolve_date_range(start, end)
    try:
        result = _make_datahub().get_dataset(
            DatasetRequest(
                dataset_type='index_daily',
                symbol='sh000001',
                start=start,
                end=end,
            )
        )
        return result.frame
    except Exception as exc:
        print(f'无法获取上证综合指数的历史数据: {exc}')
        return None


def load_security_etf_data(start, end, symbol='sh512880'):
    """DataHub 包装：加载证券 ETF 数据。"""
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest(
            dataset_type='etf_daily',
            symbol=symbol,
            start=start,
            end=end,
        )
    )
    return result.frame


def load_market_turnover_data(start, end):
    """DataHub 包装：加载两市成交额数据。"""
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest(
            dataset_type='market_turnover',
            start=start,
            end=end,
        )
    )
    return result.frame


def load_data(symbol, start=None, end=None, include_index=False):
    """
    加载股票数据，可选加载上证综合指数。

    Args:
        symbol:        股票代码，如 '000001'
        start:         开始日期，如 '20200101'，默认最近 3 年
        end:           结束日期，如 '20231231'，默认今天
        include_index: 是否加载上证综合指数，默认 False

    Returns:
        如果 include_index=False，返回股票 DataFrame。
        如果 include_index=True，返回 (stock_df, index_df) 元组。
        指数加载失败时 index_df 为 None。

    Raises:
        Exception: 股票数据加载失败时抛出。
    """
    stock_df = load_market_data(symbol, start, end)

    if not include_index:
        return stock_df

    try:
        index_df = load_shanghai_composite(start, end)
    except Exception as e:
        print(f'上证指数加载失败，将继续使用股票数据: {e}')
        index_df = None

    return stock_df, index_df
```

- [ ] **Step 2: 运行全量测试，确认绿色**

Run: `python -m pytest -q tests/`

Expected: PASS（净 153 个，相比清理前 154 减 1：删除了冗余的 `_read_cached_frame` 测试；迁移的 4 个仍存在）。

- [ ] **Step 3: 重跑删除符号 grep，确认 `data_loader.py` 之外零残留引用**

Run:

```bash
grep -rn "_fetch_sse_turnover\|_fetch_szse_turnover\|_retry_akshare\|_is_empty_data_error\|_read_cached_frame\|_get_stock_name\|_sanitize_filename_part\|_parse_filename\|_AKSHARE_COLUMN_MAP\|_CACHE_DIR" --include="*.py" . | grep -v "datahub/sources.py"
```

Expected: 无输出（所有匹配仅剩 `datahub/sources.py` 活跃副本，不再有 `data_loader.py` 或测试引用）。

- [ ] **Step 4: Commit**

```bash
git add backtest/data_loader.py
git commit -m "refactor(data_loader): remove dead code and duplicated turnover/retry logic"
```

---

## Self-Review

- **Spec coverage:** spec「Deletions」→ Task 3；spec「Test Relocation」→ Task 1 + Task 2；spec「Verification」→ 每个 Task 的 run + Task 3 Step 3 grep；spec「Non-goals」（跨进程锁、golden）明确不做，无对应任务，符合预期；spec「Acceptance Criteria」每条都被 Task 1-3 覆盖。
- **Placeholder scan:** 无 TBD/TODO；每个代码步骤都给了完整代码或精确删除清单。
- **Type consistency:** 被迁移测试的符号名（`_fetch_sse_turnover`、`_AKSHARE_COLUMN_MAP`）与 `datahub/sources.py` 实际定义一致；`data_loader.py` 保留的 `STANDARD_COLUMNS` / `INDEX_STANDARD_COLUMNS` / `resolve_date_range` 等与现有调用方一致。

## Known Limitations

- 本计划不引入跨进程文件锁，`CacheStore.lock_for` 仍只防同进程并发。该限制已在 `docs/superpowers/plans/2026-06-19-datahub-implementation.md` 的 Known Limitations 记录。
