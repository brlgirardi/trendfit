"""Fase 3d — filtro anti-chop (ADX / inclinação MA200) no v3, validado OOS.

Pergunta do dono: reduzir exposição quando NÃO há tendência (lateral) corta o whipsaw
sem matar a captura das tendências grandes? threshold/floor escolhidos só no treino;
'off' sempre candidato. Lido de ARQUIVO.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.signal import position_events  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402
from trendfit.layers.trend_filter import adx_factor, maslope_factor  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


def calmar(wf):
    m = wf.oos_metrics
    return m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0


def trade_stats(wf, price):
    ev = position_events(wf.oos_weights, price.loc[wf.oos_weights.index], threshold=0.05)
    trades, op = [], None
    for _, r in ev.iterrows():
        if r["kind"] == "entry":
            op = r
        elif r["kind"] == "exit" and op is not None:
            trades.append(r["price"] / op["price"] - 1); op = None
    if not trades:
        return 0, 0.0
    t = np.array(trades)
    return len(t), (t > 0).mean() * 100


def row(name, wf, bh, price):
    m = wf.oos_metrics
    nt, wr = trade_stats(wf, price)
    return (f"  {name:24}{m['total_return']*100:+8.0f}%{m['max_drawdown']*100:8.0f}%"
            f"{m['sharpe']:8.2f}{calmar(wf):8.2f}{m['avg_exposure']*100:7.0f}%"
            f"{nt:6d}{wr:7.0f}%")


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    n = len(df)
    price = df["Close"]

    base_cands = []
    for lname, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for bnd, atrk in g["variants"]:
                base_cands.append((f"{lname}|a{asym}|b{bnd}|k{atrk}", lbs,
                                   StrategyConfig(ma_window=e["ma_window"], band=bnd,
                                                  mode="long_asym", asym=asym, atr_k=atrk)))
    ones = np.ones(n, dtype=float)

    def vec(spec):
        if spec is None:
            return ones
        if spec[0] == "adx":
            return adx_factor(df, adx_lo=spec[1], adx_hi=spec[2], floor=spec[3])
        if spec[0] == "slope":
            return maslope_factor(df, slope_window=spec[1], thr=spec[2], floor=spec[3])
        if spec[0] == "adx*slope":
            return (adx_factor(df, adx_lo=spec[1], adx_hi=spec[2], floor=spec[3])
                    * maslope_factor(df, slope_window=20, thr=0.0, floor=spec[3]))
        raise ValueError(spec)

    families = {
        "baseline (só v3)": [None],
        "+ ADX": [None, ("adx", 15, 25, 0.0), ("adx", 15, 25, 0.3), ("adx", 20, 30, 0.0)],
        "+ inclinação MA200": [None, ("slope", 20, 0.0, 0.0), ("slope", 30, 0.0, 0.3)],
        "+ ADX × inclinação": [None, ("adx*slope", 15, 25, 0.0), ("adx*slope", 20, 30, 0.0)],
    }

    def run(specs):
        cands, ext_by = [], {}
        for sp in specs:
            v = vec(sp)
            tag = "off" if sp is None else "_".join(str(x) for x in sp)
            for nm, lbs, cfg in base_cands:
                cn = f"{nm}#{tag}"
                cands.append((cn, lbs, cfg)); ext_by[cn] = v
        wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"],
                               cost_bps=e["cost_bps"], external_by=ext_by)
        return wf, Counter(s.chosen.split("#")[1] for s in wf.steps)

    base_wf, _ = run([None])
    bh = base_wf.benchmark
    p0, p1 = base_wf.oos_period
    print("=" * 96)
    print(f" FASE 3d — FILTRO ANTI-CHOP NO v3 (BTC OOS {p0.date()} -> {p1.date()})")
    print(" (não operar no lateral; threshold escolhido SÓ no treino; 'off' sempre candidato)")
    print("=" * 96)
    print(f"  {'família':24}{'retorno':>9}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}{'expos':>7}"
          f"{'trades':>6}{'win%':>7}")
    print("  " + "-" * 92)
    print(row("baseline (só v3)", base_wf, bh, price))
    detail = {}
    for fname, specs in families.items():
        if fname.startswith("baseline"):
            continue
        wf, chosen = run(specs)
        detail[fname] = (wf, chosen)
        print(row(fname, wf, bh, price))
    print("=" * 96)
    bc = calmar(base_wf)
    print(f"\n  baseline Calmar={bc:.2f}. Escolhas do grid por janela:")
    for fname, (wf, chosen) in detail.items():
        d = calmar(wf) - bc
        verd = "MELHORA" if d > 0.03 else ("neutro" if abs(d) <= 0.03 else "PIORA")
        print(f"    {fname:24} dCalmar={d:+.2f} [{verd}]  {dict(chosen)}")

    print("\n  Diagnóstico — melhores configs FIXAS (v3 no treino, filtro fixo):")
    for fname, specs in families.items():
        if fname.startswith("baseline"):
            continue
        for sp in specs[1:]:
            wf, _ = run([sp])
            m = wf.oos_metrics
            nt, wr = trade_stats(wf, price)
            tag = "_".join(str(x) for x in sp)
            print(f"    {tag:18} ret={m['total_return']*100:+6.0f}% DD={m['max_drawdown']*100:5.0f}% "
                  f"Sharpe={m['sharpe']:.2f} Calmar={calmar(wf):.2f} expos={m['avg_exposure']*100:.0f}% "
                  f"trades={nt} win={wr:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
