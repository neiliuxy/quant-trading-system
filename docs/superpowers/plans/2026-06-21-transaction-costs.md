# A股交易成本建模 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为回测引擎接入 A 股真实交易成本（佣金、印花税、过户费、滑点），让回测结果不再偏乐观。

**Architecture:** 新建 `backtest/costs.py` 集中费率常量与自定义 `bt.CommInfoBase` 子类（处理印花税单边、最低佣金等非对称费率），暴露一个 `apply_ashare_costs(cerebro)` 辅助函数。两条独立的回测路径（`backtest/service.py` 走 Web/API，`backtest/run_backtest.py` 走 CLI）各加一行调用接入。

**Tech Stack:** Python 3, backtrader 1.9.78, pytest。

**对应设计文档:** `docs/superpowers/specs/2026-06-21-transaction-costs-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `backtest/costs.py` | 费率常量 + `AShareCommission` 类 + `apply_ashare_costs()` | 新建 |
| `backtest/service.py` | Web/API 回测路径，接入成本 | 修改（+2 行） |
| `backtest/run_backtest.py` | CLI 回测路径，接入成本 | 修改（+2 行） |
| `tests/test_costs.py` | 成本逻辑单元测试 + 端到端回归 | 新建 |

---

## 背景知识（实现者必读）

- **backtrader 佣金接口**：`bt.CommInfoBase._getcommission(self, size, price, pseudoexec)` 返回单笔交易的总费用。`size` **带符号**：买入为正，卖出为负。靠 `size < 0` 判断卖出，实现印花税单边收取。
- **`percabs=True`**：让 `commission` 参数按绝对值解释（0.00025 = 0.025%），不需要 ×100。本设计直接在 `_getcommission` 里手算，该参数主要用于声明 commtype 行为。
- **滑点**：与佣金独立，通过 `cerebro.broker.set_slippage_perc(perc)` 设置，值落在 `broker.p.slip_perc`（已实机核查）。
- **测试数据**：项目用 `backtest.run_backtest.generate_synthetic_data(start, end)` 生成合成 OHLCV，不依赖网络。日期格式 `'20240101'`。
- **现有测试断言是结构性的**（`final_value > 0`、key 存在），不硬编码收益数字，因此本改动不会破坏它们。

---

### Task 1: 创建成本模块 `backtest/costs.py`

**Files:**
- Create: `backtest/costs.py`
- Test: `tests/test_costs.py`

- [ ] **Step 1: 写失败测试 —— 买入成本（佣金 + 过户费，无印花税）**

创建 `tests/test_costs.py`：

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backtrader as bt
import pytest

from backtest.costs import (
    AShareCommission,
    COMMISSION_RATE,
    MIN_COMMISSION,
    STAMP_DUTY_RATE,
    TRANSFER_FEE_RATE,
    SLIPPAGE_PERC,
    apply_ashare_costs,
)


def test_buy_cost_excludes_stamp_duty():
    comm = AShareCommission()
    # 金额够大,佣金按比例(超过最低 5 元)。买入 size > 0。
    size, price = 1000, 50.0  # value = 50000
    value = size * price
    cost = comm._getcommission(size, price, pseudoexec=False)
    expected = value * COMMISSION_RATE + value * TRANSFER_FEE_RATE
    assert cost == pytest.approx(expected)
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `python -m pytest tests/test_costs.py::test_buy_cost_excludes_stamp_duty -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'backtest.costs'`

- [ ] **Step 3: 写最小实现**

创建 `backtest/costs.py`：

```python
"""A股交易成本建模:佣金 + 印花税 + 过户费 + 滑点。

两条回测路径(backtest/service.py、backtest/run_backtest.py)共用。
费率为写死的 A股标准默认值,本期不做可配置化。
"""
import backtrader as bt

COMMISSION_RATE   = 0.00025   # 佣金 0.025%,双边
MIN_COMMISSION    = 5.0       # 最低佣金 5 元/笔
STAMP_DUTY_RATE   = 0.0005    # 印花税 0.05%,卖出单边
TRANSFER_FEE_RATE = 0.00001   # 过户费 0.001%,双边
SLIPPAGE_PERC     = 0.001     # 滑点 0.1%,双边


