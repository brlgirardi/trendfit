"""Fase 4 — sistema v3.1 (k=3) aplicado a múltiplos ativos: BTC, ETH, SP500.

Mesmo motor (ensemble Donchian + regime MA200 + trailing ATR, grid do btc.json), mesmo
walk-forward honesto (params escolhidos só no treino). Pergunta: o sistema generaliza
além do BTC? Compara cada ativo vs seu Buy & Hold. Lido de ARQUIVO.

ETH/BTC: OHLCV real via CCXT. SP500: só close no cache (yfinance) -> OHLC sintético
(O=H=L=C), aproximação rotulada (sem intraday real; o trailing ATR vira range de close;
MA200/Donchian em dias úteis, não 24/7). Ver gotchas em docs/PHASE4.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.data.external import load_series  # noqa: E402
from trendfit.engine.signal import current_signal  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


def candidates(e, g):
    out = []
    for ln, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                out.append((f"{ln}|a{asym}|b{band}|k{atrk}", lbs,
                            StrategyConfig(ma_window=e["ma_window"], band=band, mode="long_asym", asym=asym, atr_k=atrk)))
    return out


def load_crypto(sym, exch):
    with OHLCVCache(DB) as c:
        df = fetch_ohlcv_daily(c, cache_symbol=sym, timeframe="1d", exchanges=exch)
    return df[~df.index.duplicated(keep="last")].sort_index()


def load_spx():
    s = load_series(DB, "spx").dropna()
    return pd.DataFrame({"Open": s, "High": s, "Low": s, "Close": s, "Volume": 0.0})


ASSETS = {
    "BTC": lambda: load_crypto("BTC", [("binance", "BTC/USDT"), ("kraken", "BTC/USD"), ("coinbase", "BTC/USD"), ("bitstamp", "BTC/USD")]),
    "ETH": lambda: load_crypto("ETH", [("binance", "ETH/USDT"), ("kraken", "ETH/USD"), ("coinbase", "ETH/USD")]),
    "SP500": load_spx,
}


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    cands = candidates(e, g)
    print("=" * 100)
    print(" FASE 4 — SISTEMA v3.1 (k=3) MULTI-ATIVO · walk-forward honesto (params só no treino)")
    print("=" * 100)
    print(f"  {'ativo':7}{'período OOS':23}{'sistema':>9}{'B&H':>8}{'sysDD':>8}{'bhDD':>8}{'Sharpe':>8}{'vsBH':>8}  sinal hoje")
    print("  " + "-" * 96)
    for name, loader in ASSETS.items():
        try:
            df = loader()
            if len(df) < w["train_days"] + w["test_days"] + 30:
                print(f"  {name:7}histórico insuficiente ({len(df)}d)"); continue
            wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"], cost_bps=e["cost_bps"])
            m, bh = wf.oos_metrics, wf.benchmark
            p0, p1 = wf.oos_period
            sig = current_signal(df, wf.steps[-1].lookbacks, kind=e["kind"], ma_window=e["ma_window"])
            sg = "FORA" if sig.recommended_weight <= 0 else f"COMPR {sig.recommended_weight*100:.0f}%"
            print(f"  {name:7}{f'{p0.date()}->{p1.date()}':23}{m['total_return']*100:+8.0f}%{bh.total_return*100:+7.0f}%"
                  f"{m['max_drawdown']*100:7.0f}%{bh.max_drawdown*100:7.0f}%{m['sharpe']:8.2f}"
                  f"{(m['total_return']-bh.total_return)*100:+7.0f}%  {sg} ({'bull' if sig.regime_bull else 'bear'})")
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:7}FALHOU: {type(exc).__name__}: {exc}")
    print("=" * 100)
    print("  Sistema deve BATER o B&H em risco (DD muito menor, Sharpe maior) em cada ativo.")
    print("  SP500 = OHLC sintético (só close no cache), dias úteis — aproximação, não intraday real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
