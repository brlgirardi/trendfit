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
    # critérios EXPLÍCITOS (checklist transparente — é isso que leva ao viés)
    trend_up = slope > 0.005
    criteria = [
        {"label": "Regime (preço vs MA200)", "state": "ok" if regime == "BULL" else "bad",
         "detail": f"{regime} · {dist_ma*100:+.0f}% da MA200",
         "peso": "MANDA na decisão de comprar/vender (trade system)"},
        {"label": "Tendência (inclinação MA)", "state": "ok" if trend_up else "bad" if slope < -0.005 else "warn",
         "detail": "subindo" if trend_up else "caindo" if slope < -0.005 else "lateral",
         "peso": "confirma a força do regime"},
        {"label": f"Valuation ({valuation_label or 'percentil preço'})",
         "state": "ok" if cheap else "bad" if expensive else "warn",
         "detail": f"percentil {val_pct:.0f}% — {'barato' if cheap else 'caro' if expensive else 'neutro'}",
         "peso": "só CONTEXTO de ciclo (testado como regra e refutado — PHASE5); não aciona"},
    ]
    n_ok = sum(1 for c in criteria if c["state"] == "ok")
    # racional: o regime manda no timing; valuation é zona. Explica o que falta.
    if regime == "BULL" and cheap:
        rationale = "Regime a favor + barato: critérios alinhados para ACUMULAR."
    elif regime == "BULL":
        rationale = "Regime a favor, mas não está barato: manter, sem aumentar agressivo."
    elif cheap:
        rationale = "Barato, MAS regime contra (timing). Comprar exige o preço recuperar a MA200 — não pegar faca caindo."
    else:
        rationale = "Regime contra e sem desconto: evitar / aguardar."
    return {"name": name, "price": p, "regime": regime, "slope": slope, "dist_ma": dist_ma,
            "price_pct": price_pct, "val_pct": val_pct,
            "val_label": valuation_label or "percentil preço (proxy)",
            "bias": bias, "criteria": criteria, "n_ok": n_ok, "rationale": rationale,
            "asof": close.index[-1].date()}


def environment_fragility(views: list[dict]) -> tuple[str, str]:
    """Heurística de fragilidade do ambiente a partir das views (não previsão)."""
    by = {v["name"]: v for v in views}
    spx_hot = by.get("SP500", {}).get("price_pct", 0) > 90
    btc_bear = by.get("BTC", {}).get("regime") == "BEAR"
    level = "ELEVADA" if (spx_hot and btc_bear) else "MODERADA" if (spx_hot or btc_bear) else "BAIXA"
    why = f"SP500 percentil {by.get('SP500', {}).get('price_pct', float('nan')):.0f}% · BTC {by.get('BTC', {}).get('regime', '—')}"
    return level, why
