import numpy as np

from trendfit.engine.ensemble import ensemble_position
from trendfit.layers.regime import regime_allow


def test_ensemble_position_is_fraction(trend_df):
    lbs = [10, 20, 30]
    pos = ensemble_position(trend_df, lbs, "donchian")
    assert pos.min() >= 0.0 and pos.max() <= 1.0
    # valores possíveis são múltiplos de 1/len(lbs)
    allowed = {round(k / len(lbs), 6) for k in range(len(lbs) + 1)}
    assert set(np.round(np.unique(pos), 6)).issubset(allowed)


def test_ensemble_all_long_in_strong_uptrend(trend_df):
    pos = ensemble_position(trend_df, [10, 20, 30], "donchian")
    assert pos[190] == 1.0  # todos os lookbacks long no topo da subida


def test_ensemble_unknown_kind_raises(trend_df):
    import pytest

    with pytest.raises(ValueError):
        ensemble_position(trend_df, [10], "naoexiste")


def test_regime_allow_matches_ma(trend_df):
    allow = regime_allow(trend_df, 200)
    ma = trend_df["Close"].rolling(200).mean().to_numpy()
    close = trend_df["Close"].to_numpy()
    # onde há MA, allow == (close > ma)
    valid = ~np.isnan(ma)
    np.testing.assert_array_equal(allow[valid], close[valid] > ma[valid])
    # antes da janela, sempre False (conservador)
    assert not allow[:199].any()
