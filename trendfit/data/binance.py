"""Binance — leitor de portfolio READ-ONLY (display, nunca sinal).

Busca saldos via API privada com assinatura HMAC-SHA256.
Chaves lidas de BINANCE_API_KEY / BINANCE_API_SECRET no ambiente.
Se ausentes ou erro de rede → retorna {} silenciosamente.

LINHA VERMELHA: dados aqui são DISPLAY-ONLY. Nunca entram no motor de sinais.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

_BASE = "https://api.binance.com"


def _signed_get(path: str, api_key: str, api_secret: str, params: dict | None = None) -> dict:
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)
    query = urllib.parse.urlencode(params)
    sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{_BASE}{path}?{query}&signature={sig}"
    req = urllib.request.Request(url, headers={"X-MBX-APIKEY": api_key})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


def _price_usdt(symbol: str) -> float:
    url = f"{_BASE}/api/v3/ticker/price?symbol={symbol}USDT"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return float(json.loads(resp.read())["price"])


def fetch_avg_cost(api_key: str, api_secret: str, symbol: str) -> float:
    """Retorna preço médio de compra de `symbol` (ex: 'BTC') calculado sobre todos os trades.

    Usa GET /api/v3/myTrades com paginação. Retorna 0.0 em caso de erro.
    """
    try:
        pair = f"{symbol}USDT"
        all_trades: list[dict] = []
        from_id: int | None = None
        while True:
            params: dict = {"symbol": pair, "limit": 1000}
            if from_id is not None:
                params["fromId"] = from_id
            batch = _signed_get("/api/v3/myTrades", api_key, api_secret, params)
            if not batch:
                break
            all_trades.extend(batch)
            if len(batch) < 1000:
                break
            from_id = batch[-1]["id"] + 1

        total_qty = 0.0
        total_cost = 0.0
        for t in all_trades:
            qty = float(t["qty"])
            price = float(t["price"])
            if t["isBuyer"]:
                total_cost += qty * price
                total_qty += qty
            else:
                # venda reduz a posição média proporcionalmente
                total_cost -= (total_cost / total_qty * qty) if total_qty > 0 else 0
                total_qty -= qty

        return round(total_cost / total_qty, 2) if total_qty > 0 else 0.0
    except Exception as exc:
        logger.warning("Falha Binance avg_cost %s: %s", symbol, str(exc))
        return 0.0


def fetch_balances(api_key: str, api_secret: str) -> dict[str, float]:
    """Retorna {symbol: free_amount} para saldos livres > 0.

    Em caso de erro retorna {} e loga warning.
    """
    try:
        data = _signed_get("/api/v3/account", api_key, api_secret)
        return {
            b["asset"]: float(b["free"])
            for b in data.get("balances", [])
            if float(b["free"]) > 0
        }
    except Exception as exc:
        logger.warning("Falha Binance fetch_balances: %s", str(exc))
        return {}


def get_portfolio_summary() -> dict:
    """Lê BINANCE_API_KEY/SECRET do env e retorna resumo do portfolio.

    Retorna {} se chaves ausentes ou erro de rede.
    Estrutura: {BTC: {amount, usd_value}, ETH: {amount, usd_value},
                other_usd: float, total_usd: float}
    """
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        return {}

    balances = fetch_balances(api_key, api_secret)
    if not balances:
        return {}

    # Agrega saldos: spot direto + Simple Earn (LD*) → mesmo ativo base
    aggregated: dict[str, float] = {}
    for raw_sym, amount in balances.items():
        sym = raw_sym[2:] if raw_sym.startswith("LD") else raw_sym
        aggregated[sym] = aggregated.get(sym, 0.0) + amount

    result: dict = {}
    other_usd = 0.0

    for symbol, amount in aggregated.items():
        if symbol in ("BTC", "ETH"):
            try:
                price = _price_usdt(symbol)
            except Exception as exc:
                logger.warning("Falha Binance preço %s: %s", symbol, str(exc))
                price = 0.0
            avg_price = fetch_avg_cost(api_key, api_secret, symbol)
            # fallback manual: BINANCE_BTC_AVG_PRICE / BINANCE_ETH_AVG_PRICE no .env
            if not avg_price:
                env_key = f"BINANCE_{symbol}_AVG_PRICE"
                manual = os.environ.get(env_key, "")
                avg_price = float(manual) if manual else 0.0
            pnl_usd = round((price - avg_price) * amount, 2) if avg_price else None
            pnl_pct = round((price / avg_price - 1) * 100, 1) if avg_price else None
            result[symbol] = {
                "amount": amount,
                "usd_value": round(amount * price, 2),
                "avg_price": avg_price,
                "pnl_usd": pnl_usd,
                "pnl_pct": pnl_pct,
            }
        elif symbol == "USDT":
            other_usd += amount
        else:
            try:
                other_usd += amount * _price_usdt(symbol)
            except Exception:
                pass

    system_usd = sum(v["usd_value"] for v in result.values())
    result["other_usd"] = round(other_usd, 2)
    result["total_usd"] = round(system_usd + other_usd, 2)
    return result
