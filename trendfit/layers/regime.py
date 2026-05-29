"""Veto de regime v1: preço vs média móvel longa (proxy macro bull/bear).

Esta é a versão mais simples do filtro de contexto descrito no PRD. A IA das
fases 2/3 (MVRV, fluxo de ETF, NLP de notícias) substitui/enriquece este proxy,
mas a interface permanece: devolve um vetor booleano `allow` (True = regime
permite exposição long).

Importante: o veto é um FILTRO de contexto, não um gerador de sinal. Ele só pode
zerar/reduzir a posição que o núcleo já propôs — nunca criar uma posição.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def regime_allow(df: pd.DataFrame, ma_window: int = 200) -> np.ndarray:
    """Vetor booleano: True quando Close > MA(Close, ma_window) — regime bull macro.

    Dias antes de haver janela suficiente para a MA ficam False (sem exposição),
    o que é conservador e evita operar sem contexto de regime definido.
    """
    ma = df["Close"].rolling(ma_window).mean().to_numpy()
    close = df["Close"].to_numpy()
    allow = close > ma
    allow[np.isnan(ma)] = False
    return allow