class AShareCommission(bt.CommInfoBase):
    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('percabs', True),  # 费率按绝对值,0.00025 = 0.025%
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        commission = max(value * COMMISSION_RATE, MIN_COMMISSION)
        transfer = value * TRANSFER_FEE_RATE
        stamp = value * STAMP_DUTY_RATE if size < 0 else 0.0  # 仅卖出
        return commission + transfer + stamp


def apply_ashare_costs(cerebro):
    """给 cerebro 套上 A股交易成本 + 滑点。两条回测路径共用。"""
    cerebro.broker.addcommissioninfo(AShareCommission())
    cerebro.broker.set_slippage_perc(SLIPPAGE_PERC)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `python -m pytest tests/test_costs.py::test_buy_cost_excludes_stamp_duty -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backtest/costs.py tests/test_costs.py
git commit -m "feat(backtest): add A-share commission module with buy-side cost"
```

---

### Task 2: 卖出成本含印花税 + 最低佣金托底

**Files:**
- Modify: `tests/test_costs.py`

- [ ] **Step 1: 写失败测试 —— 卖出比买入多出印花税**

在 `tests/test_costs.py` 末尾追加：

```python
def test_sell_cost_includes_stamp_duty():
    comm = AShareCommission()
    size, price = 1000, 50.0  # value = 50000
    value = size * price
    buy_cost = comm._getcommission(size, price, pseudoexec=False)
    sell_cost = comm._getcommission(-size, price, pseudoexec=False)
    # 卖出比买入恰好多一份印花税
    assert sell_cost - buy_cost == pytest.approx(value * STAMP_DUTY_RATE)


def test_minimum_commission_floor():
    comm = AShareCommission()
    # 小额交易:1 手(100 股)低价股,按比例佣金 < 5 元,应被托底到 5 元。
    size, price = 100, 3.0  # value = 300, 比例佣金 = 0.075 元
    value = size * price
    cost = comm._getcommission(size, price, pseudoexec=False)
    # 佣金被托底为 5 元 + 过户费(无印花税,买入)
    expected = MIN_COMMISSION + value * TRANSFER_FEE_RATE
    assert cost == pytest.approx(expected)
```

- [ ] **Step 2: 运行测试,确认通过**

实现已在 Task 1 完成,这两项测试应直接通过（验证设计正确性）。

Run: `python -m pytest tests/test_costs.py -v`
Expected: 3 项全部 PASS

> 若 `test_minimum_commission_floor` 失败,检查 `max(value * COMMISSION_RATE, MIN_COMMISSION)` 是否写对。

- [ ] **Step 3: 提交**

```bash
git add tests/test_costs.py
git commit -m "test(backtest): cover sell-side stamp duty and min commission"
```

---

### Task 3: 滑点接入测试

**Files:**
- Modify: `tests/test_costs.py`

- [ ] **Step 1: 写失败测试 —— apply_ashare_costs 设置滑点**

在 `tests/test_costs.py` 末尾追加：

```python
def test_apply_costs_sets_slippage():
    cerebro = bt.Cerebro()
    apply_ashare_costs(cerebro)
    assert cerebro.broker.p.slip_perc == pytest.approx(SLIPPAGE_PERC)
```

- [ ] **Step 2: 运行测试,确认通过**

Run: `python -m pytest tests/test_costs.py::test_apply_costs_sets_slippage -v`
Expected: PASS（实现已在 Task 1 完成）

- [ ] **Step 3: 提交**

```bash
git add tests/test_costs.py
git commit -m "test(backtest): verify slippage wiring in apply_ashare_costs"
```

---

### Task 4: 接入 service.py（Web/API 路径）

**Files:**
- Modify: `backtest/service.py`（import + `cerebro.broker.setcash(req.cash)` 之后一行）

- [ ] **Step 1: 加 import**

在 `backtest/service.py` 顶部的项目内 import 区（与其他 `from backtest...` 同处）加：

```python
from backtest.costs import apply_ashare_costs
```

- [ ] **Step 2: 在 setcash 后接入成本**

定位 `run_backtest_service` 中的这一行：

```python
    cerebro.broker.setcash(req.cash)
```

改为：

```python
    cerebro.broker.setcash(req.cash)
    apply_ashare_costs(cerebro)
```

- [ ] **Step 3: 运行现有 service 测试,确认不回归**

Run: `python -m pytest tests/test_backtest_service.py -v`
Expected: 全部 PASS（断言为结构性,加成本后 `final_value > 0` 仍成立）

- [ ] **Step 4: 提交**

