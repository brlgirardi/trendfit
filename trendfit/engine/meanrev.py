"""Estratégia mean-reversion (range) — alternativa selecionável ao trend (anti-viés).

Long-only, causal: compra quando o preço está oversold (z-score abaixo de z_buy) e reduz
quando overbought (acima de z_sell), via banda de Bollinger sobre SMA(window). É a
estratégia natural para mercado LATERAL; perde em tendências fortes (ver docs/REGIME_ANALYSIS.md).

NÃO é o default — existe como contraponto medido, para o projeto não ficar enviesado num
único estilo. Validada OOS (params escolhidos só no treino) em scripts/validate_meanrev.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def meanrev_weights(close: pd.Series, window: int = 20, z_buy: float = -1.0,
                    z_sell: float = 1.0, floor: float = 0.0) -> pd.Series:
    """Peso long-only em [floor, 1] por z-score de Bollinger. z<=z_buy -> 1 (oversold),
    z>=z_sell -> floor (overbought), linear no meio. Série causal (o uso aplica shift(1))."""
    sma = close.rolling(window).mean()
    sd = close.rolling(window).std()
    z = (close - sma) / sd
    expo = ((z_sell - z) / (z_sell - z_buy)).clip(lower=floor, upper=1.0)
    return expo.fillna(0.0)
