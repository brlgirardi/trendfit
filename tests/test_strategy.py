import numpy as np
import pandas as pd

from trendfit.engine.strategy import (
    StrategyConfig,
    _apply_cooldown,
    _chandelier_overlay,
    atr,
    donchian_long_asym,
    donchian_state_symmetric,
    ensemble_long_asym,
    ensemble_net,
    regime_hysteresis,
    target_weights,
)


def _df(close):
    idx = pd.date_range("2020-01-01", periods=len(close), freq="D", tz="UTC")
    df = pd.DataFrame(index=idx)
    df["Close"] = close
    df["Open"] = df["Close"].shift(1).fillna(df["Close"])
    df["High"] = df[["Open", "Close"]].max(axis=1) * 1.001
    df["Low"] = df[["Open", "Close"]].min(axis=1) * 0.999
    return df


def test_symmetric_state_in_minus1_plus1():
    df = _df(np.concatenate([np.linspace(100, 300, 120), np.linspace(300, 100, 120)]))
    st = donchian_state_symmetric(df["High"], df["Low"], df["Close"], 20)
    assert set(np.unique(st)).issubset({-1.0, 0.0, 1.0})
    assert st[110] == 1.0    # subindo -> long
    assert st[230] == -1.0   # caindo -> short


def test_ensemble_net_in_range():
    df = _df(np.linspace(100, 300, 300))
    net = ensemble_net(df, [10, 20, 30])
    assert net.min() >= -1.0 and net.max() <= 1.0


def test_regime_hysteresis_holds_in_dead_zone():
    # MA ~100 (250 dias em 100); banda 5% => zona morta [95, 105]
    close = pd.Series([100.0] * 250 + [110, 103, 104, 90])
    reg = regime_hysteresis(close, 200, band=0.05)
    assert reg[250] == 1.0    # 110 > 105 -> vira bull
    assert reg[251] == 1.0    # 103 dentro da banda -> MANTÉM bull (histerese)
    assert reg[252] == 1.0    # 104 ainda na banda -> mantém
    assert reg[253] == -1.0   # 90 < 95 -> vira bear


def test_cooldown_freezes_short_trades():
    w = np.array([0, 1, 0, 1, 0, 1, 0, 0, 0, 0], dtype=float)  # pipoca
    out = _apply_cooldown(w, min_hold=4)
    # após a 1ª mudança (idx1), congela por 4 dias -> menos transições que o original
    changes_in = np.sum(np.abs(np.diff(w)) > 0)
    changes_out = np.sum(np.abs(np.diff(out)) > 0)
    assert changes_out < changes_in


def test_cooldown_noop_when_min_hold_one():
    w = np.array([0, 1, 0, 1, 0], dtype=float)
    np.testing.assert_array_equal(_apply_cooldown(w, 1), w)


def test_long_only_never_short():
    df = _df(np.concatenate([np.linspace(100, 300, 250), np.linspace(300, 80, 250)]))
    cfg = StrategyConfig(ma_window=200, band=0.03, mode="long_only")
    w = target_weights(df, [10, 20, 30], cfg)
    assert w.min() >= 0.0  # nunca vende a descoberto


def test_long_short_allows_negative_in_bear():
    df = _df(np.concatenate([np.linspace(100, 300, 250), np.linspace(300, 80, 250)]))
    cfg = StrategyConfig(ma_window=200, band=0.03, mode="long_short")
    w = target_weights(df, [10, 20, 30], cfg)
    assert w.min() < 0.0   # short aparece no bear
    assert w.max() > 0.0   # long aparece no bull


def test_invalid_mode_raises():
    import pytest

    df = _df(np.linspace(100, 200, 250))
    with pytest.raises(ValueError):
        target_weights(df, [10], StrategyConfig(mode="xpto"))


def test_atr_positive():
    df = _df(np.concatenate([np.linspace(100, 200, 60), np.linspace(200, 120, 60)]))
    a = atr(df, 22)
    assert np.nanmin(a[30:]) > 0


def test_asymmetric_holds_longer_than_symmetric():
    """Canal de saída mais largo => fica mais tempo long numa tendência com repique."""
    up = np.linspace(100, 200, 120)
    pullback = np.concatenate([up, [195, 188, 182, 190, 205], np.linspace(206, 300, 100)])
    df = _df(pullback)
    sym = donchian_long_asym(df["High"], df["Low"], df["Close"], 20, 20)
    asy = donchian_long_asym(df["High"], df["Low"], df["Close"], 20, 60)  # saída 3x mais larga
    # a versão assimétrica passa pelo menos tanto tempo long quanto a simétrica
    assert asy.sum() >= sym.sum()


def test_ensemble_long_asym_range():
    df = _df(np.linspace(100, 300, 300))
    net = ensemble_long_asym(df, [10, 20, 30], asym=2.0)
    assert net.min() >= 0.0 and net.max() <= 1.0


def test_chandelier_exits_on_drop():
    close = np.array([100, 110, 120, 130, 90, 90, 90], dtype=float)  # topo 130 e despenca
    w = np.ones(len(close))
    atr_arr = np.full(len(close), 5.0)
    out = _chandelier_overlay(w, close, atr_arr, k=3.0)  # stop = topo - 15
    assert out[4] == 0.0       # caiu de 130 p/ 90 (>15) -> stopado
    assert out[-1] == 0.0      # permanece fora (latch) até o sinal zerar


def test_chandelier_off_when_k_zero():
    w = np.ones(5)
    out = _chandelier_overlay(w, np.array([100.0, 90, 80, 70, 60]), np.full(5, 5.0), k=0.0)
    np.testing.assert_array_equal(out, w)


def test_long_asym_mode_long_only():
    df = _df(np.concatenate([np.linspace(100, 300, 250), np.linspace(300, 90, 250)]))
    cfg = StrategyConfig(ma_window=200, band=0.05, mode="long_asym", asym=2.0, atr_k=4.0)
    w = target_weights(df, [10, 20, 30], cfg)
    assert w.min() >= 0.0 and w.max() <= 1.0  # nunca short
