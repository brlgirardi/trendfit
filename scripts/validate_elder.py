"""Validação comparativa: sistema Elder (Triple Screen) vs k=3 vs Buy & Hold.

Roda os três no MESMO período OOS (out-of-sample do walk-forward do k=3) para um
veredito honesto. O Elder usa config default (parâmetros clássicos do Elder, NÃO
otimizados no período) — sem overfit. O k=3 usa params escolhidos só no treino (WF).

Uso: python scripts/validate_elder.py [BTC|ETH|...]
NÃO altera o engine; é só comparação.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from trendfit.cockpit import _candidates, _cfg_from_name, load_asset_df, load_profile  # noqa: E402
from trendfit.engine.backtest import backtest  # noqa: E402
from trendfit.engine.elder import ElderConfig, triple_screen_position  # noqa: E402
from trendfit.engine.strategy import target_weights  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402


def _calmar(m: dict) -> float:
    dd = abs(m["max_drawdown"])
    return (m["cagr"] / dd) if dd else 0.0


def _line(name: str, m: dict) -> str:
    return (f"{name:<22} ret {m['total_return']*100:+8.1f}%  "
            f"maxDD {m['max_drawdown']*100:6.1f}%  Sharpe {m['sharpe']:5.2f}  "
            f"Calmar {_calmar(m):5.2f}  expo {m['avg_exposure']*100:4.0f}%")


def run(asset: str) -> None:
    df = load_asset_df(asset)
    prof = load_profile()
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]

    # k=3 (engine atual) — walk-forward honesto
    cands = _candidates(e, g)
    wf = walk_forward_grid(df, cands, train_days=w["train_days"],
                           test_days=w["test_days"], cost_bps=e["cost_bps"])
    p0, p1 = wf.oos_period
    start = df.index.get_loc(p0)
    end = df.index.get_loc(p1) + 1

    # Elder (Triple Screen) — config default, MESMO período OOS
    pos = triple_screen_position(df, ElderConfig())
    res_elder = backtest(df, pos, start, end, cost_bps=e["cost_bps"])

    print(f"\n=== {asset} — período OOS {p0.date()} → {p1.date()} ===")
    print(_line("Buy & Hold", wf.benchmark.summary()))
    print(_line("k=3 (engine atual)", wf.oos_metrics))
    print(_line("Elder (Triple Screen)", res_elder.summary()))

    verdict = ("SOBREVIVE (vale walk-forward de params)"
               if _calmar(res_elder.summary()) >= _calmar(wf.oos_metrics) * 0.9
               else "NÃO bate o k=3 com config default — provável refutação")
    print(f"Veredito exploratório (Calmar): {verdict}")


def main() -> None:
    assets = sys.argv[1:] or ["BTC"]
    for a in assets:
        try:
            run(a)
        except Exception as exc:
            print(f"[{a}] falhou: {exc}")


if __name__ == "__main__":
    main()
