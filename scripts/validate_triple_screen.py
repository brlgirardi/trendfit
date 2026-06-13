"""WFA honesto: Triple Screen com o nosso motor (semana+dia) vs k=3 vs Buy & Hold.

"Rodar seco não vale" (Bruno). Aqui o Triple Screen é validado por walk-forward CEGO:
em cada janela, escolhe os lookbacks (semanal e diário) com melhor retorno/risco SÓ no
treino e aplica no teste — params nunca veem o futuro. Compara com o k=3 (mesmo WF) e
B&H no MESMO período OOS. Grid pequeno de propósito (controla graus de liberdade — a
história do projeto mostra que +DoF pune no cego).

Tela 3 (intraday) entra quando houver coletor intraday; esta versão usa semana+dia.

Uso: python scripts/validate_triple_screen.py [BTC|ETH|...]
"""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from trendfit.cockpit import _candidates, load_asset_df, load_profile  # noqa: E402
from trendfit.engine.backtest import _metrics_from_returns, backtest  # noqa: E402
from trendfit.engine.triple_screen import triple_screen_weights  # noqa: E402
from trendfit.engine.walkforward import selection_score, walk_forward_grid  # noqa: E402

# grid pequeno (controla DoF): conjuntos de lookbacks semanais × diários
WEEKLY_SETS = [[4, 8, 13], [8, 13, 26]]
DAILY_SETS = [[20, 40, 80], [10, 20, 40]]
TS_GRID = [{"weekly_lookbacks": w, "daily_lookbacks": d}
           for w, d in product(WEEKLY_SETS, DAILY_SETS)]


def _calmar(m: dict) -> float:
    dd = abs(m["max_drawdown"])
    return (m["cagr"] / dd) if dd else 0.0


def _line(name: str, m: dict) -> str:
    return (f"{name:<26} ret {m['total_return']*100:+8.1f}%  maxDD {m['max_drawdown']*100:6.1f}%  "
            f"Sharpe {m['sharpe']:5.2f}  Calmar {_calmar(m):5.2f}  expo {m['avg_exposure']*100:4.0f}%")


def wfa_triple_screen(df, grid, train_days: int, test_days: int, cost_bps: float):
    """Walk-forward cego do Triple Screen. Retorna (metrics, oos_period)."""
    n = len(df)
    # pré-computa os pesos (causais) de cada candidato uma vez
    weights = {i: triple_screen_weights(df, **c) for i, c in enumerate(grid)}

    oos_rets, oos_eq, oos_w, oos_dates = [], [], [], []
    equity = 1.0
    i = train_days
    while i + test_days <= n:
        # escolhe o melhor candidato NO TREINO [i-train_days, i)
        best_i, best_score = 0, -1e18
        for ci in range(len(grid)):
            res = backtest(df, weights[ci], i - train_days, i, cost_bps)
            s = selection_score(res)
            if s > best_score:
                best_score, best_i = s, ci
        # aplica CEGO no teste [i, i+test_days)
        res_test = backtest(df, weights[best_i], i, i + test_days, cost_bps)
        for d, r, ww in zip(res_test.daily_returns.index, res_test.daily_returns.values,
                            res_test.weights.values):
            equity *= (1 + r)
            oos_rets.append(r)
            oos_eq.append(equity)
            oos_w.append(ww)
            oos_dates.append(d)
        i += test_days

    rets = np.array(oos_rets)
    eq = np.array(oos_eq) if oos_eq else np.array([1.0])
    w = np.array(oos_w)
    m = _metrics_from_returns(rets, eq, w)
    period = (oos_dates[0], oos_dates[-1]) if oos_dates else None
    return m, period


def run(asset: str) -> None:
    df = load_asset_df(asset)
    prof = load_profile()
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]

    # k=3 (engine atual) — WF honesto
    cands = _candidates(e, g)
    wf = walk_forward_grid(df, cands, train_days=w["train_days"],
                           test_days=w["test_days"], cost_bps=e["cost_bps"])
    # Triple Screen — WFA honesto, mesmas janelas
    ts_m, ts_period = wfa_triple_screen(df, TS_GRID, w["train_days"], w["test_days"], e["cost_bps"])

    p0, p1 = wf.oos_period
    print(f"\n=== {asset} — OOS k=3 {p0.date()}→{p1.date()} | TS {ts_period[0].date()}→{ts_period[1].date()} ===")
    print(_line("Buy & Hold", wf.benchmark.summary()))
    print(_line("k=3 (engine atual)", wf.oos_metrics))
    print(_line("Triple Screen (WFA)", ts_m))
    verdict = ("SUPERA o k=3" if _calmar(ts_m) > _calmar(wf.oos_metrics)
               else "NÃO supera o k=3")
    print(f"Veredito WFA (Calmar): Triple Screen {verdict}")


def main() -> None:
    for a in (sys.argv[1:] or ["BTC"]):
        try:
            run(a)
        except Exception as exc:
            print(f"[{a}] falhou: {exc}")


if __name__ == "__main__":
    main()
