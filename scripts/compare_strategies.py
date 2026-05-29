"""Compara o núcleo v1 (long-only breakout simples) contra variantes v2/v3
(Donchian simétrico + histerese + cooldown + long/short) no MESMO walk-forward.

Regra: só vale o que ganhar OUT-OF-SAMPLE em retorno/risco. O objetivo NÃO é
deixar o gráfico bonito — é achar a config com melhor retorno ajustado a risco
sem inventar graus de liberdade.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.signal import position_events  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward, walk_forward_strategy  # noqa: E402


def _row(name, m, bh, n_trades):
    edge = m["total_return"] - bh.total_return
    calmar = m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    return (f"  {name:30}{m['total_return']*100:+8.0f}%{m['max_drawdown']*100:8.0f}%"
            f"{m['sharpe']:8.2f}{calmar:8.2f}{m['avg_exposure']*100:8.0f}%"
            f"{n_trades:7d}{edge*100:+9.0f}%")


def _ntrades(wf):
    """Conta 'aberturas de posição': transições de caixa(0) para long/short, ou reversões de sinal."""
    import numpy as np
    w = wf.oos_weights.to_numpy()
    sign = np.sign(w)
    prev = np.concatenate([[0.0], sign[:-1]])
    opens = ((prev == 0) & (sign != 0)) | ((prev > 0) & (sign < 0)) | ((prev < 0) & (sign > 0))
    return int(opens.sum())


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w = prof["engine"], prof["walkforward"]
    with OHLCVCache(ROOT / "db" / "trendfit.sqlite") as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated()].sort_index()
    ens, td, ted, ma, cost = e["ensembles"], w["train_days"], w["test_days"], e["ma_window"], e["cost_bps"]

    variants = []
    # v1 baseline (long-only, breakout simples, sem banda)
    v1 = walk_forward(df, ens, e["kind"], td, ted, ma, cost)
    variants.append(("v1 long-only (atual)", v1))

    # v2: long-only + histerese de regime (varia a banda) + cooldown
    for band in (0.03, 0.05):
        cfg = StrategyConfig(ma_window=ma, band=band, mode="long_only", min_hold=1)
        wf = walk_forward_strategy(df, cfg, ens, td, ted, cost)
        variants.append((f"v2 long-only band={band:.0%}", wf))
    cfg = StrategyConfig(ma_window=ma, band=0.05, mode="long_only", min_hold=5)
    variants.append(("v2 long-only band=5% hold=5d", walk_forward_strategy(df, cfg, ens, td, ted, cost)))

    # v3: long/short + histerese
    for band in (0.03, 0.05):
        cfg = StrategyConfig(ma_window=ma, band=band, mode="long_short", min_hold=1)
        wf = walk_forward_strategy(df, cfg, ens, td, ted, cost)
        variants.append((f"v3 long/short band={band:.0%}", wf))
    cfg = StrategyConfig(ma_window=ma, band=0.05, mode="long_short", min_hold=5)
    variants.append(("v3 long/short band=5% hold=5d", walk_forward_strategy(df, cfg, ens, td, ted, cost)))

    bh = v1.benchmark
    p0, p1 = v1.oos_period
    print("=" * 96)
    print(f" COMPARAÇÃO DE ESTRATÉGIAS — BTC walk-forward OOS {p0.date()} -> {p1.date()}")
    print("=" * 96)
    print(f"  {'estratégia':30}{'retorno':>9}{'maxDD':>8}{'Sharpe':>8}{'Calmar':>8}"
          f"{'expos.':>8}{'trades':>7}{'vs B&H':>10}")
    print("  " + "-" * 92)
    for name, wf in variants:
        print(_row(name, wf.oos_metrics, bh, _ntrades(wf)))
    print(_row("Buy & Hold", bh.summary(), bh, 0))
    print("=" * 96)
    print("  Calmar = CAGR / |maxDD| (retorno por unidade de drawdown). Maior = melhor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
