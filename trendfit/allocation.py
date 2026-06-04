"""Agente de Alocação — classificação de regime + valuation por ativo (NÃO previsão).

Camada de AGREGAÇÃO da Fase 4 (multi-ativo). Para cada ativo, classifica regime de
tendência (preço vs MA200 + inclinação) e posição no range/valuation. O 'viés' é uma
HEURÍSTICA transparente, ainda NÃO validada OOS — contexto, não ordem.
"""

from __future__ import annotations

import pandas as pd


def asset_view(name: str, close: pd.Series, valuation_pct: float | None = None,
               valuation_label: str = "") -> dict:
    """Classifica um ativo a partir da série de fechamento. Retorna dict com regime,
    distância da MA200, percentil de preço, valuation (% — proxy se não houver fundamental)
    e um viés heurístico (não validado)."""
    close = close.dropna()
    if len(close) < 210:
        return {"name": name, "price": float(close.iloc[-1]) if len(close) else float("nan"),
                "regime": "—", "slope": 0.0, "dist_ma": 0.0, "price_pct": float("nan"),
                "val_pct": float("nan"), "val_label": "histórico insuficiente",
                "bias": "—", "asof": close.index[-1].date() if len(close) else None}
    p = float(close.iloc[-1])
    ma200 = close.rolling(200).mean()
    regime = "BULL" if p > ma200.iloc[-1] else "BEAR"
    slope = ma200.iloc[-1] / ma200.iloc[-21] - 1
    dist_ma = p / ma200.iloc[-1] - 1
    price_pct = float((close < p).mean() * 100)
    val_pct = price_pct if valuation_pct is None else valuation_pct
    cheap, expensive = val_pct < 35, val_pct > 70
    if regime == "BULL" and cheap:
        bias = "ACUMULAR (barato + tendência)"
    elif regime == "BULL" and expensive:
        bias = "MANTER c/ cautela (caro, mas em alta)"
    elif regime == "BEAR" and cheap:
        bias = "ZONA DE INTERESSE (barato; aguardar virada)"
    elif regime == "BEAR" and expensive:
        bias = "EVITAR (caro + tendência de baixa)"
    else:
        bias = "NEUTRO"
    return {"name": name, "price": p, "regime": regime, "slope": slope, "dist_ma": dist_ma,
            "price_pct": price_pct, "val_pct": val_pct,
            "val_label": valuation_label or "percentil preço (proxy)",
            "bias": bias, "asof": close.index[-1].date()}


def environment_fragility(views: list[dict]) -> tuple[str, str]:
    """Heurística de fragilidade do ambiente a partir das views (não previsão)."""
    by = {v["name"]: v for v in views}
    spx_hot = by.get("SP500", {}).get("price_pct", 0) > 90
    btc_bear = by.get("BTC", {}).get("regime") == "BEAR"
    level = "ELEVADA" if (spx_hot and btc_bear) else "MODERADA" if (spx_hot or btc_bear) else "BAIXA"
    why = f"SP500 percentil {by.get('SP500', {}).get('price_pct', float('nan')):.0f}% · BTC {by.get('BTC', {}).get('regime', '—')}"
    return level, why
