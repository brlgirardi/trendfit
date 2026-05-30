"""Fase 2 — ablação das camadas externas sobre o núcleo v3 (grid leakage-free).

Complemento ao validate_phase2.py (que testa o v1). Aqui a pergunta é a que de fato
decide o default: adicionar veto externo (macro/sentimento) ao núcleo v3 (o default,
profiles/btc.json) MELHORA o out-of-sample, ou over-restringe e derruba a exposição?

O grid escolhe asym/banda/ATR SÓ no treino (sem vazamento). O veto externo entra por
E lógico (composite_allow) tanto no v1 quanto no walk_forward_grid. Alinhamento sem
look-ahead (ffill + shift(1)). Dados reais (cache SQLite).

IMPORTANTE (anti-overfit de meta-nível): escolher a combinação de camadas olhando esta
tabela OOS é a mesma armadilha do sweep +183% do v3. Esta tabela é diagnóstico honesto,
NÃO um cardápio para cherry-pick. Só adotar camada com tese econômica a priori E ganho
de risco/retorno que sobreviva — nunca "a linha mais bonita do OOS".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.layers.external_regime import composite_allow  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


def row(name, wf, bh):
    m = wf.oos_metrics
    calmar = m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    return (f"  {name:26}{m['total_return']*100:+8.0f}%{m['max_drawdown']*100:8.0f}%"
            f"{m['sharpe']:8.2f}{calmar:8.2f}{m['avg_exposure']*100:8.0f}%"
            f"{(m['total_return']-bh.total_return)*100:+9.0f}%")


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))  # v3 default
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated(keep="last")].sort_index()

    cands = []
    for lname, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                cands.append((f"{lname}|a{asym}|b{band}|k{atrk}", lbs,
                              StrategyConfig(ma_window=e["ma_window"], band=band,
                                             mode="long_asym", asym=asym, atr_k=atrk)))

    def run(layers):
        ext = composite_allow(DB, df.index, layers) if layers else None
        return walk_forward_grid(df, cands, train_days=w["train_days"],
                                 test_days=w["test_days"], cost_bps=e["cost_bps"],
                                 external_allow=ext)

    combos = [
        ("baseline v3 (só grid)", []),
        ("+ Fear&Greed", ["fng"]),
        ("+ VIX", ["vix"]),
        ("+ DXY (dolar)", ["dxy"]),
        ("+ 10Y (juros)", ["us10y"]),
        ("+ DXY+10Y", ["dxy", "us10y"]),
        ("+ macro (vix+dxy+10y)", ["vix", "dxy", "us10y"]),
        ("+ tudo (fng+macro)", ["fng", "vix", "dxy", "us10y"]),
    ]
    base = run([])
    bh = base.benchmark
    p0, p1 = base.oos_period

    print("=" * 92)
    print(f" FASE 2 — ABLACAO DE CAMADAS EXTERNAS NO NUCLEO v3 GRID (BTC OOS {p0.date()} -> {p1.date()})")
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

    def calmar(wf):
        m = wf.oos_metrics
        return m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    base_cal = calmar(base)
    base_ret = base.oos_metrics["total_return"]
    print(f"\n  Baseline v3: retorno={base_ret*100:+.1f}% Calmar={base_cal:.2f} "
          f"expos={base.oos_metrics['avg_exposure']*100:.0f}%")
    for name, layers in combos[1:]:
        wf = results[name]
        m = wf.oos_metrics
        print(f"  {name:26} dRet={ (m['total_return']-base_ret)*100:+6.1f}pp  "
              f"dCalmar={calmar(wf)-base_cal:+.2f}  expos={m['avg_exposure']*100:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
