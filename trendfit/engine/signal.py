"""Leitura do sinal atual do sistema (núcleo + veto) para o último dado disponível.

NÃO é recomendação de investimento — é a saída mecânica do sistema na última barra.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trendfit.engine.indicators import STATE_FUNCS
from trendfit.layers.regime import regime_allow


@dataclass
class CurrentSignal:
    date: pd.Timestamp
    price: float
    ensemble_vote: float          # 0..1 (fração de lookbacks long)
    per_lookback: dict[int, bool]
    regime_bull: bool
    ma_value: float
    recommended_weight: float     # voto * veto
    reading: str


def current_signal(
    df: pd.DataFrame,
    lookbacks: list[int],
    kind: str = "donchian",
    ma_window: int = 200,
) -> CurrentSignal:
    func = STATE_FUNCS[kind]
    high, low, close = df["High"], df["Low"], df["Close"]
    per_lb = {}
    votes = 0.0
    for lb in lookbacks:
        st = func(high, low, close, lb)
        long_now = bool(st[-1] > 0)
        per_lb[lb] = long_now
        votes += st[-1]
    vote = votes / len(lookbacks)

    allow = regime_allow(df, ma_window)
    ma = df["Close"].rolling(ma_window).mean().to_numpy()
    bull = bool(allow[-1])
    weight = vote if bull else 0.0

    if weight >= 0.66:
        reading = "COMPRADO forte — tendência confirmada"
    elif weight >= 0.33:
        reading = "PARCIAL — tendência mista"
    elif weight > 0:
        reading = "LEVE — sinal fraco"
    else:
        reading = "FORA — sem tendência de alta confirmada / regime bear"

    return CurrentSignal(
        date=df.index[-1],
        price=float(df["Close"].iloc[-1]),
        ensemble_vote=vote,
        per_lookback=per_lb,
        regime_bull=bull,
        ma_value=float(ma[-1]) if not np.isnan(ma[-1]) else float("nan"),
        recommended_weight=weight,
        reading=reading,
    )
