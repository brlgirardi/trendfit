"""Triple Screen INTRADAY (3 telas reais): maré diária + onda/entrada em 1h.

Agora com o 3º timeframe que faltava (dados 1h em db/intraday.db). Compara, no mesmo
período e no MESMO grão diário, contra o k=3 (engine oficial) e o Buy & Hold.

Ponto-chave honesto: operar em 1h gera MUITOS trades — então os CUSTOS importam.
Roda com taker realista da Binance (10 bps) e também sem custo, pra isolar o efeito.

NÃO altera o engine. Uso: python scripts/validate_elder_intraday.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trendfit.cockpit import _candidates, load_asset_df, load_profile  # noqa: E402
from trendfit.data.cache import OHLCVCache  # noqa: E402
from trendfit.engine.backtest import backtest  # noqa: E402
from trendfit.engine.elder import ElderConfig, triple_screen_position  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

TRADING_DAYS = 252


def daily_metrics(equity: pd.Series) -> dict:
    """Métricas no grão DIÁRIO a partir de uma curva de equity (intraday ou diária)."""
    eq = equity.resample("D").last().dropna()
    rets = eq.pct_change().dropna().to_numpy()
    total = float(eq.iloc[-1] / eq.iloc[0] - 1)
    years = len(eq) / TRADING_DAYS
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1) if years > 0 else 0.0
    peak = eq.cummax()
    dd = float(((eq - peak) / peak).min())
    sharpe = float(rets.mean() / rets.std() * np.sqrt(TRADING_DAYS)) if rets.std() > 0 else 0.0
    calmar = (cagr / abs(dd)) if dd else 0.0
    return {"total": total, "cagr": cagr, "dd": dd, "sharpe": sharpe, "calmar": calmar}


def _fmt(label: str, m: dict, extra: str = "") -> str:
    return (f"{label:<26} ret {m['total']*100:+8.1f}%  maxDD {m['dd']*100:6.1f}%  "
            f"Sharpe {m['sharpe']:5.2f}  Calmar {m['calmar']:5.2f}  {extra}")


def main() -> None:
    cache = OHLCVCache("db/intraday.db")
    df1h = cache.load("BTC", "1h")
    df1h = df1h.rename(columns=str.capitalize) if "close" in df1h.columns else df1h
    n = len(df1h)
    warmup = 24 * 40  # ~40 dias de 1h p/ a maré diária (MACD) estabilizar
    pos = triple_screen_position(df1h, ElderConfig(tide_freq="D"))
    n_trades = int(np.sum(np.abs(np.diff(pos)) > 0))

    print(f"\n=== BTC Triple Screen INTRADAY (maré 1D / onda+entrada 1h) ===")
    print(f"Período 1h: {df1h.index[warmup].date()} → {df1h.index[-1].date()} "
          f"| {n} candles | {n_trades} trades")

    for cost in (0.0, 10.0):
        res = backtest(df1h, pos, warmup, n, cost_bps=cost)
        tag = "SEM custo" if cost == 0 else f"taker {cost:.0f}bps"
        print(_fmt(f"Elder intraday ({tag})", daily_metrics(res.equity),
                   f"expo {res.avg_exposure*100:3.0f}%"))

    # Referência: k=3 e B&H (diário) no período OOS
    df_d = load_asset_df("BTC")
    prof = load_profile()
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    wf = walk_forward_grid(df_d, _candidates(e, g), train_days=w["train_days"],
                           test_days=w["test_days"], cost_bps=e["cost_bps"])
    p0, p1 = wf.oos_period
    print(f"\n--- referência diária (OOS {p0.date()} → {p1.date()}) ---")
    km = wf.oos_metrics
    km_calmar = km["cagr"] / abs(km["max_drawdown"]) if km["max_drawdown"] else 0.0
    print(f"{'k=3 (engine oficial)':<26} ret {km['total_return']*100:+8.1f}%  "
          f"maxDD {km['max_drawdown']*100:6.1f}%  Sharpe {km['sharpe']:5.2f}  "
          f"Calmar {km_calmar:5.2f}")


if __name__ == "__main__":
    main()
