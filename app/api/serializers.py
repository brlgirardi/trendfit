"""Serialização da saída do cockpit (trendfit.cockpit) para o formato JSON da API REST.

Camada PURA de transformação: recebe o dict que `asset_cockpit()` / `environment_now()`
devolvem e o reformata para o contrato que o front-end consome (timestamps unix em
segundos, candles OHLCV, faixas de regime, postura com cor, métricas walk-forward).

NÃO decide nada, NÃO lê DB, NÃO toca o engine — só remapeia. Toda a inteligência
(regime, sinais, postura, walkforward) já vem pronta do cockpit; aqui só traduzimos.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _to_unix(date_str: str) -> int:
    """'YYYY-MM-DD' -> unix timestamp em segundos (meia-noite UTC)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


# ──────────────────────────────────────────────────────────────────────────────
# Mapa de cor por postura (display-only — postura informa, regime decide).
# ──────────────────────────────────────────────────────────────────────────────
POSTURE_COLORS = {
    "ACUMULAR": "#16a34a",
    "NEUTRO": "#3b82f6",
    "CAUTELOSO": "#f59e0b",
    "DEFENSIVO": "#ef4444",
}
_POSTURE_DEFAULT = "#94a3b8"


def serialize_ohlcv(cockpit_data: dict) -> list[dict]:
    """Combina series.date + OHLC (ou só price quando high_low=False) em candles.

    Formato: [{"time": int_unix_s, "open", "high", "low", "close", "volume": float}]
    Ativos sem OHLC real (high_low=False): open=high=low=close=price, volume=0.0.
    """
    series = cockpit_data.get("series") or {}
    dates = series.get("date") or []
    closes = series.get("price") or []
    has_ohlc = bool(series.get("high_low"))

    opens = series.get("open") if has_ohlc else None
    highs = series.get("high") if has_ohlc else None
    lows = series.get("low") if has_ohlc else None

    out: list[dict] = []
    for i, d in enumerate(dates):
        close = float(closes[i])
        if has_ohlc and opens is not None and highs is not None and lows is not None:
            o, h, low = float(opens[i]), float(highs[i]), float(lows[i])
        else:
            o = h = low = close
        out.append({
            "time": _to_unix(d),
            "open": o, "high": h, "low": low, "close": close,
            "volume": 0.0,
        })
    return out


