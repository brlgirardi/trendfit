"""Testes do Triple Screen com nosso motor (apartado do engine)."""

import numpy as np
import pandas as pd
import pytest

from trendfit.engine.triple_screen import (
    resample_weekly,
    triple_screen_weights,
    weekly_tide,
)


@pytest.fixture
def df():
    n = 520
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    trend = np.linspace(100, 220, n)
    noise = np.cumsum(np.sin(np.linspace(0, 50, n)) * 1.2)
    close = trend + noise
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                         "Close": close, "Volume": np.full(n, 1000.0)}, index=idx)


def test_resample_weekly(df):
    wk = resample_weekly(df)
    assert len(wk) < len(df)
    assert set(["Open", "High", "Low", "Close"]).issubset(wk.columns)
    assert (wk["High"] >= wk["Low"]).all()


def test_weights_in_range(df):
    w = triple_screen_weights(df, [4, 8, 13], [20, 40, 80])
    assert len(w) == len(df)
    assert w.min() >= 0.0 and w.max() <= 1.0


def test_tide_is_boolean(df):
    t = weekly_tide(df, [4, 8, 13])
    assert t.dtype == bool
    assert len(t) == len(df)


def test_tide_gates_exposure(df):
    """Onde a maré é baixa, o peso é zerado (filtro de tela 1)."""
    w = triple_screen_weights(df, [4, 8, 13], [20, 40, 80])
    tide = weekly_tide(df, [4, 8, 13])
    assert np.all(w[~tide] == 0.0)


def test_no_lookahead(df):
    """CAUSALIDADE: a decisão do dia i não muda com dados futuros."""
    full = triple_screen_weights(df, [4, 8, 13], [20, 40, 80])
    for i in (300, 380, 450):
        trunc = triple_screen_weights(df.iloc[: i + 1], [4, 8, 13], [20, 40, 80])
        assert trunc[i] == pytest.approx(full[i]), f"look-ahead no dia {i}"
