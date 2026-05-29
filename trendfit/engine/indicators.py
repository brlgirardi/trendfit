"""Indicadores base, vetorizados e SEM look-ahead.

Regra anti-look-ahead: todo canal/ruptura usa `.shift(1)` no rolling — a decisão
do dia *i* só enxerga dados até o fechamento de *i-1*. O retorno é sempre aplicado
ao peso do dia anterior (ver engine.backtest), fechando qualquer vazamento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def donchian_state(high: pd.Series, low: pd.Series, close: pd.Series, lookback: int) -> np.ndarray:
    """Estado Donchian breakout (1=long, 0=fora) para um lookback.

    Entra long quando o close rompe a máxima dos últimos `lookback` dias (excl. hoje);
    sai quando rompe a mínima. Mantém o estado entre rupturas (stop-and-reverse parcial).
    """
    hh = high.rolling(lookback).max().shift(1).to_numpy()
    ll = low.rolling(lookback).min().shift(1).to_numpy()
    c = close.to_numpy()
    state = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if not np.isnan(hh[i]) and c[i] > hh[i]:
            cur = 1.0
        elif not np.isnan(ll[i]) and c[i] < ll[i]:
            cur = 0.0
        state[i] = cur
    return state


def hilo_state(high: pd.Series, low: pd.Series, close: pd.Series, lookback: int) -> np.ndarray:
    """Estado HiLo Activator (1=long, 0=fora) — variante do núcleo (réplica da lógica AFL).

    Close > MA(High, lb) -> bull; Close <= MA(Low, lb) -> bear; senão mantém.
    """
    ma_h = high.rolling(lookback).mean().shift(1).to_numpy()
    ma_l = low.rolling(lookback).mean().shift(1).to_numpy()
    c = close.to_numpy()
    state = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if not np.isnan(ma_h[i]) and c[i] > ma_h[i]:
            cur = 1.0
        elif not np.isnan(ma_l[i]) and c[i] <= ma_l[i]:
            cur = 0.0
        state[i] = cur
    return state


def moving_average(close: pd.Series, window: int) -> np.ndarray:
    """Média móvel simples. (Sem shift: usada como referência de regime, ver layers.regime.)"""
    return close.rolling(window).mean().to_numpy()


# Mapa de geradores de estado disponíveis para o ensemble.
STATE_FUNCS = {
    "donchian": donchian_state,
    "hilo": hilo_state,
}
