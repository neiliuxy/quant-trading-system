"""Structured backtest service used by CLI and web API."""

from dataclasses import asdict, dataclass, field
from typing import Any

import backtrader as bt
import pandas as pd

from backtest.data_loader import load_market_data, resolve_date_range
from market.market_analyzer import MarketConfig, get_market_score
from strategies.registry import get_strategy_spec


@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    start: str
    end: str
    cash: float = 100000.0
    use_market_filter: bool = True
    risk_percent: float = 0.95
    fast_ma: int = 10
    slow_ma: int = 20
    strategy_id: str = 'swing_ma_boll'
    strategy_params: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> 'BacktestRequest':
        start, end = resolve_date_range(self.start, self.end)
        try:
            spec = get_strategy_spec(self.strategy_id)
        except KeyError:
            raise ValueError(f"Unknown strategy_id: '{self.strategy_id}'")
        # Silently ignore unknown params - each strategy only uses its declared params
        merged_params = dict(spec.defaults)
        for k, v in self.strategy_params.items():
            if k in {param.name for param in spec.params}:
                merged_params[k] = v
        return BacktestRequest(
            symbol=str(self.symbol).zfill(6),
            start=start,
            end=end,
            cash=float(self.cash),
            use_market_filter=bool(self.use_market_filter),
            risk_percent=float(self.risk_percent),
            fast_ma=int(self.fast_ma),
            slow_ma=int(self.slow_ma),
            strategy_id=self.strategy_id,
            strategy_params=merged_params,
        )


@dataclass
class BacktestResult:
    symbol: str
    start: str
    end: str
    initial_cash: float
    final_value: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    market_scores: list[dict[str, Any]] = field(default_factory=list)
    market_score_summary: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EquityCurveAnalyzer(bt.Analyzer):
    def start(self):
        self.rows = []

    def next(self):
        self.rows.append({
            'date': self.strategy.datas[0].datetime.date(0).strftime('%Y%m%d'),
            'value': float(self.strategy.broker.getvalue()),
            'cash': float(self.strategy.broker.getcash()),
        })

    def get_analysis(self):
        return self.rows


class TradeListAnalyzer(bt.Analyzer):
    def start(self):
        self.trades = []

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.trades.append({
            'date': self.strategy.datas[0].datetime.date(0).strftime('%Y%m%d'),
            'pnl': float(trade.pnl),
            'pnlcomm': float(trade.pnlcomm),
            'barlen': int(trade.barlen),
            'size': float(trade.size),
        })

    def get_analysis(self):
        return self.trades


def _market_score_payload(start: str, end: str, enabled: bool) -> tuple[dict[str, float] | None, list[dict[str, Any]], dict[str, float]]:
    if not enabled:
        return None, [], {}

    score_df = get_market_score(start, end, MarketConfig())
    score_dict = dict(zip(
        score_df['date'].dt.strftime('%Y%m%d'),
        score_df['total_score'],
    ))
    rows = []
    for _, row in score_df.iterrows():
        rows.append({
            'date': row['date'].strftime('%Y%m%d'),
            'trend_score': float(row['trend_score']),
            'sentiment_score': float(row['sentiment_score']),
            'volume_score': float(row['volume_score']),
            'total_score': float(row['total_score']),
        })
    summary = {
        'min': float(score_df['total_score'].min()),
        'max': float(score_df['total_score'].max()),
        'mean': float(score_df['total_score'].mean()),
    }
    return score_dict, rows, summary


def run_backtest_service(request: BacktestRequest) -> BacktestResult:
    req = request.normalized()
    spec = get_strategy_spec(req.strategy_id)
    score_dict, score_rows, score_summary = _market_score_payload(
        req.start, req.end, req.use_market_filter
    )

    df = load_market_data(req.symbol, req.start, req.end)
    data = bt.feeds.PandasData(dataname=df, datetime=0)

    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    strategy_kwargs = dict(req.strategy_params)
    strategy_kwargs['risk_percent'] = req.risk_percent
    strategy_kwargs['market_score_dict'] = score_dict
    # Only pass params the strategy class actually declares
    strategy_param_names = set(spec.strategy_class.params._getkeys())
    strategy_kwargs = {k: v for k, v in strategy_kwargs.items() if k in strategy_param_names}
    cerebro.addstrategy(spec.strategy_class, **strategy_kwargs)
    cerebro.broker.setcash(req.cash)
    cerebro.addanalyzer(EquityCurveAnalyzer, _name='equity')
    cerebro.addanalyzer(TradeListAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_stats')

    strategies = cerebro.run(runonce=False, stdstats=False)
    strategy = strategies[0]

    final_value = float(cerebro.broker.getvalue())
    total_return_pct = (final_value / req.cash - 1.0) * 100.0
    drawdown = strategy.analyzers.drawdown.get_analysis()
    trade_stats = strategy.analyzers.trade_stats.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()
    total_closed = int(trade_stats.get('total', {}).get('closed', 0) or 0)
    won_total = int(trade_stats.get('won', {}).get('total', 0) or 0)
    win_rate_pct = (won_total / total_closed * 100.0) if total_closed else 0.0

    return BacktestResult(
        symbol=req.symbol,
        start=req.start,
        end=req.end,
        initial_cash=req.cash,
        final_value=final_value,
        total_return_pct=float(total_return_pct),
        max_drawdown_pct=float(drawdown.get('max', {}).get('drawdown', 0.0) or 0.0),
        trade_count=total_closed,
        win_rate_pct=float(win_rate_pct),
        equity_curve=strategy.analyzers.equity.get_analysis(),
        trades=trades,
        market_scores=score_rows,
        market_score_summary=score_summary,
    )
