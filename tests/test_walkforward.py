import numpy as np
import pandas as pd
import pytest

from trendfit.engine.walkforward import walk_forward
from trendfit.engine.signal import current_signal


@pytest.fixture
def long_df():
    """~6 anos de série sintética com ciclos, suficiente p/ treino 4a + 1-2 testes."""
    n = 365 * 6
    idx = pd.date_range("2017-01-01", periods=n, freq="D", tz="UTC")
    t = np.arange(n)
    # tendência de alta com ciclos senoidais (sobe, corrige, sobe)
    close = 100 * np.exp(0.0006 * t) * (1 + 0.3 * np.sin(t / 120))
    df = pd.DataFrame(index=idx)
    df["Close"] = close
    df["Open"] = df["Close"].shift(1).fillna(df["Close"])
    df["High"] = df[["Open", "Close"]].max(axis=1) * 1.001
    df["Low"] = df[["Open", "Close"]].min(axis=1) * 0.999
    df["Volume"] = 1.0
    return df


def test_walk_forward_runs_and_has_benchmark(long_df):
    wf = walk_forward(long_df, train_days=365 * 4, test_days=365)
    assert wf.oos_period is not None
    assert wf.benchmark.n_days > 0
    assert "total_return" in wf.oos_metrics
    assert isinstance(wf.beat_buy_and_hold, bool)
    assert isinstance(wf.veto_helped, bool)
    assert len(wf.steps) >= 1
    # benchmark cobre exatamente o mesmo período OOS (sem costura/off-by-one)
    assert wf.benchmark.n_days == wf.oos_metrics["n_days"]


def test_walk_forward_selection_only_uses_known_configs(long_df):
    wf = walk_forward(long_df, train_days=365 * 4, test_days=365)
    for step in wf.steps:
        assert step.chosen in {"curto", "medio", "longo", "amplo"}


def test_walk_forward_strategy_runs(long_df):
    from trendfit.engine.strategy import StrategyConfig
    from trendfit.engine.walkforward import walk_forward_strategy

    cfg = StrategyConfig(ma_window=200, band=0.05, mode="long_only", min_hold=5)
    wf = walk_forward_strategy(long_df, cfg, train_days=365 * 4, test_days=365)
    assert wf.benchmark.n_days == wf.oos_metrics["n_days"]
    assert len(wf.steps) >= 1
    assert isinstance(wf.beat_buy_and_hold, bool)


def test_walk_forward_grid_selects_on_train(long_df):
    from trendfit.engine.strategy import StrategyConfig
    from trendfit.engine.walkforward import walk_forward_grid

    cands = []
    for asym in (1.0, 2.0):
        cfg = StrategyConfig(ma_window=200, band=0.05, mode="long_asym", asym=asym)
        cands.append((f"a{asym}", [10, 20, 30], cfg))
    wf = walk_forward_grid(long_df, cands, train_days=365 * 4, test_days=365)
    assert wf.benchmark.n_days == wf.oos_metrics["n_days"]
    assert len(wf.steps) >= 1
    assert all(s.chosen in {"a1.0", "a2.0"} for s in wf.steps)


def test_walk_forward_strategy_long_short_can_go_negative(long_df):
    from trendfit.engine.strategy import StrategyConfig
    from trendfit.engine.walkforward import walk_forward_strategy

    cfg = StrategyConfig(ma_window=200, band=0.03, mode="long_short")
    wf = walk_forward_strategy(long_df, cfg, train_days=365 * 4, test_days=365)
    assert wf.oos_weights.min() <= 0.0  # permite caixa/short


def test_walk_forward_insufficient_history_raises(long_df):
    small = long_df.iloc[:300]
    with pytest.raises(ValueError):
        walk_forward(small, train_days=365 * 4, test_days=365)


def test_current_signal_fields(long_df):
    sig = current_signal(long_df, [10, 20, 30], "donchian", 200)
    assert 0.0 <= sig.ensemble_vote <= 1.0
    assert 0.0 <= sig.recommended_weight <= 1.0
    assert sig.reading
