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
