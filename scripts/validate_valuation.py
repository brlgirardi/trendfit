"""Fase 5 — estratégia de ALOCAÇÃO por valuation (MVRV), validada sem look-ahead.

Testa a tese do dono: "comprar quando barato (MVRV baixo), reduzir quando caro (alto)"
como ALOCAÇÃO de ciclo longo — diferente do modulador da Fase 3 (que acoplava ao trend).

Anti-look-ahead: o "barato/caro" é o PERCENTIL EXPANDING de MVRV (só com história até o
dia), com shift(1). Threshold 30/70 escolhido a priori (não fitado no OOS). Compara:
  - Buy & Hold
  - v3 (trend puro, config live)
  - Valuation-only (compra barato / reduz caro, ignora tendência)
  - Trend × Valuation (timing do trend + dosagem do valuation)

CAVEAT honesto: MVRV cobre ~2-3 ciclos só — amostra pequena para regra de ciclo.
Lido de ARQUIVO.
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
from trendfit.data.external import load_series  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"
TD = 365


def causal_expanding_pct(s: pd.Series, min_obs: int = 365) -> pd.Series:
    """Percentil de cada ponto na própria história ATÉ ele (expanding, causal)."""
    a = s.to_numpy(dtype=float)
    out = np.full(len(a), np.nan)
    for i in range(len(a)):
        if i + 1 >= min_obs:
            hist = a[: i + 1]
            out[i] = np.mean(hist <= a[i])
    return pd.Series(out, index=s.index)


def metrics(ret: pd.Series) -> dict:
    ret = ret.dropna()
    eq = (1 + ret).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    n = len(ret)
    cagr = eq.iloc[-1] ** (TD / n) - 1 if n else 0.0
    sharpe = ret.mean() / ret.std() * np.sqrt(TD) if ret.std() else 0.0
    return {"ret": eq.iloc[-1] - 1, "dd": dd, "sharpe": sharpe,
            "calmar": cagr / abs(dd) if dd else 0.0, "expo": None}


def line(name, m, expo=None):
    e = f"{expo*100:6.0f}%" if expo is not None else "     —"
    return f"  {name:26}{m['ret']*100:+9.0f}%{m['dd']*100:8.0f}%{m['sharpe']:8.2f}{m['calmar']:8.2f}{e:>9}"


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    px = df["Close"]
    ret = px.pct_change()

    mv = load_series(DB, "mvrv")
    if mv.empty:
        print("sem MVRV no cache"); return 1
    mv_al = mv.reindex(px.index, method="ffill")
    pct = causal_expanding_pct(mv_al).shift(1)  # causal
    # exposição valuation: barato(pct<=.3)->1 ; caro(pct>=.7)->0 ; linear no meio
    val_expo = ((0.7 - pct) / (0.7 - 0.3)).clip(0.0, 1.0)

    # v3 live (config mais recente do walk-forward), peso sobre todo o df
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
    w_v3 = pd.Series(target_weights(df, last.lookbacks, cfg), index=df.index)

    # período comum: onde valuation existe (pct válido) — multi-ciclo
    valid = val_expo.dropna().index
    p0 = valid[0]
    sl = slice(p0, px.index[-1])
    r = ret.loc[sl]
    strat = {
        "Buy & Hold": (pd.Series(1.0, index=r.index), r),
        "v3 (trend puro)": (w_v3.shift(1).loc[sl].fillna(0), r),
        "Valuation-only (MVRV)": (val_expo.shift(1).loc[sl].fillna(0), r),
        "Trend x Valuation": ((w_v3 * val_expo).shift(1).loc[sl].fillna(0), r),
    }
    print("=" * 86)
    print(f" FASE 5 — ALOCAÇÃO POR VALUATION (MVRV) · período {p0.date()} -> {px.index[-1].date()} ({len(r)}d)")
    print(" (percentil EXPANDING causal, threshold 30/70 a priori, sem look-ahead)")
    print("=" * 86)
    print(f"  {'estratégia':26}{'retorno':>10}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}{'expos':>9}")
    print("  " + "-" * 82)
    res = {}
    for name, (wgt, rr) in strat.items():
        sret = (wgt * rr).dropna()
        m = metrics(sret); m_expo = float(wgt.mean())
        res[name] = m
        print(line(name, m, m_expo))
    print("=" * 86)
    bh = res["Buy & Hold"]
    print(f"\n  vs B&H (retorno {bh['ret']*100:+.0f}%, Sharpe {bh['sharpe']:.2f}, Calmar {bh['calmar']:.2f}):")
    for name in ("v3 (trend puro)", "Valuation-only (MVRV)", "Trend x Valuation"):
        m = res[name]
        verdict = "MELHOR risco/retorno" if m["calmar"] > bh["calmar"] else "pior"
        print(f"    {name:26} Calmar {m['calmar']:.2f} ({verdict}); Sharpe {m['sharpe']:.2f}")
    print(f"\n  CAVEAT: período cobre ~{(px.index[-1]-p0).days/365:.1f} anos / poucos ciclos — amostra pequena.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
