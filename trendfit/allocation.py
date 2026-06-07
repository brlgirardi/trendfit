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


# === Buffett Jr — ambiente macro (global) + postura por ativo ========================
# Filosofia: o que o Buffett faz — critérios explícitos -> leitura do PRESENTE -> postura.
# DOIS EIXOS separados: TIMING (regime, validado OOS, MANDA no comprado/fora) e POSTURA
# (valuation/sentimento/alavancagem/macro, NÃO validado, só margem de segurança).
# REGRA DE OURO: a postura INFORMA, o regime DECIDE — nunca altera o sinal nem o tamanho.
# LINHA VERMELHA: tudo é leitura do presente; jamais probabilidade ou "vai até X".

def _direction(chg: float | None, up_is_good: bool, hi: float) -> tuple[str, str]:
    """Direção de uma série (subindo/caindo/estável) + estado de risco (ok/bad/warn)."""
    if chg is None:
        return "—", "warn"
    if chg > hi:
        return "subindo", ("ok" if up_is_good else "bad")
    if chg < -hi:
        return "caindo", ("bad" if up_is_good else "ok")
    return "estável", "warn"


def environment_read(ctx: dict) -> dict:
    """Leitura do AMBIENTE macro NO PRESENTE (não previsão): juros (10Y), risco de
    mercado (VIX), dólar (DXY) e sentimento (Fear&Greed). Classifica o pano de fundo
    como FAVORÁVEL / MISTO / ADVERSO a ativos de risco — descrição do regime macro
    ATUAL, jamais aposta de direção. Limiares explícitos e editáveis.

    ctx: dict já formatado pelo chamador (sem acesso a DB aqui). Chaves opcionais:
    us10y, us10y_chg (var. 21d, pp), vix, dxy_chg (var. 21d, fração), fng (0-100)."""
    notes, score = [], 0

    def _tally(state):
        return 1 if state == "ok" else -1 if state == "bad" else 0

    y, ych = ctx.get("us10y"), ctx.get("us10y_chg")
    if y is not None:
        direc, st = _direction(ych, up_is_good=False, hi=0.05)  # juros caindo = alívio p/ risco
        score += _tally(st)
        notes.append({"label": "Juros 10Y (EUA)", "state": st, "detail": f"{y:.2f}% · {direc}"})
    vix = ctx.get("vix")
    if vix is not None:
        st = "ok" if vix < 20 else "warn" if vix < 28 else "bad"
        score += _tally(st)
        cl = "calmo" if vix < 20 else "atenção" if vix < 28 else "estresse"
        notes.append({"label": "Risco de mercado (VIX)", "state": st, "detail": f"{vix:.0f} · {cl}"})
    dch = ctx.get("dxy_chg")
    if dch is not None:
        direc, st = _direction(dch, up_is_good=False, hi=0.01)  # dólar forte = headwind p/ risco
        score += _tally(st)
        notes.append({"label": "Dólar (DXY)", "state": st, "detail": f"{direc} (21d {dch*100:+.0f}%)"})
    fng = ctx.get("fng")
    if fng is not None:
        st = "ok" if fng < 25 else "bad" if fng > 75 else "warn"  # contrarian: medo=chance, euforia=risco
        score += _tally(st)
        lab = ("medo extremo" if fng < 25 else "medo" if fng < 45 else "neutro"
               if fng < 55 else "ganância" if fng < 75 else "euforia")
        notes.append({"label": "Sentimento (Fear&Greed)", "state": st, "detail": f"{fng:.0f} · {lab}"})

    level = "FAVORÁVEL" if score >= 2 else "ADVERSO" if score <= -2 else "MISTO"
    rationale = {
        "FAVORÁVEL": "Pano de fundo de baixo atrito para risco (juros/dólar/volatilidade alinhados). "
                     "Não é garantia de alta — é só o ambiente atual.",
        "MISTO": "Sinais macro cruzados: parte favorece risco, parte pesa contra. Sem viés claro — "
                 "deixar o regime de cada ativo mandar.",
        "ADVERSO": "Pano de fundo de atrito para risco (aperto/estresse/euforia). NÃO é previsão de "
                   "queda — é leitura de que a margem de segurança pesa mais agora.",
    }[level]
    color = {"FAVORÁVEL": "#16a34a", "MISTO": "#f59e0b", "ADVERSO": "#ef4444"}[level]
    return {"level": level, "score": score, "notes": notes, "rationale": rationale, "color": color}


