"""Qual estratégia vence em cada REGIME? boom (2020-21) vs maduro/pós-boom (2022+).

Tese do dono: o boom inicial (BTC 10-20x) pode nunca mais acontecer; num BTC maduro/lateral,
o vencedor pode ser outro — talvez mean-reversion (range), não trend-following.

Compara, em cada sub-período, long-only e causal (shift1), sem otimizar parâmetros no OOS:
  - Buy & Hold
  - Trend (v3, config live)
  - Mean-reversion (Bollinger z-score: compra oversold, reduz overbought)

Lido de ARQUIVO. Honestidade: parâmetros a priori (SMA20/2sigma; v3 do walk-forward).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.strategy import StrategyConfig, target_weights  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

TD = 365


def metrics(ret: pd.Series) -> dict:
    ret = ret.dropna()
    if len(ret) < 30:
        return {"ret": float("nan"), "dd": float("nan"), "sharpe": float("nan"), "calmar": float("nan")}
    eq = (1 + ret).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    cagr = eq.iloc[-1] ** (TD / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(TD) if ret.std() else 0.0
    return {"ret": eq.iloc[-1] - 1, "dd": dd, "sharpe": sharpe, "calmar": cagr / abs(dd) if dd else 0.0}


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    with OHLCVCache(DB := ROOT / "db" / "trendfit.sqlite") as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    px = df["Close"]; ret = px.pct_change()

    # Trend v3 (config live)
    cands = []
    for ln, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                cands.append((f"{ln}|a{asym}|b{band}|k{atrk}", lbs,
                              StrategyConfig(ma_window=e["ma_window"], band=band, mode="long_asym", asym=asym, atr_k=atrk)))
    wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"], cost_bps=e["cost_bps"])
    last = wf.steps[-1]; nm = last.chosen
    cfg = StrategyConfig(ma_window=e["ma_window"], band=float(nm.split("|b")[1].split("|")[0]),
                         mode="long_asym", asym=float(nm.split("|a")[1].split("|")[0]), atr_k=float(nm.split("|k")[1]))
    w_trend = pd.Series(target_weights(df, last.lookbacks, cfg), index=df.index).shift(1)

    # Mean-reversion (Bollinger z-score), long-only causal
    sma = px.rolling(20).mean(); sd = px.rolling(20).std()
    z = ((px - sma) / sd).shift(1)
    w_mr = (0.5 - z / 2).clip(0.0, 1.0)  # z<=-1 -> 1 (oversold) ; z>=+1 -> 0 (overbought)

    strats = {
        "Buy & Hold": pd.Series(1.0, index=px.index),
        "Trend (v3)": w_trend,
        "Mean-reversion (range)": w_mr,
    }
    periods = {
        "BOOM 2019-2021": ("2019-01-01", "2021-12-31"),
        "MADURO 2022-hoje": ("2022-01-01", str(px.index[-1].date())),
        "lateral 2024 (chop)": ("2024-03-01", "2024-10-01"),
        "TUDO 2019-hoje": ("2019-01-01", str(px.index[-1].date())),
    }
    print("=" * 92)
    print(" QUAL ESTRATÉGIA VENCE EM CADA REGIME (long-only, causal, sem otimizar no período)")
    print("=" * 92)
    for pname, (a, b) in periods.items():
        sl = slice(a, b)
        rr = ret.loc[sl]
        print(f"\n  [{pname}]  ({rr.index[0].date()} -> {rr.index[-1].date()}, {len(rr)}d)")
        print(f"    {'estratégia':26}{'retorno':>10}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}")
        for name, wgt in strats.items():
            m = metrics((wgt.loc[sl].fillna(0) * rr))
            print(f"    {name:26}{m['ret']*100:+9.0f}%{m['dd']*100:8.0f}%{m['sharpe']:8.2f}{m['calmar']:8.2f}")
    print("\n" + "=" * 92)
    print("  Leitura: comparar o VENCEDOR por Calmar/Sharpe no MADURO e no lateral — não no boom.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
