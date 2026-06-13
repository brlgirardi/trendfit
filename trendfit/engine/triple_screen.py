"""Triple Screen com o NOSSO motor — experimento apartado (k=3 intocado).

A estrutura de Alexander Elder (várias telas em timeframes diferentes), mas usando
o ENSEMBLE trend-following do TrendFit em cada tela, em vez dos osciladores do Elder
— essa é a "ideia pegada" do Bruno: nosso sistema em triple screen.

  Tela 1 — MARÉ (semanal): ensemble Donchian define a direção permitida. Causal
           (defasada 1 semana: só usa a semana fechada).
  Tela 2 — SINAL (diário): ensemble Donchian dá a exposição fracionária (0..1).
  Tela 3 — ENTRADA (intraday): [FUTURO] afina o ponto — precisa do coletor intraday.

  weight = exposição_diária  SE a maré semanal permite  SENÃO 0.

LINHA VERMELHA / regra-mãe:
- Apartado: NÃO toca o engine k=3, não vira o sinal oficial. Só entra em produção se
  o WFA CEGO (params escolhidos só no treino) bater o k=3 — "rodar seco não vale".
- Sem look-ahead: maré semanal defasada (shift). Validado por teste de causalidade.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trendfit.engine.ensemble import ensemble_position


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Reamostra OHLC diário para semanal (W-SUN)."""
    agg = {
        "Open": df["Open"].resample("W").first() if "Open" in df else df["Close"].resample("W").first(),
        "High": df["High"].resample("W").max() if "High" in df else df["Close"].resample("W").max(),
        "Low": df["Low"].resample("W").min() if "Low" in df else df["Close"].resample("W").min(),
        "Close": df["Close"].resample("W").last(),
    }
    return pd.DataFrame(agg).dropna()


def weekly_tide(df: pd.DataFrame, weekly_lookbacks: list[int],
                threshold: float = 0.5, kind: str = "donchian") -> np.ndarray:
    """Tela 1 — maré semanal CAUSAL: fração do ensemble semanal long >= threshold.

    Calcula o ensemble no semanal, defasa 1 semana (shift) e reindexa ao diário —
    cada dia só enxerga a maré da última semana já encerrada (sem look-ahead)."""
    wk = resample_weekly(df)
    if len(wk) <= max(weekly_lookbacks) + 1:
        return np.zeros(len(df), dtype=bool)
    frac = ensemble_position(wk, weekly_lookbacks, kind)
    up = pd.Series(frac >= threshold, index=wk.index).shift(1).fillna(False)
    daily = up.reindex(df.index, method="ffill").fillna(False)
    return daily.to_numpy().astype(bool)


def triple_screen_weights(df: pd.DataFrame, weekly_lookbacks: list[int],
                          daily_lookbacks: list[int], threshold: float = 0.5,
                          kind: str = "donchian") -> np.ndarray:
    """Vetor de exposição 0..1 alinhado ao df. Decisão do dia i usa só dados até i
    (o backtest aplica o peso ao retorno de i+1) — causal."""
    tide = weekly_tide(df, weekly_lookbacks, threshold, kind)
    daily = ensemble_position(df, daily_lookbacks, kind)
    return np.where(tide, daily, 0.0)
