"""Coletores de dados externos (Fase 2) — macro e sentimento, custo zero.

Fontes (todas gratuitas, sem chave paga):
  - Fear & Greed Index: alternative.me (diário, desde 2018)
  - Macro via yfinance: VIX, DXY, US 10Y yield, ouro, S&P500

Tudo gravado no mesmo cache SQLite (tabela própria `series`), idempotente.

ANTI-LOOK-AHEAD: o coletor só grava o dado bruto com seu timestamp real. O
alinhamento defasado (usar só o que estava disponível no dia do sinal) é feito na
camada que consome (layers/), não aqui.

Se uma fonte falhar, devolve vazio e registra o erro — o chamador decide se
prossegue sem a camada (nunca inventar dados).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import urllib.request
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    name TEXT NOT NULL,        -- ex 'fng', 'vix', 'dxy', 'us10y', 'gold', 'spx'
    ts   INTEGER NOT NULL,     -- epoch ms (UTC), início do dia
    value REAL NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (name, ts)
);
"""

# nome canônico -> ticker yfinance
YF_SERIES = {
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
    "gold": "GC=F",
    "spx": "^GSPC",
    "qqq": "QQQ",    # Nasdaq-100 (proxy de tech/IA)
    "soxx": "SOXX",  # semicondutores (proxy de IA/hardware)
}

FNG_URL = "https://api.alternative.me/fng/?limit=0&format=json"


def _conn(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA)
    return conn


def _upsert(conn, name, rows, source) -> int:
    if not rows:
        return 0
    conn.executemany(
        """INSERT INTO series (name, ts, value, source) VALUES (?, ?, ?, ?)
           ON CONFLICT(name, ts) DO UPDATE SET value=excluded.value, source=excluded.source""",
        [(name, int(ts), float(v), source) for ts, v in rows],
    )
    conn.commit()
    return len(rows)


def fetch_fear_greed(db_path: str | Path) -> int:
    """Baixa o Fear & Greed Index completo (diário). Retorna nº de pontos gravados."""
    conn = _conn(db_path)
    try:
        req = urllib.request.Request(FNG_URL, headers={"User-Agent": "trendfit/0.1"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("data", [])
        rows = [(int(d["timestamp"]) * 1000, float(d["value"])) for d in data]
        return _upsert(conn, "fng", rows, "alternative.me")
    finally:
        conn.close()


def fetch_yf_series(db_path: str | Path, names: list[str] | None = None) -> dict[str, int]:
    """Baixa séries macro via yfinance. Retorna {nome: nº de pontos}."""
    import yfinance as yf

    names = names or list(YF_SERIES)
    conn = _conn(db_path)
    written = {}
    try:
        for name in names:
            ticker = YF_SERIES[name]
            try:
                h = yf.Ticker(ticker).history(period="max", interval="1d")
                if h.empty:
                    written[name] = 0
                    continue
                rows = [(int(idx.tz_localize(None).timestamp() * 1000) if idx.tzinfo
                         else int(idx.timestamp() * 1000), float(c))
                        for idx, c in h["Close"].items() if pd.notna(c)]
                written[name] = _upsert(conn, name, rows, f"yfinance:{ticker}")
            except Exception as exc:  # noqa: BLE001 - registra 0 e segue
                logger.warning("Falha YF fetch série %s: %s", name, str(exc))
                written[name] = 0
        return written
    finally:
        conn.close()


def fetch_funding_binance(db_path: str | Path, symbol: str = "BTCUSDT") -> int:
    """Baixa o histórico de funding rate (perpétuo USDT-M Binance) e AGREGA para diário
    (média das ~3 leituras de 8h). Funding alto/positivo = longs pagando caro = mercado
    super-alavancado comprado (sinal de fragilidade/topo). Retorna nº de dias gravados.

    ANTI-LOOK-AHEAD: grava só o dado bruto com timestamp real; a defasagem é na camada.
    """
    conn = _conn(db_path)
    try:
        raw: list[tuple[int, float]] = []
        start = 1500000000000  # ~jul/2017 (antes do primeiro funding real)
        while True:
            url = (f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}"
                   f"&limit=1000&startTime={start}")
            req = urllib.request.Request(url, headers={"User-Agent": "trendfit/0.1"})
            batch = json.loads(urllib.request.urlopen(req, timeout=30).read())
            if not batch:
                break
            raw.extend((int(d["fundingTime"]), float(d["fundingRate"])) for d in batch)
            if len(batch) < 1000:
                break
            start = batch[-1]["fundingTime"] + 1
        if not raw:
            return 0
        s = pd.Series({ts: v for ts, v in raw})
        s.index = pd.to_datetime(s.index, unit="ms", utc=True).normalize()
        daily = s.groupby(s.index).mean()
        rows = [(int(idx.timestamp() * 1000), float(v)) for idx, v in daily.items()]
        return _upsert(conn, "funding", rows, f"binance:{symbol}")
    finally:
        conn.close()


def fetch_mvrv_coinmetrics(db_path: str | Path) -> int:
    """Baixa MVRV (CapMVRVCur) on-chain do CoinMetrics community API (gratuito). MVRV alto
    = preço muito acima do custo base agregado (euforia/sobrevalorização); baixo = capitulação.
    Retorna nº de pontos gravados.
    """
    conn = _conn(db_path)
    try:
        rows: list[tuple[int, float]] = []
        url = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
               "?assets=btc&metrics=CapMVRVCur&frequency=1d&page_size=10000"
               "&start_time=2014-01-01")
        while url:
            req = urllib.request.Request(url, headers={"User-Agent": "trendfit/0.1"})
            d = json.loads(urllib.request.urlopen(req, timeout=30).read())
            for r in d.get("data", []):
                if r.get("CapMVRVCur") is None:
                    continue
                ts = int(pd.Timestamp(r["time"]).normalize().timestamp() * 1000)
                rows.append((ts, float(r["CapMVRVCur"])))
            url = d.get("next_page_url")
        return _upsert(conn, "mvrv", rows, "coinmetrics:CapMVRVCur")
    finally:
        conn.close()


