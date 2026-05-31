"""Fase 3b — vol-targeting no núcleo v3, validado OOS (sem alavancagem).

Pergunta: dimensionar a posição pela volatilidade realizada (mirar vol-alvo constante)
melhora o retorno ajustado a risco do v3? alvo/janela são dimensão do grid (escolha só no
treino); 'off' sempre candidato. cap=1.0 => sem alavancagem (só reduz em vol alta).

Lido de ARQUIVO. Dados reais (cache SQLite).
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
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402
from trendfit.layers.volatility import vol_target_factor  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


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

    base_cands = []
    for lname, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                base_cands.append((f"{lname}|a{asym}|b{band}|k{atrk}", lbs,
                                   StrategyConfig(ma_window=e["ma_window"], band=band,
                                                  mode="long_asym", asym=asym, atr_k=atrk)))

    ones = np.ones(n, dtype=float)
    # configs de vol-target: (target_vol_anual, janela). None = off.
    vt_specs = [None, (0.5, 20), (0.5, 30), (0.7, 20), (0.7, 30)]

    def vt_vec(spec):
        if spec is None:
            return ones
        return vol_target_factor(df, target_vol=spec[0], window=spec[1], cap=1.0)

    def run(specs):
        cands, ext_by = [], {}
        for spec in specs:
            vec = vt_vec(spec)
            tag = "off" if spec is None else f"vt{spec[0]}_{spec[1]}"
            for nm, lbs, cfg in base_cands:
                cname = f"{nm}#{tag}"
                cands.append((cname, lbs, cfg))
                ext_by[cname] = vec
        wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"],
                               cost_bps=e["cost_bps"], external_by=ext_by)
        chosen = Counter(s.chosen.split("#")[1] for s in wf.steps)
        return wf, chosen

    base_wf, _ = run([None])
    bh = base_wf.benchmark
    p0, p1 = base_wf.oos_period

    print("=" * 94)
    print(f" FASE 3b — VOL-TARGETING NO v3 (BTC OOS {p0.date()} -> {p1.date()}; cap=1.0, sem alavancagem)")
    print(" (alvo/janela escolhidos SÓ no treino; 'off' sempre candidato)")
    print("=" * 94)
    print(f"  {'config':26}{'retorno':>9}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}{'expos.':>8}{'vs B&H':>10}")
    print("  " + "-" * 90)
    print(row("baseline (só v3)", base_wf, bh))
    vt_wf, chosen = run(vt_specs)
    print(row("+ vol-target (grid)", vt_wf, bh))
    bhm = bh.summary()
    print(f"  {'Buy & Hold':26}{bhm['total_return']*100:+8.0f}%{bhm['max_drawdown']*100:8.0f}%"
          f"{bhm['sharpe']:8.2f}{bhm['cagr']/abs(bhm['max_drawdown']):8.2f}{100:7.0f}%{0:+9.0f}%")
    print("=" * 94)

    bc, br = calmar(base_wf), base_wf.oos_metrics["total_return"]
    print(f"\n  Baseline v3: retorno={br*100:+.1f}% Calmar={bc:.2f} Sharpe={base_wf.oos_metrics['sharpe']:.2f}")
    print(f"  + vol-target: dRet={(vt_wf.oos_metrics['total_return']-br)*100:+.1f}pp "
          f"dCalmar={calmar(vt_wf)-bc:+.2f} dSharpe={vt_wf.oos_metrics['sharpe']-base_wf.oos_metrics['sharpe']:+.2f}")
    print(f"  escolhas do grid por janela: {dict(chosen)}")

    # também rodar cada config FIXA (diagnóstico: o melhor possivel por config, ainda OOS honesto
    # pois a estrategia v3 e selecionada no treino; so o vt e fixo)
    print("\n  Diagnóstico — cada vol-target FIXO (v3 escolhido no treino, vt fixo):")
    for spec in vt_specs[1:]:
        wf, _ = run([spec])
        m = wf.oos_metrics
        print(f"    vt{spec[0]}_{spec[1]:<3}  ret={m['total_return']*100:+6.0f}%  "
              f"DD={m['max_drawdown']*100:5.0f}%  Sharpe={m['sharpe']:.2f}  "
              f"Calmar={calmar(wf):.2f}  expos={m['avg_exposure']*100:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
