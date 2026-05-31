"""Vol-targeting (Fase 3b) — dimensiona a posição pela volatilidade realizada.

NÃO prevê direção: só ajusta o TAMANHO para mirar uma volatilidade-alvo constante.
Quando a vol realizada dispara (tipicamente pré-crash / pânico), o fator cai e corta
exposição; quando a tendência é calma, mantém. É a alavanca de gestão de risco mais
robusta em trend-following — melhora o retorno ajustado a risco sem tentar adivinhar topo.

Causal e sem look-ahead: a vol usa retornos passados e entra com shift(1) (no dia i só
enxerga o que fechou até i-1). O alvo/janela são escolhidos só no treino (dimensão do grid).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 365  # cripto: 24/7


def realized_vol(close: pd.Series, window: int) -> pd.Series:
    """Volatilidade anualizada dos log-retornos numa janela móvel (causal)."""
    r = np.log(close).diff()
    return r.rolling(window).std() * np.sqrt(TRADING_DAYS)


def vol_target_factor(
    df: pd.DataFrame,
    target_vol: float,
    window: int = 20,
    cap: float = 1.0,
    floor: float = 0.0,
) -> np.ndarray:
    """Fator de escala em [floor, cap] = target_vol / vol_realizada (clipado).

    cap=1.0 (default) => SEM alavancagem: o fator só REDUZ a exposição quando a vol está
    acima do alvo. Sem dado suficiente (início) => cap (não sufoca a posição sem info).
    """
    rv = realized_vol(df["Close"], window).shift(1)  # causal
    scale = (target_vol / rv).clip(lower=floor, upper=cap)
    return scale.fillna(cap).to_numpy()
