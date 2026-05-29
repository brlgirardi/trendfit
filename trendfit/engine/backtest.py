"""Backtest vetorizado de posição fracionária + métricas de retorno/risco.

Convenção anti-look-ahead: o peso decidido com a informação do dia *i* (w[i]) é
aplicado ao retorno de *i* para *i+1*. Ou seja, o retorno diário do portfólio é
`w[i-1] * (C[i]/C[i-1] - 1)`. Nenhum retorno usa um peso decidido com informação
futura.

Custo de transação opcional (`cost_bps`) é cobrado sobre o turnover (|Δpeso|).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 365  # cripto opera todos os dias


@dataclass
class BacktestResult:
    equity: pd.Series          # curva de capital (base 1.0)
    daily_returns: pd.Series   # retornos diários do portfólio
    weights: pd.Series         # peso aplicado por dia (0..1)
    total_return: float        # retorno total no período (fração, ex 0.92 = +92%)
    cagr: float
    max_drawdown: float        # fração negativa (ex -0.35 = -35%)
    sharpe: float
    volatility: float          # anualizada
    avg_exposure: float        # peso médio (tempo no mercado ponderado)
    n_days: int

    def summary(self) -> dict:
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "max_drawdown": self.max_drawdown,
            "sharpe": self.sharpe,
            "volatility": self.volatility,
            "avg_exposure": self.avg_exposure,
            "n_days": self.n_days,
        }


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float(((equity - peak) / peak).min())


def _metrics_from_returns(rets: np.ndarray, equity: np.ndarray, weights: np.ndarray) -> dict:
    n = len(rets)
    total = float(equity[-1] - 1.0) if n else 0.0
    years = n / TRADING_DAYS if n else 0.0
    cagr = float(equity[-1] ** (1 / years) - 1) if years > 0 and equity[-1] > 0 else 0.0
    vol = float(rets.std(ddof=0) * np.sqrt(TRADING_DAYS)) if n > 1 else 0.0
    mean_ann = float(rets.mean() * TRADING_DAYS) if n else 0.0
    sharpe = float(mean_ann / vol) if vol > 0 else 0.0
    return {
        "total_return": total,
        "cagr": cagr,
        "max_drawdown": _max_drawdown(equity),
        "sharpe": sharpe,
        "volatility": vol,
        "avg_exposure": float(np.mean(weights)) if n else 0.0,
        "n_days": n,
    }


def backtest(
    df: pd.DataFrame,
    target_weights: np.ndarray,
    start: int,
    end: int,
    cost_bps: float = 0.0,
) -> BacktestResult:
    """Simula o portfólio sobre o slice [start:end) do df.

    df: DataFrame com coluna Close (índice temporal).
    target_weights: vetor 0..1 alinhado ao df inteiro (já com veto aplicado).
    cost_bps: custo por unidade de turnover, em basis points (ex 10 = 0.10%).
    """
    close = df["Close"].to_numpy()
    idx = df.index
    w = target_weights

    rets, eq_vals, applied_w, dates = [], [], [], []
    equity = 1.0
    for i in range(start + 1, end):
        ret = close[i] / close[i - 1] - 1.0
        pos = w[i - 1]  # peso decidido ontem, aplicado ao retorno de hoje
        turnover = abs(w[i - 1] - (w[i - 2] if i - 2 >= start else 0.0))
        cost = turnover * (cost_bps / 10_000.0)
        port_ret = pos * ret - cost
        equity *= (1 + port_ret)
        rets.append(port_ret)
        eq_vals.append(equity)
        applied_w.append(pos)
        dates.append(idx[i])

    rets_a = np.array(rets)
    eq_a = np.array(eq_vals) if eq_vals else np.array([1.0])
    w_a = np.array(applied_w)
    m = _metrics_from_returns(rets_a, eq_a, w_a)
    return BacktestResult(
        equity=pd.Series(eq_a, index=dates, name="equity"),
        daily_returns=pd.Series(rets_a, index=dates, name="ret"),
        weights=pd.Series(w_a, index=dates, name="weight"),
        **m,
    )


def buy_and_hold(df: pd.DataFrame, start: int, end: int) -> BacktestResult:
    """Benchmark Buy & Hold (peso 1.0 o tempo todo) no mesmo slice."""
    full_long = np.ones(len(df))
    return backtest(df, full_long, start, end, cost_bps=0.0)
