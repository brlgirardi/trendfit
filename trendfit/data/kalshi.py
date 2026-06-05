"""Kalshi — cone do MERCADO DE APOSTAS (contexto, NÃO sinal).

Lê a distribuição one-touch que a Kalshi precifica para o preço do ativo até o fim
do ano (API pública, sem auth). Mesma natureza do `polymarket.py`: é leitura do que a
multidão aposta AGORA, projetada até a resolução — CONTEXTO/sentimento, igual
Fear&Greed/funding. O valor é o comparativo: dois mercados independentes (Kalshi e
Polymarket) precificando o mesmo horizonte.

══════════════════════════════════════════════════════════════════════════════════
LINHA VERMELHA — NEVER USED BY ENGINE
Estes números NUNCA entram em strategy.py / signal.py / walkforward.py. O sistema não
aciona, não modula, não dimensiona, não vira sinal a partir daqui. É só ESPELHO da
multidão, plotado à frente de hoje no gráfico. Probabilidade implícita ≠ probabilidade
real (viés da multidão, prêmio, liquidez). O TrendFit não prevê — quem prevê é quem
aposta; aqui só mostramos a aposta dele.
══════════════════════════════════════════════════════════════════════════════════

Semântica HONESTA: os mercados MAXY/MINY são "one-touch" — resolvem Yes se o preço
TOCAR o strike em ALGUM momento até o fim do ano, não se fechar nele. O rótulo no
painel deve dizer "tocar X", nunca "preço será X".
"""

from __future__ import annotations

import json
import re
import urllib.request

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"

# Séries one-touch anuais por ativo: (alta = "max do ano", baixa = "min do ano").
# Só ativos com mercado líquido. Ouro/SP500 não mapeados → cone some (degrada gracioso).
SERIES: dict[str, tuple[str, str]] = {
    "BTC": ("KXBTCMAXY", "KXBTCMINY"),
    "ETH": ("KXETHMAXY", "KXETHMINY"),
}

_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def _get(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "trendfit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fixa/HTTPS)
        return json.loads(r.read().decode())


def _end_from_event(event_ticker: str) -> str | None:
    """Data do fim do HORIZONTE da aposta a partir do event_ticker (ex 'KXBTCMAXY-26DEC31'
    → '2026-12-31'). É a data em que a aposta para de valer, NÃO o settlement (que é ~1 mês
    depois). Por isso o cone some em 1º de janeiro — by design (ver docs/MARKET_CONE.md)."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event_ticker or "")
    if not m:
        return None
    yy, mon, dd = m.group(1), m.group(2), m.group(3)
    if mon not in _MONTHS:
        return None
    return f"20{yy}-{_MONTHS[mon]:02d}-{int(dd):02d}"


def _read_series(series_ticker: str, direction: str, timeout: float) -> tuple[list, str | None]:
    """Lê um lado do cone (alta ou baixa) de uma série one-touch.
    Retorna ([(target, prob, oi)], end_date). Filtra resolvidos/sem liquidez."""
    d = _get(f"{KALSHI}/markets?series_ticker={series_ticker}&status=open&limit=80", timeout)
    pts, end = [], None
    for m in d.get("markets", []):
        strike = m.get("floor_strike") if direction == "up" else m.get("floor_strike")
        # both MAXY ("Above $X") and MINY ("Below $X") expõem o nível em floor_strike
        if strike is None:
            strike = m.get("cap_strike")
        lp = m.get("last_price_dollars")
        if strike is None or lp in (None, ""):
            continue
        try:
            prob = float(lp)
            target = float(strike)
        except (ValueError, TypeError):
            continue
        if not (0.0 < prob < 1.0):          # ignora resolvidos (0/1) e sem trade
            continue
        oi = m.get("open_interest_fp")
        try:
            oi = float(oi) if oi is not None else 0.0
        except (ValueError, TypeError):
            oi = 0.0
        if oi <= 0:                          # sem liquidez = não informa
            continue
        if end is None:
            end = _end_from_event(m.get("event_ticker") or "")
        pts.append((round(target), prob, oi))
    pts.sort()
    return pts, end


def fetch_price_cone(asset: str, timeout: float = 12.0) -> dict | None:
    """Cone de probabilidade one-touch do ativo na Kalshi (mercados anuais líquidos).

    Retorna {source, up, down, end} ou None se indisponível. Nunca levanta exceção.
      up   = [(target, prob, oi)] — prob de TOCAR acima de target até o fim do ano
      down = [(target, prob, oi)] — prob de TOCAR abaixo de target até o fim do ano
      end  = 'YYYY-MM-DD' fim do horizonte da aposta (resolução, não settlement)
    """
    pair = SERIES.get(asset)
    if not pair:
        return None
    try:
        up, end_up = _read_series(pair[0], "up", timeout)
        down, end_dn = _read_series(pair[1], "down", timeout)
        if not up and not down:
            return None
        return {"source": "kalshi", "up": up, "down": down, "end": end_up or end_dn}
    except Exception:  # noqa: BLE001 — contexto opcional; nunca derruba o painel
        return None
