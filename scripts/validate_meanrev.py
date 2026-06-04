"""Valida o perfil mean-reversion OOS (params escolhidos SÓ no treino) vs B&H e v3.

Walk-forward honesto: em cada janela de treino escolhe a combinação (window, z_buy, z_sell)
com melhor Calmar no passado; aplica no teste cego; concatena a curva OOS. Compara com
Buy & Hold e com o trend v3 (config live) no mesmo período. Lido de ARQUIVO.
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
from trendfit.engine.meanrev import meanrev_weights  # noqa: E402
from trendfit.engine.strategy import StrategyConfig, target_weights  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

TD = 365


def metrics(ret: pd.Series) -> dict:
    ret = ret.dropna()
    if len(ret) < 30:
        return {"ret": float("nan"), "dd": float("nan"), "sharpe": 0.0, "calmar": 0.0}
    eq = (1 + ret).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    cagr = eq.iloc[-1] ** (TD / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(TD) if ret.std() else 0.0
    return {"ret": eq.iloc[-1] - 1, "dd": dd, "sharpe": sharpe, "calmar": cagr / abs(dd) if dd else 0.0}


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc_meanrev.json"))
    train_days, test_days = prof["walkforward"]["train_days"], prof["walkforward"]["test_days"]
    grid = [(wd, zb, zs) for wd in prof["grid"]["window"] for zb, zs in prof["grid"]["z_pairs"]]

    with OHLCVCache(ROOT / "db" / "trendfit.sqlite") as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    px = df["Close"]; ret = px.pct_change(); n = len(df)

    # pesos pré-computados de cada candidato mean-rev (causais)
    w_by = {f"w{wd}|z{zb}/{zs}": meanrev_weights(px, wd, zb, zs) for wd, zb, zs in grid}

    def score(w, a, b):
        m = metrics((w.shift(1).iloc[a:b] * ret.iloc[a:b]))
        return m["calmar"] if m["ret"] == m["ret"] else -1

    oos = pd.Series(np.nan, index=df.index)
    i = train_days
    while i + test_days <= n:
        best = max(w_by.items(), key=lambda kv: score(kv[1], i - train_days, i))
        oos.iloc[i:i + test_days] = best[1].shift(1).iloc[i:i + test_days].values
        i += test_days
    first, end = train_days, i
    sl = slice(df.index[first], df.index[end - 1])
    r = ret.loc[sl]

    # v3 trend (config live) e B&H no mesmo período
    e, g = prof["engine_ref"], prof["grid_ref"]
    cands = []
    for ln, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                cands.append((f"{ln}|a{asym}|b{band}|k{atrk}", lbs,
                              StrategyConfig(ma_window=e["ma_window"], band=band, mode="long_asym", asym=asym, atr_k=atrk)))
    wf = walk_forward_grid(df, cands, train_days=train_days, test_days=test_days, cost_bps=e["cost_bps"])
    nm = wf.steps[-1].chosen
    cfg = StrategyConfig(ma_window=e["ma_window"], band=float(nm.split("|b")[1].split("|")[0]),
                         mode="long_asym", asym=float(nm.split("|a")[1].split("|")[0]), atr_k=float(nm.split("|k")[1]))
    w_v3 = pd.Series(target_weights(df, wf.steps[-1].lookbacks, cfg), index=df.index)

    rows = {
        "Buy & Hold": metrics(r),
        "Trend v3 (default)": metrics(w_v3.shift(1).loc[sl].fillna(0) * r),
        "Mean-reversion (perfil)": metrics(oos.loc[sl].fillna(0) * r),
    }
    print("=" * 80)
    print(f" PERFIL MEAN-REVERSION — OOS honesto (params no treino) · {df.index[first].date()} -> {df.index[end-1].date()}")
    print("=" * 80)
    print(f"  {'estratégia':26}{'retorno':>10}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}")
    for name, m in rows.items():
        print(f"  {name:26}{m['ret']*100:+9.0f}%{m['dd']*100:8.0f}%{m['sharpe']:8.2f}{m['calmar']:8.2f}")
    print("=" * 80)
    mr, v3 = rows["Mean-reversion (perfil)"], rows["Trend v3 (default)"]
    print(f"\n  Mean-rev Calmar {mr['calmar']:.2f} vs Trend {v3['calmar']:.2f} -> "
          f"{'mean-rev melhor' if mr['calmar'] > v3['calmar'] else 'TREND melhor (mean-rev é especialista de lateral)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
