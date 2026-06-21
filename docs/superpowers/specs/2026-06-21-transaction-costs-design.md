# A股交易成本建模 — 设计文档

> 创建日期：2026-06-21
> 对应改进项：`docs/improvement-directions.md` 第 1 项「补齐交易成本」

---

## 背景与目标

当前回测路径完全没有交易成本：全仓库检索不到 `setcommission` / `slippage`。波段策略 3~10 天换手，成本会显著吃掉收益，导致**所有回测结果偏乐观**。

本设计为回测引擎接入 A 股真实交易成本，让回测结果可信。

**非目标**：成本费率的可配置化（CLI / API / 前端调参）。本期采用写死的默认值，符合 YAGNI。

---

## 成本构成（A股标准费率）

| 费项 | 费率 | 买入 | 卖出 | 说明 |
|------|------|:----:|:----:|------|
| 佣金 | 0.025%，最低 5 元/笔 | ✓ | ✓ | 券商收取 |
| 印花税 | 0.05% | ✗ | ✓ | **仅卖出单边** |
| 过户费 | 0.001% | ✓ | ✓ | 沪深均收 |
| 滑点 | 0.1% | ✓ | ✓ | 模拟冲击成本 |

关键非对称性：**印花税只在卖出收**，**佣金有最低 5 元限制**。这是选用自定义 `CommInfoBase` 而非简单 `setcommission` 的原因 —— 后者只能表达对称的固定费率。

---

## 架构

### 新增模块 `backtest/costs.py`

集中所有费率常量与成本逻辑，单一职责，可独立测试。两条回测路径共用。

```python
import backtrader as bt

# A股费率常量(写死的默认值)
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

要点：
- `size` 在 backtrader 中带符号（买入正、卖出负），靠 `size < 0` 判断卖出以实现印花税单边收取。
- 最低佣金用 `max(...)` 表达。
- 滑点独立走 `set_slippage_perc`，不混进佣金。
- `percabs=True` 让费率按绝对值解释（0.00025 = 0.025%），避免 ×100 混淆。

> backtrader 接口已核查（v1.9.78）：`_getcommission(self, size, price, pseudoexec)` 签名、`set_slippage_perc`、`addcommissioninfo` 均存在。

### 接入点（两处，各加一行）

两条路径独立构建 cerebro，均需接入：

**路径一 —— `backtest/service.py`（Web/API）**
在 `cerebro.broker.setcash(req.cash)` 之后：
```python
cerebro.broker.setcash(req.cash)
apply_ashare_costs(cerebro)   # 新增
```

**路径二 —— `backtest/run_backtest.py`（CLI）**
在 `cerebro.broker.setcash(cash)` 之后插入同样一行。

两个文件顶部各加 `from backtest.costs import apply_ashare_costs`。

---

## 附带影响（已核查，无需额外动作）

- **缓存自动失效**：`run_key`（`server/jobs.py`）的哈希包含 `code_version`（git short hash）。本次提交后 code_version 变化，旧的「零成本」缓存结果不会被命中，新回测自动重算，无需手动清 `data/quantx.sqlite`。
- **汇总逻辑不变**：`BacktestResult` 的 `final_value` / `total_return_pct` / `win_rate_pct` 全部由 cerebro 算出，加成本后自动反映，无需改 `run_backtest_service` 的汇总代码。结果会比现在低一些，这正是预期效果。

---

## 测试 `tests/test_costs.py`

直接验证成本逻辑，不依赖网络/数据：

1. **买入成本** — `size>0`：佣金（按比例）+ 过户费，**不含**印花税。用金额够大的交易，验证 `_getcommission` ≈ `value*(0.00025+0.00001)`。
2. **卖出成本** — `size<0`：佣金 + 过户费 + 印花税，验证比同额买入多出 `value*0.0005`。
3. **最低佣金** — 小额交易（1 手 × 低价），验证佣金被 `max(..., 5.0)` 托底到 5 元。
4. **滑点接入** — 调 `apply_ashare_costs(cerebro)` 后，断言 `broker.p.slip_perc == 0.001`。
5. **端到端回归** — 同一段合成数据，「加成本」vs「无成本」，断言加成本后 `final_value` 更低且有成交，证明确实在扣钱。

**验证标准**：
- `python -m pytest -q tests/test_costs.py` 全绿。
- `python -m pytest -q tests/` 整体不回归。`test_backtest_service.py`、`test_integration.py` 若硬编码了旧收益数字，同步更新断言。

---

## 落地步骤

1. 新建 `backtest/costs.py` → 验证：可 import，常量与类定义正确。
2. `service.py` 接入 + import → 验证：Web 回测结果较此前下降。
3. `run_backtest.py` 接入 + import → 验证：CLI 回测打印的 Return 较此前下降。
4. 新建 `tests/test_costs.py` → 验证：5 项测试全绿。
5. 全量测试 `python -m pytest -q tests/` → 验证：无回归（必要时更新硬编码断言）。