CAPE_URL = "https://www.multpl.com/shiller-pe/table/by-month"


def fetch_cape_multpl(db_path: str | Path) -> int:
    """Baixa o CAPE (Shiller P/E, P/L ciclicamente ajustado) mensal do multpl.com.
    CAPE alto = ações caras vs lucros de 10 anos (margem de segurança baixa); é a
    métrica-âncora de valuation de AÇÕES (histórico desde 1871). Retorna nº de pontos.

    É só CONTEXTO de valuation (igual MVRV/funding): NÃO vira sinal, NÃO aciona, NÃO
    modula exposição. A Fase 5 refutou valuation como gatilho — aqui é leitura, não ordem.
    """
    conn = _conn(db_path)
    try:
        req = urllib.request.Request(CAPE_URL, headers={"User-Agent": "Mozilla/5.0 trendfit/1.0"})
        html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")  # noqa: S310
        # tabela mensal: <td>Mon D, YYYY</td><td> &#x2002; NN.NN </td>
        pairs = re.findall(r"<td>([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})</td>\s*"
                           r"<td>\s*(?:&#x2002;\s*)?([\d.]+)", html)
        rows: list[tuple[int, float]] = []
        for d, v in pairs:
            try:
                # âncora no 1º do mês: "Jun 1" e "Jun 13" (mês corrente) viram o mesmo
                # ponto → o UNIQUE(series, ts) deduplica em vez de criar dois junhos.
                anchored = pd.Timestamp(d).normalize().to_period("M").to_timestamp()
                ts = int(anchored.timestamp() * 1000)
                rows.append((ts, float(v)))
            except (ValueError, TypeError):
                continue
        return _upsert(conn, "cape", rows, "multpl.com:shiller-pe")
    except Exception as exc:  # noqa: BLE001 — fonte opcional; nunca inventar dado
        logger.warning("Falha CAPE fetch (multpl.com): %s", str(exc))
        return 0
    finally:
        conn.close()


def load_series(db_path: str | Path, name: str) -> pd.Series:
    """Carrega uma série externa como pd.Series indexada por data UTC (normalizada a meia-noite)."""
    conn = _conn(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT ts, value FROM series WHERE name=? ORDER BY ts ASC", conn, params=(name,)
        )
    finally:
        conn.close()
    if df.empty:
        return pd.Series(dtype=float, name=name)
    idx = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.normalize()
    s = pd.Series(df["value"].to_numpy(), index=idx, name=name)
    return s[~s.index.duplicated(keep="last")]
