"""Testes do sistema Elder (Triple Screen) — apartado do engine principal."""

import numpy as np
import pandas as pd
import pytest

from trendfit.engine.elder import (
    ElderConfig,
    atr,
    force_index,
    macd_histogram,
    stochastic_k,
    triple_screen_position,
)


@pytest.fixture
def df():
    """Série diária sintética com tendência + ruído (2 anos)."""
    n = 520
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    trend = np.linspace(100, 200, n)
    noise = np.cumsum(np.sin(np.linspace(0, 60, n)) * 1.5)
    close = trend + noise
    high = close + 1.0
    low = close - 1.0
    vol = np.full(n, 1000.0)
    return pd.DataFrame({"Open": close, "High": high, "Low": low, "Close": close,
                         "Volume": vol}, index=idx)


def test_macd_histogram_shape(df):
    h = macd_histogram(df["Close"].to_numpy())
    assert len(h) == len(df)
    assert np.all(np.isfinite(h))


def test_force_index_shape(df):
    fi = force_index(df["Close"].to_numpy(), df["Volume"].to_numpy())
    assert len(fi) == len(df)
    assert np.all(np.isfinite(fi))


def test_stochastic_in_range(df):
    k = stochastic_k(df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy())
    assert len(k) == len(df)
    assert k.min() >= 0.0 and k.max() <= 100.0


def test_atr_positive(df):
    a = atr(df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy())
    assert len(a) == len(df)
    assert np.all(a >= 0)


def test_position_is_binary(df):
    pos = triple_screen_position(df)
    assert len(pos) == len(df)
    assert set(np.unique(pos)).issubset({0.0, 1.0})


def test_position_starts_flat(df):
    """Sem maré computável no começo, não pode estar comprado de cara."""
    pos = triple_screen_position(df)
    assert pos[0] == 0.0


def test_position_no_lookahead(df):
    """CAUSALIDADE: a decisão do dia i não pode mudar quando dados FUTUROS mudam.

    Compara a posição em índices passados calculada sobre o df completo vs. sobre o
    df truncado até i — devem bater (a maré semanal é defasada, sem look-ahead)."""
    full = triple_screen_position(df)
    for i in (300, 380, 450):
        truncated = triple_screen_position(df.iloc[: i + 1])
        assert truncated[i] == full[i], f"look-ahead detectado no dia {i}"


def test_stoch_fallback_without_volume(df):
    """Sem volume, cai no estocástico sem quebrar."""
    no_vol = df.drop(columns=["Volume"])
    cfg = ElderConfig(oscillator="force")  # força, mas sem volume → fallback stoch
    pos = triple_screen_position(no_vol, cfg)
    assert set(np.unique(pos)).issubset({0.0, 1.0})


def test_config_stoch_mode(df):
    pos = triple_screen_position(df, ElderConfig(oscillator="stoch"))
    assert len(pos) == len(df)
