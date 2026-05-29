import pandas as pd

from trendfit.engine.signal import position_events


def _series(vals):
    idx = pd.date_range("2022-01-01", periods=len(vals), freq="D", tz="UTC")
    return pd.Series(vals, index=idx)


def test_position_events_classifies_transitions():
    w = _series([0.0, 0.0, 0.33, 0.66, 1.0, 1.0, 0.5, 0.0, 0.0])
    price = _series([100, 101, 102, 103, 104, 105, 106, 107, 108])
    ev = position_events(w, price)
    kinds = ev["kind"].tolist()
    assert kinds[0] == "entry"        # 0 -> 0.33
    assert "scale_in" in kinds        # 0.33 -> 0.66, 0.66 -> 1.0
    assert "scale_out" in kinds       # 1.0 -> 0.5
    assert kinds[-1] == "exit"        # 0.5 -> 0.0
    # cada evento carrega preço e label
    assert ev["price"].notna().all()
    assert ev["label"].str.contains("%").all()


def test_position_events_ignores_flat_periods():
    # começa long (1 entrada no dia 1) e depois fica flat -> nenhum evento adicional
    w = _series([1.0, 1.0, 1.0, 1.0])
    price = _series([100, 110, 120, 130])
    ev = position_events(w, price)
    assert len(ev) == 1
    assert ev["kind"].iloc[0] == "entry"


def test_position_events_threshold():
    w = _series([0.0, 0.005, 0.5])  # 0.005 está abaixo do threshold default (0.01)
    price = _series([100, 100, 100])
    ev = position_events(w, price)
    assert len(ev) == 1  # só a transição 0.005 -> 0.5 conta
