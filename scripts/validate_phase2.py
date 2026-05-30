"""Fase 2 — ablação das camadas externas no veto.

Pergunta honesta: adicionar cada camada externa (sentimento/macro) ao veto MA200
MELHORA o out-of-sample? Testa cada camada isolada e combinações, sobre o mesmo
walk-forward v1 (baseline simples, fácil de interpretar). Só vale o que melhora OOS.

Dados reais (cache SQLite). Alinhamento sem look-ahead (ffill + shift(1)).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.layers.external_regime import composite_allow  # noqa: E402
from trendfit.engine.walkforward import walk_forward  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


def row(name, wf, bh):
    m = wf.oos_metrics
    calmar = m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    return (f"  {name:26}{m['total_return']*100:+8.0f}%{m['max_drawdown']*100:8.0f}%"
            f"{m['sharpe']:8.2f}{calmar:8.2f}{m['avg_exposure']*100:8.0f}%"
            f"{(m['total_return']-bh.total_return)*100:+9.0f}%")


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc_v1.json"))
    e, w = prof["engine"], prof["walkforward"]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated()].sort_index()
    ens, td, ted, ma, cost = e["ensembles"], w["train_days"], w["test_days"], e["ma_window"], e["cost_bps"]

    def run(layers):
        ext = composite_allow(DB, df.index, layers) if layers else None
        return walk_forward(df, ens, e["kind"], td, ted, ma, cost, external_allow=ext)

    combos = [
        ("baseline (só MA200)", []),
        ("+ Fear&Greed", ["fng"]),
        ("+ VIX", ["vix"]),
        ("+ DXY (dólar)", ["dxy"]),
        ("+ 10Y (juros)", ["us10y"]),
        ("+ macro (vix+dxy+10y)", ["vix", "dxy", "us10y"]),
        ("+ tudo (fng+macro)", ["fng", "vix", "dxy", "us10y"]),
    ]
    base = run([])
    bh = base.benchmark
    p0, p1 = base.oos_period

    print("=" * 92)
    print(f" FASE 2 — ABLAÇÃO DE CAMADAS EXTERNAS (BTC OOS {p0.date()} -> {p1.date()})")
    print("=" * 92)
    print(f"  {'veto':26}{'retorno':>9}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}{'expos.':>8}{'vs B&H':>10}")
    print("  " + "-" * 88)
    results = {}
    for name, layers in combos:
        wf = run(layers)
        results[name] = wf
        print(row(name, wf, bh))
    bhm = bh.summary()
    print(f"  {'Buy & Hold':26}{bhm['total_return']*100:+8.0f}%{bhm['max_drawdown']*100:8.0f}%"
          f"{bhm['sharpe']:8.2f}{bhm['cagr']/abs(bhm['max_drawdown']):8.2f}{100:7.0f}%{0:+9.0f}%")
    print("=" * 92)

    # veredito automático: melhor por Calmar vs baseline
    def calmar(wf):
        m = wf.oos_metrics
        return m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    base_cal = calmar(base)
    best = max(results.items(), key=lambda kv: calmar(kv[1]))
    print(f"\n  Baseline Calmar={base_cal:.2f}. Melhor camada: '{best[0]}' Calmar={calmar(best[1]):.2f}")
    if calmar(best[1]) > base_cal * 1.03:
        print("  >>> Alguma camada externa MELHORA o OOS (>3% Calmar). Vale integrar.")
    else:
        print("  >>> Nenhuma camada externa melhora o OOS de forma relevante. NÃO integrar ainda.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
