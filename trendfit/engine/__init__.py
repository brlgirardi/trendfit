"""Engine de backtest: indicadores, ensemble, backtest vetorizado e walk-forward."""

from trendfit.engine.backtest import BacktestResult, backtest, buy_and_hold
from trendfit.engine.ensemble import ensemble_position
from trendfit.engine.walkforward import WalkForwardResult, walk_forward

__all__ = [
    "ensemble_position",
    "backtest",
    "buy_and_hold",
    "BacktestResult",
    "walk_forward",
    "WalkForwardResult",
]
