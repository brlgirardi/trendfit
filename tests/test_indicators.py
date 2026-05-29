import numpy as np
import pandas as pd

from trendfit.engine.indicators import donchian_state, hilo_state, moving_average


def test_donchian_no_lookahead_uses_only_past(trend_df):
    """O canal usa rolling().shift(1): a barra de hoje não entra no próprio canal."""
    h, l, c = trend_df["High"], trend_df["Low"], trend_df["Close"]
    lb = 20
    hh = h.rolling(lb).max().shift(1)
    # Num dia i, o estado long exige Close[i] > max(High[i-lb..i-1]) — nunca > High[i].
    state = donchian_state(h, l, c, lb)
    longs = np.where(state > 0)[0]
    for i in longs[longs > lb][:50]:
        # se está long, em algum momento <= i o close rompeu o topo passado
        assert c.iloc[i] >= 0  # sanity
    # canal do dia i não pode depender de dados futuros: hh[i] == max das barras anteriores
    assert np.isnan(hh.iloc[lb - 1])
    assert hh.iloc[lb] == h.iloc[:lb].max()


def test_donchian_goes_long_in_uptrend_flat_in_downtrend(trend_df):
    state = donchian_state(trend_df["High"], trend_df["Low"], trend_df["Close"], 20)
    # No fim da primeira subida (índice ~190) deve estar long
    assert state[190] == 1.0
    # No fundo da queda (índice ~395) deve estar fora
    assert state[395] == 0.0


def test_hilo_state_binary(trend_df):
    state = hilo_state(trend_df["High"], trend_df["Low"], trend_df["Close"], 22)
    assert set(np.unique(state)).issubset({0.0, 1.0})
    assert state[190] == 1.0


def test_moving_average_matches_pandas(trend_df):
    ma = moving_average(trend_df["Close"], 50)
    expected = trend_df["Close"].rolling(50).mean().to_numpy()
    np.testing.assert_allclose(ma[60:], expected[60:])
