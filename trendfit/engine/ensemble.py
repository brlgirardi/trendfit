"""Ensemble trend-following: posição fracionária por votação entre lookbacks.

Cada lookback é um voto binário (long/fora). A posição-alvo é a FRAÇÃO de
lookbacks que concordam em estar long — de 0.0 a 1.0. Isso suaviza ruído e
reduz overfitting: nenhum parâmetro único decide tudo (1 "knob" diversificado
em vez de N parâmetros otimizados).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trendfit.engine.indicators import STATE_FUNCS


def ensemble_position(
    df: pd.DataFrame,
    lookbacks: list[int],
    kind: str = "donchian",
) -> np.ndarray:
    """Vetor de posição-alvo (0..1) = fração dos lookbacks votando long.

    df: DataFrame com colunas High, Low, Close.
    kind: 'donchian' (validado) ou 'hilo'.
    """
    if kind not in STATE_FUNCS:
        raise ValueError(f"tipo de ensemble desconhecido: {kind!r} (use {list(STATE_FUNCS)})")
    func = STATE_FUNCS[kind]
    high, low, close = df["High"], df["Low"], df["Close"]
    votes = np.zeros(len(df))
    for lb in lookbacks:
        votes += func(high, low, close, lb)
    return votes / len(lookbacks)
