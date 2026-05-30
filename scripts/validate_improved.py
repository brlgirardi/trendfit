"""Validação SEM vazamento das melhorias (canal assimétrico + ATR).

Diferença crucial vs improve_strategies.py: aqui o asym/banda/ATR NÃO são fixados
por mim olhando o OOS. O walk-forward escolhe o candidato (lookbacks × asym × ATR)
em cada janela usando SÓ o treino. O número OOS resultante é honesto.

Compara: v1 (atual) | grid honesto | (referência) melhor config fixa olhando OOS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward, walk_forward_grid, walk_forward_strategy  # noqa: E402
from scripts.diagnose_btc import round_trips  # noqa: E402


def line(name, wf, bh, price):
    m = wf.oos_metrics
    rt = round_trips(wf.oos_weights, price)
    avg_d = rt["dias"].mean() if not rt.empty else 0
    calmar = m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    return (f"  {name:32}{m['total_return']*100:+7.0f}%{m['max_drawdown']*100:7.0f}%"
            f"{m['sharpe']:7.2f}{calmar:7.2f}{len(rt):6d}{avg_d:7.0f}"
            f"{(m['total_return']-bh.total_return)*100:+8.0f}%")


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w = prof["engine"], prof["walkforward"]
    with OHLCVCache(ROOT / "db" / "trendfit.sqlite") as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated()].sort_index()
    ens, td, ted, ma, cost = e["ensembles"], w["train_days"], w["test_days"], e["ma_window"], e["cost_bps"]

    # GRID honesto: lookbacks × asym × (com/sem banda e ATR). Tudo escolhido no treino.
    candidates = []
    for lname, lbs in ens.items():
        for asym in (1.0, 1.5, 2.0, 3.0):
            for band, atrk in ((0.0, 0.0), (0.05, 0.0), (0.05, 4.0)):
                cfg = StrategyConfig(ma_window=ma, band=band, mode="long_asym", asym=asym, atr_k=atrk)
                candidates.append((f"{lname}|a{asym}|b{band}|k{atrk}", lbs, cfg))

    v1 = walk_forward(df, ens, e["kind"], td, ted, ma, cost)
    price = df["Close"].loc[v1.oos_period[0]:v1.oos_period[1]]
    bh = v1.benchmark
    grid = walk_forward_grid(df, candidates, td, ted, cost)
    # referência overfit (escolhida por mim olhando OOS) — só para contraste
    ref_cfg = StrategyConfig(ma_window=ma, band=0.05, mode="long_asym", asym=2.0, atr_k=4.0)
    ref = walk_forward_strategy(df, ref_cfg, ens, td, ted, cost)

    p0, p1 = v1.oos_period
    print("=" * 92)
    print(f" VALIDAÇÃO SEM VAZAMENTO — BTC walk-forward OOS {p0.date()} -> {p1.date()}")
    print("=" * 92)
    print(f"  {'':32}{'retorno':>7}{'maxDD':>7}{'Sharpe':>7}{'Calmar':>7}{'trades':>6}{'d.méd':>7}{'vs B&H':>8}")
    print("  " + "-" * 88)
    print(line("v1 long-only (atual)", v1, bh, price))
    print(line("GRID honesto (asym no treino)", grid, bh, price))
    print(line("[ref] asym2+banda+ATR (overfit)", ref, bh, price))
    bhm = bh.summary()
    bcal = bhm["cagr"] / abs(bhm["max_drawdown"])
    print(f"  {'Buy & Hold':32}{bhm['total_return']*100:+7.0f}%{bhm['max_drawdown']*100:7.0f}%"
          f"{bhm['sharpe']:7.2f}{bcal:7.2f}{0:6d}{'-':>7}{0:+8.0f}%")
    print("=" * 92)
    print("\n  Config escolhida pelo GRID em cada janela de teste (só com dados de treino):")
    for s in grid.steps:
        print(f"    {s.test_start.date()}..{s.test_end.date()}  ->  {s.chosen}  (OOS {s.oos_return_veto*100:+.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
