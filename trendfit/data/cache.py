"""Cache de OHLCV em SQLite.

Idempotente: cada candle é uma linha (symbol, timeframe, ts) com UNIQUE.
Re-rodar o coletor faz upsert, nunca duplica. Evita rate limit ao reabrir
a mesma janela já baixada.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol     TEXT    NOT NULL,
    timeframe  TEXT    NOT NULL,
    ts         INTEGER NOT NULL,   -- epoch ms (UTC) do início do candle
    open       REAL    NOT NULL,
    high       REAL    NOT NULL,
    low        REAL    NOT NULL,
    close      REAL    NOT NULL,
    volume     REAL    NOT NULL,
    source     TEXT    NOT NULL,   -- exchange/feed de origem
    PRIMARY KEY (symbol, timeframe, ts)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_lookup ON ohlcv (symbol, timeframe, ts);
"""


class OHLCVCache:
    """Wrapper fino sobre SQLite para candles OHLCV."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "OHLCVCache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def upsert(self, symbol: str, timeframe: str, rows: list[tuple], source: str) -> int:
        """rows: lista de (ts_ms, open, high, low, close, volume). Retorna nº de linhas escritas."""
        if not rows:
            return 0
        payload = [(symbol, timeframe, int(ts), o, h, l, c, v, source) for ts, o, h, l, c, v in rows]
        self.conn.executemany(
            """INSERT INTO ohlcv (symbol, timeframe, ts, open, high, low, close, volume, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(symbol, timeframe, ts) DO UPDATE SET
                   open=excluded.open, high=excluded.high, low=excluded.low,
                   close=excluded.close, volume=excluded.volume, source=excluded.source""",
            payload,
        )
        self.conn.commit()
        return len(payload)

    def last_ts(self, symbol: str, timeframe: str) -> int | None:
        """Maior timestamp (ms) já em cache para o par, ou None."""
        cur = self.conn.execute(
            "SELECT MAX(ts) FROM ohlcv WHERE symbol=? AND timeframe=?",
            (symbol, timeframe),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    def load(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Carrega candles como DataFrame indexado por data (UTC), colunas OHLCV capitalizadas."""
        df = pd.read_sql_query(
            "SELECT ts, open, high, low, close, volume, source FROM ohlcv "
            "WHERE symbol=? AND timeframe=? ORDER BY ts ASC",
            self.conn,
            params=(symbol, timeframe),
        )
        if df.empty:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df = df.set_index("date")
        df = df.rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        )
        return df[["Open", "High", "Low", "Close", "Volume"]]

    def info(self, symbol: str, timeframe: str) -> dict:
        cur = self.conn.execute(
            "SELECT COUNT(*), MIN(ts), MAX(ts) FROM ohlcv WHERE symbol=? AND timeframe=?",
            (symbol, timeframe),
        )
        n, mn, mx = cur.fetchone()
        return {
            "rows": n or 0,
            "first": pd.to_datetime(mn, unit="ms", utc=True) if mn else None,
            "last": pd.to_datetime(mx, unit="ms", utc=True) if mx else None,
        }
