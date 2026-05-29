import numpy as np
import pandas as pd

from trendfit.engine.backtest import backtest, buy_and_hold


def _const_df(prices):
    idx = pd.date_range("2021-01-01", periods=len(prices), freq="D", tz="UTC")
    df = pd.DataFrame({"Open": prices, "High": prices, "Low": prices, "Close": prices}, index=idx)
    return df


def test_buy_and_hold_equals_price_ratio():
    df = _const_df([100, 110, 121, 133.1])  # +10% ao dia
    res = buy_and_hold(df, 0, len(df))
    # B&H total = preço_final/preço_inicial - 1
    assert abs(res.total_return - (133.1 / 100 - 1)) < 1e-9


def test_weight_applied_to_prior_day_no_lookahead():
    """Peso decidido no dia i só captura o retorno de i->i+1 (nunca o de hoje)."""
    df = _const_df([100, 100, 200, 200])  # salto só entre dia 1 e 2
    w = np.zeros(len(df))
    w[1] = 1.0  # long decidido no dia índice 1 -> captura o salto para o dia 2
    res = backtest(df, w, 0, len(df))
    assert abs(res.total_return - 1.0) < 1e-9  # capturou +100%

    w2 = np.zeros(len(df))
    w2[2] = 1.0  # long decidido só no dia 2 -> salto já passou, não captura nada
    res2 = backtest(df, w2, 0, len(df))
    assert abs(res2.total_return - 0.0) < 1e-9


def test_fractional_weight_scales_return():
    df = _const_df([100, 100, 200, 200])
    w = np.zeros(len(df))
    w[1] = 0.5
    res = backtest(df, w, 0, len(df))
    assert abs(res.total_return - 0.5) < 1e-9  # metade do salto de +100%


def test_cost_reduces_return():
    df = _const_df([100, 110, 121])
    w = np.ones(len(df))
    no_cost = backtest(df, w, 0, len(df), cost_bps=0.0)
    with_cost = backtest(df, w, 0, len(df), cost_bps=50.0)
    assert with_cost.total_return < no_cost.total_return


def test_max_drawdown_negative_on_decline():
    df = _const_df([100, 120, 60, 60])
    w = np.ones(len(df))
    res = backtest(df, w, 0, len(df))
    assert res.max_drawdown < 0
