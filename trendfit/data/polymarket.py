"""Polymarket — termômetro do MERCADO DE APOSTAS (contexto, NÃO sinal).

Lê a distribuição de probabilidade IMPLÍCITA que o mercado de previsão precifica para
o preço do BTC (Gamma API pública, sem auth). É leitura do PRESENTE — o que a multidão
aposta AGORA —, igual Fear&Greed/funding: CONTEXTO/sentimento. NUNCA vira sinal, nunca
modula exposição, nunca é "previsão do TrendFit". O valor é o comparativo: onde o
sistema (frio, regime) diverge da manada.

LINHA VERMELHA: o sistema não prevê. Aqui só ESPELHAMOS o que outro mercado precifica.
Probabilidade implícita ≠ probabilidade real (viés da multidão, prêmio, liquidez).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

GAMMA_SEARCH = "https://gamma-api.polymarket.com/public-search"


def _get(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "trendfit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fixa/HTTPS)
        return json.loads(r.read().decode())


def fetch_btc_price_distribution(timeout: float = 12.0) -> dict | None:
    """Distribuição implícita de preço do BTC no Polymarket (mercado anual mais líquido).

    Retorna dict {title, end, volume, up, down} ou None se indisponível.
      up   = [(target, prob)] — prob de o BTC SUBIR até target (decrescente no target)
      down = [(target, prob)] — prob de o BTC CAIR até target (decrescente no target)
    Descarta mercados já resolvidos (prob 0 ou 1) e sem liquidez. Nunca levanta exceção."""
    try:
        q = urllib.parse.urlencode({"q": "what price will bitcoin hit",
                                    "limit_per_type": 20, "events_status": "active"})
        d = _get(f"{GAMMA_SEARCH}?{q}", timeout)
        evs = d.get("events", []) if isinstance(d, dict) else []
        cand = [e for e in evs if "price will bitcoin hit" in (e.get("title") or "").lower()]
        if not cand:
            return None
        e = max(cand, key=lambda x: x.get("volume") or 0)  # o mais líquido (horizonte anual)
        up, down = [], []
        for m in e.get("markets", []):
            t = (m.get("groupItemTitle") or "").strip()
            liq = m.get("liquidityNum") or m.get("liquidity")
            try:
                px = json.loads(m.get("outcomePrices", "[]"))
            except (ValueError, TypeError):
                px = None
            if not t or not px or liq in (None, 0):
                continue
            prob = float(px[0])
            if not (0.0 < prob < 1.0):          # ignora mercados já resolvidos
                continue
            num = re.sub(r"[^0-9]", "", t)
            if not num:
                continue
            target = int(num)
            if "↓" in t or "below" in t.lower() or "<" in t:
                down.append((target, prob))
            elif "↑" in t or "above" in t.lower():
                up.append((target, prob))
        up.sort()
        down.sort()
        if not up and not down:
            return None
        return {"title": e.get("title"), "end": (e.get("endDate") or "")[:10],
                "volume": float(e.get("volume") or 0), "up": up, "down": down}
    except Exception:  # noqa: BLE001 — contexto opcional; nunca derruba o painel
        return None


def nearest_prob(points: list[tuple[int, float]], level: float) -> tuple[int, float] | None:
    """Target mais próximo de `level` na curva e sua prob. None se vazio."""
    if not points:
        return None
    return min(points, key=lambda tp: abs(tp[0] - level))


def fifty_fifty_level(down: list[tuple[int, float]]) -> float | None:
    """Nível onde a prob de CAIR até X cruza 50% (piso 'provável' implícito do mercado).
    Interpola linearmente na curva down (prob decresce conforme o target cai)."""
    if not down or len(down) < 2:
        return None
    s = sorted(down)  # target asc; prob asc (alvo maior = mais provável de tocar)
    for (t0, p0), (t1, p1) in zip(s, s[1:]):
        if p0 <= 0.5 <= p1 and p1 != p0:
            return t0 + (t1 - t0) * (0.5 - p0) / (p1 - p0)
    return None