def asset_posture(view: dict, ctx: dict | None = None, env: dict | None = None) -> dict:
    """POSTURA por ativo (Buffett Jr): combina TIMING (regime, validado — manda no
    comprado/fora) com CONTEXTO (valuation/sentimento/alavancagem/ambiente) e sintetiza
    margem de segurança em ACUMULAR / NEUTRO / CAUTELOSO / DEFENSIVO + racional escrito
    + cenários CONDICIONAIS (gatilhos objetivos do presente, nunca probabilidade).

    REGRA DE OURO: a postura INFORMA, o regime DECIDE. Nunca altera o sinal nem o
    tamanho — só descreve quão agressivo/defensivo faz sentido estar DENTRO do que o
    regime já permite. ctx: dict opcional {fng, funding}; env: saída de environment_read."""
    ctx = ctx or {}
    regime = view.get("regime")
    val = view.get("val_pct")
    has_val = val is not None and val == val
    cheap = has_val and val < 35
    expensive = has_val and val > 70
    val_extreme = has_val and val >= 90   # caro em EXTREMO histórico (ex CAPE no nível de 2000)
    fng = ctx.get("fng")
    funding = ctx.get("funding")
    greed = fng is not None and fng > 75
    funding_hot = funding is not None and funding > 0.0005  # ~0,05%/dia => alavancagem esticada
    adverse = env is not None and env.get("level") == "ADVERSO"

    if regime == "BULL":
        if expensive and (greed or funding_hot or val_extreme):
            posture = "CAUTELOSO"
            if val_extreme and not (greed or funding_hot):
                why = ("Comprado pelo timing, mas valuation em EXTREMO histórico (margem de segurança "
                       "pesa): manter sem aumentar agressivo. O regime ainda MANDA no comprado/fora — "
                       "valuation só informa, NUNCA vende (PHASE5 refutou vender por valuation).")
            else:
                why = "Comprado pelo timing, mas caro + euforia/alavancagem esticada: manter, evitar aumentar perto do topo."
        elif cheap and not adverse:
            posture = "ACUMULAR"
            why = "Regime a favor e valuation com desconto, sem euforia: ambiente para construir posição."
        elif adverse:
            posture = "NEUTRO"
            why = "Comprado pelo regime, mas pano de fundo macro adverso: manter sem aumentar agressivo."
        else:
            posture = "NEUTRO"
            why = "Comprado pelo regime, valuation/contexto sem extremo: manter a posição que o sistema indica."
    elif regime == "BEAR":
        if cheap:
            posture = "CAUTELOSO"
            why = ("Fora pelo timing (regime de baixa), MAS barato: zona de interesse. Agir só quando o "
                   "preço recuperar a MA200 — não pegar faca caindo.")
        else:
            posture = "DEFENSIVO"
            why = "Fora pelo timing e sem desconto: aguardar a virada de regime antes de qualquer compra."
    else:
        posture, why = "—", "Histórico insuficiente para postura."

    # Cenários CONDICIONAIS — gatilhos objetivos do presente (não probabilidade).
    price, dist = view.get("price"), view.get("dist_ma")
    scenarios = []
    if price and dist is not None and dist == dist:
        ma200 = price / (1 + dist)
        gap = (ma200 / price - 1) * 100
        if regime == "BEAR":
            scenarios.append(f"SE recuperar a MA200 (~${ma200:,.0f}, {gap:+.0f}% daqui) com valuation "
                             f"não-caro → postura migra p/ ACUMULAR e o sistema volta a comprar.")
            scenarios.append("ENQUANTO abaixo da MA200, o timing segue FORA — barato sozinho não é compra "
                             "(PHASE5: valuation refutado como gatilho).")
        elif regime == "BULL":
            scenarios.append(f"SE perder a MA200 (~${ma200:,.0f}, {gap:+.0f}% daqui) → regime vira BEAR e o "
                             f"sistema zera a posição (timing manda).")
            if val_extreme:
                scenarios.append("Valuation em extremo histórico ≠ venda: a PHASE5 mostrou que vender por "
                                 "valuation cedo destrói retorno. É margem de segurança (postura); o timing "
                                 "segue o regime.")
            elif expensive:
                scenarios.append("SE funding/sentimento seguirem esticados com preço caro → reforça "
                                 "CAUTELOSO (euforia tardia de ciclo).")
    color = {"ACUMULAR": "#16a34a", "NEUTRO": "#3b82f6", "CAUTELOSO": "#f59e0b",
             "DEFENSIVO": "#ef4444", "—": "#94a3b8"}[posture]
    return {"posture": posture, "rationale": why, "scenarios": scenarios, "color": color}