def _build_in_position_set(trades: list, open_until_today: bool = True) -> set[str]:
    """Conjunto de datas ISO em que o sistema estava comprado (entre entry e exit).

    Reconstrói o histórico de regime per-bar a partir da lista de trades retornada
    pelo cockpit. Trade aberto (exit_date=None) usa hoje como limite superior.
    """
    from datetime import date, timedelta

    in_pos: set[str] = set()
    today_str = date.today().isoformat()
    for trade in trades or []:
        entry_str = trade.get("entry_date")
        exit_str = trade.get("exit_date") or (today_str if open_until_today else None)
        if not entry_str or not exit_str:
            continue
        try:
            cur = datetime.strptime(entry_str, "%Y-%m-%d").date()
            end = datetime.strptime(exit_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        while cur <= end:
            in_pos.add(cur.isoformat())
            cur += timedelta(days=1)
    return in_pos


def serialize_signals(cockpit_data: dict) -> list[dict]:
    """Série de regime/posição POR DIA para overlay no gráfico.

    Regime histórico é reconstruído a partir de cockpit_data['trades']
    (entry_date / exit_date), que descrevem quando o sistema estava comprado.
    MA200 distingue BEAR (abaixo da média) de OUT (acima, mas fora da posição).

    Formato: [{"time", "regime": "BULL|BEAR|OUT", "in_position": bool,
               "fraction": float, "trailing_stop": float|None}]
    """
    series = cockpit_data.get("series") or {}
    dates: list[str] = series.get("date") or []
    prices: list = series.get("price") or []
    ma200s: list = series.get("ma200") or []
    trades = cockpit_data.get("trades") or []
    plan = cockpit_data.get("plan") or {}

    # trailing_stop do sinal vivo (aplicado apenas ao bar mais recente)
    trailing_stop_live: float | None = None
    if plan.get("sell_kind") == "trailing ATR" and plan.get("sell_level") is not None:
        trailing_stop_live = float(plan["sell_level"])

    # Conjunto de datas em que o sistema estava comprado (reconstruído dos trades)
    in_pos_dates = _build_in_position_set(trades)

    result: list[dict] = []
    for i, d in enumerate(dates):
        in_pos = d in in_pos_dates
        fraction = 1.0 if in_pos else 0.0

        if in_pos:
            regime = "BULL"
        else:
            # Distingue BEAR (preço abaixo da MA200) de OUT (acima, mas fora)
            price = prices[i] if i < len(prices) else None
            ma = ma200s[i] if i < len(ma200s) else None
            if price is not None and ma is not None and price < ma:
                regime = "BEAR"
            else:
                regime = "OUT"

        # trailing_stop só no bar final (sinal vivo); histórico recebe None
        ts = trailing_stop_live if i == len(dates) - 1 else None

        result.append({
            "time": _to_unix(d),
            "regime": regime,
            "in_position": in_pos,
            "fraction": fraction,
            "trailing_stop": ts,
        })

    return result


def serialize_posture(cockpit_data: dict, env: dict | None = None) -> dict:
    """Postura do ativo (label + ação) com cor de display.

    Formato: {"label", "action", "environment", "color"}.

    A estrutura real de `asset_posture()` é {posture, rationale, scenarios, color}:
      - label   <- posture.posture  (ACUMULAR/NEUTRO/CAUTELOSO/DEFENSIVO)
      - action  <- posture.rationale (texto que explica a ação recomendada)
    Aceitamos também a forma {label, action} por robustez. environment vem do
    ambiente macro (environment_now()['env']['level'] = FAVORÁVEL/MISTO/ADVERSO).
    """
    posture = cockpit_data.get("posture") or {}
    label = str(posture.get("posture") or posture.get("label") or "")
    action = str(posture.get("rationale") or posture.get("action") or "")

    environment = ""
    if isinstance(env, dict):
        environment = str(env.get("level", "") or "")

    return {
        "label": label,
        "action": action,
        "environment": environment,
        "color": POSTURE_COLORS.get(label, _POSTURE_DEFAULT),
    }


def serialize_valuation(cockpit_data: dict) -> dict:
    """Valuation do ativo (rótulo + percentil) para o chip de display.

    Formato: {"label": str, "pct": float | None}.

    Lê direto o que o cockpit já calculou:
      - label <- cockpit_data['val_label'] (ex.: "CAPE 42", "MVRV 1.21"; "" se ausente)
      - pct   <- cockpit_data['val_pct']   (percentil 0..100; None quando não há valuation)

    Display-only: valuation INFORMA (caro/barato vs. histórico), nunca aciona trade.
    """
    label = str(cockpit_data.get("val_label") or "")
    raw_pct = cockpit_data.get("val_pct")
    pct: float | None
    if raw_pct is None:
        pct = None
    else:
        try:
            pct = float(raw_pct)
        except (TypeError, ValueError):
            pct = None
    return {"label": label, "pct": pct}


def serialize_walkforward(cockpit_data: dict) -> dict | None:
    """Métricas OOS do walk-forward honesto. None se wf ausente.

    Formato: {"oos_return", "sharpe", "max_dd", "cagr", "period"}.
    """
    wf = cockpit_data.get("wf")
    if not wf:
        return None
    return {
        "oos_return": float(wf.get("ret", 0.0) or 0.0),
        "sharpe": float(wf.get("sharpe", 0.0) or 0.0),
        "max_dd": float(wf.get("dd", 0.0) or 0.0),
        "cagr": float(wf.get("cagr", 0.0) or 0.0),
        "period": str(wf.get("period", "") or ""),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Macro: nome do campo da API -> nome da série no DB (load_series).
# 'mvrv_btc' é exposto na API mas armazenado como 'mvrv' (MVRV do BTC).
# ──────────────────────────────────────────────────────────────────────────────
MACRO_SERIES = {
    "fng": "fng",
    "vix": "vix",
    "dxy": "dxy",
    "us10y": "us10y",
    "mvrv_btc": "mvrv",
    "mvrv_eth": "mvrv_eth",
    "funding": "funding",
}


def _series_to_points(series) -> list[dict]:
    """pd.Series indexada por data -> [{"time": int_unix_s, "value": float}]."""
    if series is None or len(series) == 0:
        return []
    points: list[dict] = []
    for idx, val in series.items():
        try:
            ts = int(idx.timestamp())
            points.append({"time": ts, "value": float(val)})
        except (ValueError, TypeError, AttributeError):
            continue
    return points


def serialize_macro(macro_series: dict) -> dict:
    """Transforma um dict {campo_api: pd.Series} em séries temporais JSON.

    macro_series: {"fng": Series, "vix": Series, ...} já carregadas via load_series.
    Cada campo vira lista [{"time", "value"}]; séries vazias/ausentes -> [].
    """
    out: dict = {}
    for field in MACRO_SERIES:
        out[field] = _series_to_points(macro_series.get(field))
    return out
