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
import sqlite3
import urllib.request
from pathlib import Path

import pandas as pd

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
            except Exception:  # noqa: BLE001 - registra 0 e segue
                written[name] = 0
        return written
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
