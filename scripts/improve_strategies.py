"""Testa melhorias para 'permanecer mais tempo na tendência':
canais assimétricos (entra rápido, sai largo) + trailing stop ATR.

Mede o que importa pro pedido: tempo médio no trade (segurou mais?),
profit factor (capturou mais da perna grande?) e retorno/risco OOS.
Só vale o que melhorar fora da amostra.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward, walk_forward_strategy  # noqa: E402
from scripts.diagnose_btc import round_trips  # noqa: E402


def trade_stats(wf, price):
    rt = round_trips(wf.oos_weights, price)
    if rt.empty:
        return 0, 0.0, 0.0, 0.0
    gains = rt[rt["ret_preco"] > 0]["ret_preco"].sum()
    losses = abs(rt[rt["ret_preco"] < 0]["ret_preco"].sum())
    pf = gains / losses if losses > 0 else float("inf")
    return len(rt), rt["dias"].mean(), rt["dias"].median(), pf


def row(name, wf, bh, price):
    m = wf.oos_metrics
    n, avg_d, med_d, pf = trade_stats(wf, price)
    calmar = m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    edge = m["total_return"] - bh.total_return
    return (f"  {name:34}{m['total_return']*100:+7.0f}%{m['max_drawdown']*100:7.0f}%"
            f"{m['sharpe']:7.2f}{calmar:7.2f}{n:6d}{avg_d:7.0f}{pf:7.2f}{edge*100:+8.0f}%")


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w = prof["engine"], prof["walkforward"]
    with OHLCVCache(ROOT / "db" / "trendfit.sqlite") as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated()].sort_index()
    ens, td, ted, ma, cost = e["ensembles"], w["train_days"], w["test_days"], e["ma_window"], e["cost_bps"]

    rows = []
    v1 = walk_forward(df, ens, e["kind"], td, ted, ma, cost)
    price = df["Close"].loc[v1.oos_period[0]:v1.oos_period[1]]
    bh = v1.benchmark
    rows.append(("v1 long-only (atual)", v1))

    # canais assimétricos: sai 1.5x/2x/3x mais largo que entra
    for asym in (1.5, 2.0, 3.0):
        cfg = StrategyConfig(ma_window=ma, band=0.0, mode="long_asym", asym=asym)
        rows.append((f"asym x{asym:.1f} (entra rápido, sai largo)",
                     walk_forward_strategy(df, cfg, ens, td, ted, cost)))

    # assimétrico + banda de regime
    cfg = StrategyConfig(ma_window=ma, band=0.05, mode="long_asym", asym=2.0)
    rows.append(("asym x2 + banda 5%", walk_forward_strategy(df, cfg, ens, td, ted, cost)))

    # trailing stop ATR (sem assimetria) — segura tendência, sai no rompimento real
    for k in (3.0, 5.0):
        cfg = StrategyConfig(ma_window=ma, band=0.0, mode="long_asym", asym=1.0, atr_k=k)
        rows.append((f"trailing ATR k={k:.0f}", walk_forward_strategy(df, cfg, ens, td, ted, cost)))

    # combinação: assimétrico + trailing ATR + banda
    cfg = StrategyConfig(ma_window=ma, band=0.05, mode="long_asym", asym=2.0, atr_k=4.0)
    rows.append(("asym x2 + banda 5% + ATR k=4", walk_forward_strategy(df, cfg, ens, td, ted, cost)))

    p0, p1 = v1.oos_period
    print("=" * 104)
    print(f" MELHORIAS PARA SEGURAR A TENDÊNCIA — BTC walk-forward OOS {p0.date()} -> {p1.date()}")
    print("=" * 104)
    print(f"  {'estratégia':34}{'retorno':>8}{'maxDD':>7}{'Sharpe':>7}{'Calmar':>7}"
          f"{'trades':>6}{'d.méd':>7}{'PF':>7}{'vs B&H':>9}")
    print("  " + "-" * 100)
    for name, wf in rows:
        print(row(name, wf, bh, price))
    bhm = bh.summary()
    bcal = bhm["cagr"] / abs(bhm["max_drawdown"])
    print(f"  {'Buy & Hold':34}{bhm['total_return']*100:+7.0f}%{bhm['max_drawdown']*100:7.0f}%"
          f"{bhm['sharpe']:7.2f}{bcal:7.2f}{0:6d}{'-':>7}{'-':>7}{0:+8.0f}%")
    print("=" * 104)
    print("  d.méd = duração média do trade (dias). PF = profit factor (ganhos/perdas). Calmar=CAGR/|maxDD|.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
