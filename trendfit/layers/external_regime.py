"""Camadas externas de regime (Fase 2): macro + sentimento, SEM look-ahead.

Cada série externa (F&G, VIX, DXY, 10Y, ouro) é alinhada ao índice diário do ativo
com `reindex(..., method="ffill").shift(1)`:
  - ffill: usa o último valor conhecido (séries macro não têm fim de semana).
  - shift(1): no dia *i* só enxerga o que estava disponível ATÉ o fechamento de *i-1*.
Isso elimina look-ahead (o dado de hoje não decide a posição de hoje).

Cada camada vira um sinal booleano `risk_on` (regime externo permite exposição).
A combinação com o veto MA200 (layers/regime.py) é validada no walk-forward — só
entra a camada que melhorar o OOS. Nenhuma camada é gerador de sinal: só filtra.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trendfit.data.external import load_series


def align_external(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Alinha uma série externa ao índice do ativo sem look-ahead (ffill + shift(1))."""
    if series.empty:
        return pd.Series(np.nan, index=index)
    idx_norm = index.normalize()
    aligned = series.reindex(idx_norm, method="ffill").shift(1)
    aligned.index = index
    return aligned


def _trend_up(s: pd.Series, window: int) -> pd.Series:
    """True quando a série está acima da própria média móvel (tendência de alta)."""
    return s > s.rolling(window).mean()


def external_signals(db_path, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Monta o DataFrame de sinais externos booleanos `risk_on` por camada, alinhado
    ao índice do ativo e sem look-ahead. Colunas: fng, vix, dxy, us10y, gold_rel.

    Convenções (risk_on = True libera exposição):
      - fng:    Fear & Greed acima de 25 (evita pânico extremo) — contrário a euforia
                não é filtrado aqui; o núcleo de tendência já corta euforia ao reverter.
      - vix:    VIX abaixo da própria MA (volatilidade não disparando = risk-on).
      - dxy:    Dólar NÃO em alta forte (DXY abaixo da própria MA) — dólar subindo
                costuma pressionar ativos de risco.
      - us10y:  Juros 10A NÃO disparando (abaixo da própria MA).
      - gold_rel: contexto informativo (ouro subindo) — não usado como veto por padrão.
    """
    fng = align_external(load_series(db_path, "fng"), index)
    vix = align_external(load_series(db_path, "vix"), index)
    dxy = align_external(load_series(db_path, "dxy"), index)
    us10y = align_external(load_series(db_path, "us10y"), index)
    gold = align_external(load_series(db_path, "gold"), index)

    out = pd.DataFrame(index=index)
    out["fng"] = fng > 25
    out["vix"] = ~_trend_up(vix, 20)            # VIX não em alta = risk-on
    out["dxy"] = ~_trend_up(dxy, 50)            # dólar não em alta = risk-on
    out["us10y"] = ~_trend_up(us10y, 50)        # juros não disparando = risk-on
    out["gold_rel"] = _trend_up(gold, 50)       # informativo
    # onde não há dado (início da série), default conservador: NÃO bloqueia (True),
    # para a camada externa só ATUAR quando há informação real.
    return out.fillna(True)


def composite_allow(
    db_path,
    index: pd.DatetimeIndex,
    layers: list[str],
) -> np.ndarray:
    """Veto externo combinado: risk_on = E lógico das camadas escolhidas.
    Retorna vetor booleano alinhado ao índice. Lista vazia -> tudo True (sem filtro)."""
    if not layers:
        return np.ones(len(index), dtype=bool)
    sig = external_signals(db_path, index)
    allow = np.ones(len(index), dtype=bool)
    for name in layers:
        allow &= sig[name].to_numpy()
    return allow
