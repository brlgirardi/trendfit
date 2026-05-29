"""Coletor de OHLCV diário via CCXT, com fallback entre exchanges.

Estratégia:
  1. Tenta a lista de exchanges em ordem (binance, depois fallbacks).
  2. Pagina via fetch_ohlcv respeitando rateLimit do CCXT.
  3. Grava incrementalmente no cache SQLite (idempotente).
  4. Retoma de onde parou se já houver dados em cache.

Sem chaves de API (dados públicos). Custo zero.
Se TODAS as fontes falharem, levanta CollectorError — o chamador decide
abortar (nunca inventar dados).
"""

from __future__ import annotations

import time

import ccxt
import pandas as pd

from trendfit.data.cache import OHLCVCache

# Ordem de preferência. Pares variam por exchange (USDT vs USD).
DEFAULT_EXCHANGES: list[tuple[str, str]] = [
    ("binance", "BTC/USDT"),
    ("kraken", "BTC/USD"),
    ("coinbase", "BTC/USD"),
    ("bitstamp", "BTC/USD"),
]

# Início histórico amplo: Binance abriu BTC/USDT em ago/2017; outras exchanges
# têm histórico anterior. Pedimos desde 2013 e a exchange devolve o que tem.
DEFAULT_SINCE_MS = int(pd.Timestamp("2013-01-01", tz="UTC").timestamp() * 1000)


class CollectorError(RuntimeError):
    """Nenhuma fonte de dados real conseguiu entregar candles."""


def _fetch_from_exchange(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    since_ms: int,
    cache: OHLCVCache,
    cache_symbol: str,
) -> int:
    """Baixa candles de uma exchange e grava no cache. Retorna nº de linhas novas/atualizadas."""
    klass = getattr(ccxt, exchange_id)
    ex = klass({"enableRateLimit": True})
    ex.load_markets()
    if symbol not in ex.markets:
        raise CollectorError(f"{exchange_id}: par {symbol} indisponível")

    # Retoma do último candle em cache (menos 1 dia para refazer o último, que pode ter fechado).
    last = cache.last_ts(cache_symbol, timeframe)
    cursor = max(since_ms, last - 86_400_000) if last else since_ms
    now_ms = ex.milliseconds()
    limit = 1000
    written = 0

    while cursor < now_ms:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
        if not batch:
            break
        written += cache.upsert(cache_symbol, timeframe, batch, source=exchange_id)
        last_batch_ts = batch[-1][0]
        if last_batch_ts <= cursor:  # sem avanço -> evita loop infinito
            break
        cursor = last_batch_ts + 1
        time.sleep(ex.rateLimit / 1000.0)
    return written


def fetch_ohlcv_daily(
    cache: OHLCVCache,
    cache_symbol: str = "BTC",
    timeframe: str = "1d",
    since_ms: int = DEFAULT_SINCE_MS,
    exchanges: list[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Coleta OHLCV diário usando a primeira exchange que responder.

    `cache_symbol` é o rótulo canônico em cache (ex: "BTC"), independente do
    par específico de cada exchange. Retorna o DataFrame consolidado do cache.
    """
    exchanges = exchanges or DEFAULT_EXCHANGES
    errors: list[str] = []

    for exchange_id, symbol in exchanges:
        try:
            n = _fetch_from_exchange(exchange_id, symbol, timeframe, since_ms, cache, cache_symbol)
            df = cache.load(cache_symbol, timeframe)
            if len(df) >= 250:  # precisa de histórico mínimo para MA200 + walk-forward
                print(f"[collector] {exchange_id} {symbol}: +{n} candles | total cache {len(df)}")
                return df
            errors.append(f"{exchange_id}: só {len(df)} candles (insuficiente)")
        except Exception as exc:  # noqa: BLE001 - reportamos e tentamos a próxima fonte
            errors.append(f"{exchange_id}: {type(exc).__name__}: {exc}")
            continue

    # Última cartada: dados já existentes em cache (offline) servem?
    df = cache.load(cache_symbol, timeframe)
    if len(df) >= 250:
        print(f"[collector] todas as fontes online falharam; usando cache existente ({len(df)} candles)")
        return df

    raise CollectorError(
        "Nenhuma fonte de dados real entregou candles suficientes.\n  - "
        + "\n  - ".join(errors)
    )
