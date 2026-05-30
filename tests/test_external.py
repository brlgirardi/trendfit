import numpy as np
import pandas as pd

from trendfit.data import external as ext
from trendfit.layers.external_regime import align_external, composite_allow, external_signals


def _seed(db, name, dates, values):
    conn = ext._conn(db)
    rows = [(int(pd.Timestamp(d, tz="UTC").timestamp() * 1000), v) for d, v in zip(dates, values)]
    ext._upsert(conn, name, rows, "test")
    conn.close()


def test_load_series_roundtrip(tmp_path):
    db = tmp_path / "x.sqlite"
    _seed(db, "dxy", ["2021-01-01", "2021-01-02", "2021-01-03"], [100, 101, 99])
    s = ext.load_series(db, "dxy")
    assert len(s) == 3
    assert s.iloc[0] == 100 and s.iloc[-1] == 99


def test_load_series_empty(tmp_path):
    assert ext.load_series(tmp_path / "e.sqlite", "vix").empty


def test_align_external_no_lookahead(tmp_path):
    """O valor alinhado no dia i deve ser o do dia i-1 (shift(1)) — sem ver o futuro."""
    db = tmp_path / "a.sqlite"
    dates = pd.date_range("2021-01-01", periods=5, freq="D")
    _seed(db, "dxy", [d.strftime("%Y-%m-%d") for d in dates], [10, 20, 30, 40, 50])
    idx = pd.date_range("2021-01-01", periods=5, freq="D", tz="UTC")
    aligned = align_external(ext.load_series(db, "dxy"), idx)
    # dia 0 não tem passado -> NaN; dia 1 vê o valor do dia 0 (=10); dia 4 vê o do dia 3 (=40)
    assert np.isnan(aligned.iloc[0])
    assert aligned.iloc[1] == 10
    assert aligned.iloc[4] == 40


def test_composite_allow_is_and(tmp_path):
    db = tmp_path / "c.sqlite"
    idx = pd.date_range("2021-01-01", periods=120, freq="D", tz="UTC")
    ds = [d.strftime("%Y-%m-%d") for d in idx]
    # dxy subindo o tempo todo -> _trend_up True -> risk_on (~trend_up) False na maior parte
    _seed(db, "dxy", ds, list(np.linspace(100, 200, 120)))
    allow = composite_allow(db, idx, ["dxy"])
    assert allow.dtype == bool and len(allow) == len(idx)
    # com dólar em alta forte, a camada deve vetar (False) em boa parte do período
    assert allow.sum() < len(idx)


def test_composite_allow_empty_layers_all_true(tmp_path):
    idx = pd.date_range("2021-01-01", periods=10, freq="D", tz="UTC")
    allow = composite_allow(tmp_path / "n.sqlite", idx, [])
    assert allow.all()


def test_external_signals_columns(tmp_path):
    db = tmp_path / "s.sqlite"
    idx = pd.date_range("2021-01-01", periods=60, freq="D", tz="UTC")
    ds = [d.strftime("%Y-%m-%d") for d in idx]
    for name in ["fng", "vix", "dxy", "us10y", "gold"]:
        _seed(db, name, ds, list(np.linspace(20, 80, 60)))
    sig = external_signals(db, idx)
    assert set(["fng", "vix", "dxy", "us10y", "gold_rel"]).issubset(sig.columns)
    assert sig.dtypes.apply(lambda d: d == bool).all()