```bash
git add backtest/service.py
git commit -m "feat(backtest): apply A-share costs in service backtest path"
```

---

### Task 5: 接入 run_backtest.py（CLI 路径）

**Files:**
- Modify: `backtest/run_backtest.py`（import + `cerebro.broker.setcash(cash)` 之后一行）

- [ ] **Step 1: 加 import**

在 `backtest/run_backtest.py` 顶部的项目内 import 区（与 `from backtest.service import _make_datahub` 同处）加：

```python
from backtest.costs import apply_ashare_costs
```

- [ ] **Step 2: 在 setcash 后接入成本**

定位 `run` 函数中的这一行：

```python
    cerebro.broker.setcash(cash)
```

改为：

```python
    cerebro.broker.setcash(cash)
    apply_ashare_costs(cerebro)
```

- [ ] **Step 3: 运行 CLI 烟囱测试,确认成本生效**

Run: `python backtest/run_backtest.py --symbol 000001 --start 20240101 --end 20240630`
Expected: 正常打印 `Starting cash` / `Final value` / `Return`。无报错即通过（数据失败会自动降级合成数据）。

- [ ] **Step 4: 提交**

```bash
git add backtest/run_backtest.py
git commit -m "feat(backtest): apply A-share costs in CLI backtest path"
```

---

### Task 6: 端到端回归测试（加成本后收益下降）

**Files:**
- Modify: `tests/test_costs.py`

- [ ] **Step 1: 写测试 —— 有成本 vs 无成本,有成本更低**

在 `tests/test_costs.py` 顶部 import 区追加：

```python
import pandas as pd
from backtest.run_backtest import generate_synthetic_data
```

在文件末尾追加：

```python
def _run_with(cerebro_mutator):
    """跑一段合成数据回测,返回 final_value。cerebro_mutator 用于注入成本。"""
    from strategies.swing_ma_boll import SwingStrategy

    df = generate_synthetic_data(start='20200101', end='20221231')
    df['date'] = pd.to_datetime(df['date'])
    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=df, datetime=0))
    cerebro.addstrategy(SwingStrategy, market_score_dict=None)
    cerebro.broker.setcash(100000.0)
    cerebro_mutator(cerebro)
    cerebro.run(runonce=False, stdstats=False)
    return cerebro.broker.getvalue()


def test_costs_reduce_final_value():
    baseline = _run_with(lambda c: None)            # 无成本
    with_costs = _run_with(apply_ashare_costs)      # 有成本
    # 同样的策略与数据,加成本后最终市值必须更低
    assert with_costs < baseline
```

- [ ] **Step 2: 运行测试,确认通过**

Run: `python -m pytest tests/test_costs.py::test_costs_reduce_final_value -v`
Expected: PASS

> 若失败且 `with_costs == baseline`：说明该合成区间内策略没有成交（成本无从体现）。改用更长区间或换 `'20200101'`–`'20231231'`，确保 SwingStrategy 在该数据上至少成交一次。

- [ ] **Step 3: 提交**

```bash
git add tests/test_costs.py
git commit -m "test(backtest): verify costs reduce final portfolio value"
```

---

### Task 7: 全量回归

**Files:** 无（仅运行）

- [ ] **Step 1: 跑全部测试**

Run: `python -m pytest -q tests/`
Expected: 全绿。

> 若 `test_backtest_service.py` 或 `test_integration.py` 出现失败：检查是否有硬编码的收益数字断言（设计核查阶段未发现，但以实跑为准）。若有，按新的含成本结果更新断言值，并在 commit message 说明。

- [ ] **Step 2: 提交（仅当有断言更新时）**

```bash
git add tests/
git commit -m "test: update assertions for post-cost backtest results"
```

若无改动则跳过本步。

---

## Self-Review 记录

- **Spec 覆盖**：四项成本（佣金/印花税/过户费/滑点）→ Task 1-3；两条接入路径 → Task 4-5；五项测试 → Task 1-3+6；全量回归 → Task 7。无遗漏。
- **占位符**：无 TBD/TODO，每个代码步骤含完整代码。
- **类型一致性**：`AShareCommission`、`apply_ashare_costs`、`slip_perc`、各费率常量名在所有 Task 中一致。
- **API 准确性**：`_getcommission` 签名、`set_slippage_perc`、`slip_perc` 均实机核查（backtrader 1.9.78）。
