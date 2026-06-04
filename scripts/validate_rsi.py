"""Fase 3c — RSI (sobrecomprado/sobrevendido) como FILTRO de timing no v3, validado OOS.

Pergunta do dono: usar sobrecompra/sobrevenda reduz entradas/saídas falsas e melhora o
resultado? Distinção honesta: NÃO como gerador de sinal (mean-reversion, já refutada),
mas como FILTRO multiplicativo — reduzir exposição quando RSI sobrecomprado extremo
(evita perseguir topo). Threshold/floor escolhidos SÓ no treino; 'off' sempre candidato.

RSI causal (ewm Wilder) com shift(1) — sem look-ahead. Lido de ARQUIVO.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = -d.clip(upper=0.0)
    rs = (up.ewm(alpha=1 / period, adjust=False).mean()
          / dn.ewm(alpha=1 / period, adjust=False).mean())
    return 100 - 100 / (1 + rs)


def calmar(wf):
    m = wf.oos_metrics
    return m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0


def row(name, wf, bh):
    m = wf.oos_metrics
    return (f"  {name:26}{m['total_return']*100:+8.0f}%{m['max_drawdown']*100:8.0f}%"
            f"{m['sharpe']:8.2f}{calmar(wf):8.2f}{m['avg_exposure']*100:8.0f}%"
            f"{(m['total_return']-bh.total_return)*100:+9.0f}%")


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    n = len(df)
    r = rsi(df["Close"], 14).shift(1)  # causal

    base_cands = []
    for lname, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for bnd, atrk in g["variants"]:
                base_cands.append((f"{lname}|a{asym}|b{bnd}|k{atrk}", lbs,
                                   StrategyConfig(ma_window=e["ma_window"], band=bnd,
                                                  mode="long_asym", asym=asym, atr_k=atrk)))
    ones = np.ones(n, dtype=float)

    def rsi_factor(ob, floor):
        over = ((r - ob) / (100 - ob)).clip(lower=0.0, upper=1.0)
        return (1.0 - over * (1.0 - floor)).fillna(1.0).to_numpy()

    # specs: None=off; (ob, floor) = reduz exposicao quando RSI > ob
    specs = [None, (70, 0.4), (80, 0.5), (75, 0.3)]

    def run(sps):
        cands, ext_by = [], {}
        for sp in sps:
            vec = ones if sp is None else rsi_factor(sp[0], sp[1])
            tag = "off" if sp is None else f"rsi{sp[0]}_{sp[1]}"
            for nm, lbs, cfg in base_cands:
                cn = f"{nm}#{tag}"
                cands.append((cn, lbs, cfg)); ext_by[cn] = vec
        wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"],
                               cost_bps=e["cost_bps"], external_by=ext_by)
        return wf, Counter(s.chosen.split("#")[1] for s in wf.steps)

    base_wf, _ = run([None])
    bh = base_wf.benchmark
    p0, p1 = base_wf.oos_period
    print("=" * 94)
    print(f" FASE 3c — RSI COMO FILTRO NO v3 (BTC OOS {p0.date()} -> {p1.date()})")
    print(" (reduz exposição quando sobrecomprado; threshold escolhido SÓ no treino; 'off' candidato)")
    print("=" * 94)
    print(f"  {'config':26}{'retorno':>9}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}{'expos.':>8}{'vs B&H':>10}")
    print("  " + "-" * 90)
    print(row("baseline (só v3)", base_wf, bh))
    rsi_wf, chosen = run(specs)
    print(row("+ RSI filtro (grid)", rsi_wf, bh))
    print("=" * 94)
    bc, br = calmar(base_wf), base_wf.oos_metrics["total_return"]
    print(f"\n  baseline v3: ret={br*100:+.1f}% Calmar={bc:.2f}")
    print(f"  + RSI: dRet={(rsi_wf.oos_metrics['total_return']-br)*100:+.1f}pp dCalmar={calmar(rsi_wf)-bc:+.2f}")
    print(f"  grid escolheu: {dict(chosen)}")
    print("\n  Diagnóstico — cada RSI fixo (v3 escolhido no treino, filtro fixo):")
    for sp in specs[1:]:
        wf, _ = run([sp])
        m = wf.oos_metrics
        print(f"    rsi>{sp[0]} floor{sp[1]}  ret={m['total_return']*100:+6.0f}%  DD={m['max_drawdown']*100:5.0f}%  "
              f"Sharpe={m['sharpe']:.2f}  Calmar={calmar(wf):.2f}  expos={m['avg_exposure']*100:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
