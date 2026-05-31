"""Fase 3 — moduladores contínuos de exposição (funding / MVRV / macro), validados OOS.

Correção da Fase 2: em vez de veto binário por E lógico (que zerava a posição e desabava
o retorno), cada sinal externo vira um FATOR de exposição em [floor, 1] que só REDUZ o
tamanho em extremos (alavancagem/euforia/aperto). O threshold/floor de cada modulador é
uma DIMENSÃO DO GRID — escolhido só no treino, junto com asym/banda/ATR. "off" (sem
modulador) é sempre um candidato, então o sistema pode declinar o sinal por janela.

Pergunta honesta: alguma família de sinal melhora o OOS do v3 de forma robusta? Só vale
o que sobrevive sem look-ahead (z-score rolling causal, ffill+shift1) e sem cherry-pick.

Dados reais (cache SQLite). Lido de ARQUIVO, nunca de stdout.
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
from trendfit.data.external import (  # noqa: E402
    fetch_funding_binance, fetch_mvrv_coinmetrics, load_series,
)
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402
from trendfit.layers.external_regime import exposure_factor, macro_factor  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


def _ensure_external() -> None:
    """Popula funding/MVRV no cache se ausentes (reprodutível em clone limpo)."""
    if load_series(DB, "funding").empty:
        print("  [setup] baixando funding rate (Binance)...")
        fetch_funding_binance(DB)
    if load_series(DB, "mvrv").empty:
        print("  [setup] baixando MVRV (CoinMetrics)...")
        fetch_mvrv_coinmetrics(DB)


def calmar(wf):
    m = wf.oos_metrics
    return m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0


def row(name, wf, bh):
    m = wf.oos_metrics
    return (f"  {name:24}{m['total_return']*100:+8.0f}%{m['max_drawdown']*100:8.0f}%"
            f"{m['sharpe']:8.2f}{calmar(wf):8.2f}{m['avg_exposure']*100:8.0f}%"
            f"{(m['total_return']-bh.total_return)*100:+9.0f}%")


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))  # v3 default
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    _ensure_external()
    idx, n = df.index, len(df)

    base_cands = []
    for lname, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                base_cands.append((f"{lname}|a{asym}|b{band}|k{atrk}", lbs,
                                   StrategyConfig(ma_window=e["ma_window"], band=band,
                                                  mode="long_asym", asym=asym, atr_k=atrk)))

    ones = np.ones(n, dtype=float)

    def mod_vec(spec):
        if spec is None:
            return ones
        kind = spec[0]
        if kind == "fund":
            return exposure_factor(DB, idx, "funding", z_hi=spec[1], floor=spec[2], direction="high_bad")
        if kind == "mvrv":
            return exposure_factor(DB, idx, "mvrv", z_hi=spec[1], floor=spec[2], direction="high_bad")
        if kind == "macro":
            return macro_factor(DB, idx, ["dxy", "us10y", "vix"], floor=spec[1])
        if kind == "fund*mvrv":
            return (exposure_factor(DB, idx, "funding", z_hi=spec[1], floor=spec[2], direction="high_bad")
                    * exposure_factor(DB, idx, "mvrv", z_hi=spec[1], floor=spec[2], direction="high_bad"))
        raise ValueError(kind)

    # cada família: lista de moduladores candidatos (None = off, sempre incluído)
    families = {
        "baseline (só v3)": [None],
        "+ funding": [None, ("fund", 1.5, 0.4), ("fund", 1.0, 0.5)],
        "+ MVRV": [None, ("mvrv", 1.5, 0.4), ("mvrv", 1.0, 0.5)],
        "+ macro (modulado)": [None, ("macro", 0.4), ("macro", 0.6)],
        "+ funding+MVRV": [None, ("fund", 1.5, 0.4), ("mvrv", 1.5, 0.4), ("fund*mvrv", 1.5, 0.5)],
    }

    def run_family(mods):
        cands, ext_by = [], {}
        for mi, spec in enumerate(mods):
            vec = mod_vec(spec)
            tag = "off" if spec is None else "_".join(str(x) for x in spec)
            for nm, lbs, cfg in base_cands:
                cname = f"{nm}#{tag}"
                cands.append((cname, lbs, cfg))
                ext_by[cname] = vec
        wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"],
                               cost_bps=e["cost_bps"], external_by=ext_by)
        chosen_mods = Counter(s.chosen.split("#")[1] for s in wf.steps)
        return wf, chosen_mods

    base_wf, _ = run_family([None])
    bh = base_wf.benchmark
    p0, p1 = base_wf.oos_period

    print("=" * 92)
    print(f" FASE 3 — MODULADORES CONTÍNUOS NO v3 (BTC OOS {p0.date()} -> {p1.date()})")
    print(" (modulador escolhido SÓ no treino; 'off' sempre candidato)")
    print("=" * 92)
    print(f"  {'família':24}{'retorno':>9}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}{'expos.':>8}{'vs B&H':>10}")
    print("  " + "-" * 88)
    detail = {}
    for fname, mods in families.items():
        wf, chosen = run_family(mods)
        detail[fname] = (wf, chosen)
        print(row(fname, wf, bh))
    bhm = bh.summary()
    print(f"  {'Buy & Hold':24}{bhm['total_return']*100:+8.0f}%{bhm['max_drawdown']*100:8.0f}%"
          f"{bhm['sharpe']:8.2f}{bhm['cagr']/abs(bhm['max_drawdown']):8.2f}{100:7.0f}%{0:+9.0f}%")
    print("=" * 92)

    base_cal, base_ret = calmar(base_wf), base_wf.oos_metrics["total_return"]
    print(f"\n  Baseline v3: retorno={base_ret*100:+.1f}% Calmar={base_cal:.2f}")
    print("  O grid escolheu (por janela) qual modulador usar:")
    for fname, (wf, chosen) in detail.items():
        if fname.startswith("baseline"):
            continue
        used = dict(chosen)
        d_cal = calmar(wf) - base_cal
        d_ret = (wf.oos_metrics["total_return"] - base_ret) * 100
        verdict = "MELHORA" if d_cal > 0.03 else ("neutro" if abs(d_cal) <= 0.03 else "PIORA")
        print(f"    {fname:24} dRet={d_ret:+6.1f}pp dCalmar={d_cal:+.2f}  [{verdict}]  escolhas={used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
