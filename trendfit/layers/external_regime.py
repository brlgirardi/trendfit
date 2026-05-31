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


def exposure_factor(
    db_path,
    index: pd.DatetimeIndex,
    signal: str,
    *,
    z_window: int = 90,
    z_hi: float = 1.5,
    floor: float = 0.4,
    direction: str = "high_bad",
) -> np.ndarray:
    """Fator CONTÍNUO de exposição em [floor, 1] a partir de uma série externa (Fase 3).

    Correção da Fase 2 (que zerava posição por veto AND): aqui o sinal só MODULA o
    tamanho. Usa z-score rolling causal (a série já entra com ffill+shift(1), sem
    look-ahead). Quando o z passa de `z_hi`, a exposição cai linearmente de 1 até `floor`
    ao longo de 1 desvio-padrão e satura.

    direction:
      - 'high_bad': reduz quando a série está ALTA (funding/MVRV em euforia = fragilidade).
      - 'low_bad':  reduz quando a série está BAIXA.
    Sem dado (início da série) -> fator 1.0 (não atua sem informação real).
    """
    s = align_external(load_series(db_path, signal), index)  # ffill + shift(1)
    mp = max(2, z_window // 2)
    mu = s.rolling(z_window, min_periods=mp).mean()
    sd = s.rolling(z_window, min_periods=mp).std()
    z = (s - mu) / sd
    if direction == "low_bad":
        z = -z
    reduce = (z - z_hi).clip(lower=0.0).clip(upper=1.0)  # 0..1 ao longo de 1 sigma
    factor = 1.0 - reduce * (1.0 - floor)
    return factor.fillna(1.0).to_numpy()


def macro_factor(
    db_path,
    index: pd.DatetimeIndex,
    layers: list[str],
    *,
    floor: float = 0.4,
) -> np.ndarray:
    """Versão MODULADORA do veto macro (Fase 3): em vez de zerar por E lógico, reduz a
    exposição proporcionalmente à fração de camadas em risk-off. Todas risk-on -> 1.0;
    todas risk-off -> floor. Reaproveita os sinais de external_signals (sem look-ahead)."""
    if not layers:
        return np.ones(len(index), dtype=float)
    sig = external_signals(db_path, index)
    frac_on = sig[layers].mean(axis=1).to_numpy()  # 0..1
    return floor + (1.0 - floor) * frac_on


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
