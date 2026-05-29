"""Walk-forward multi-ciclo — o único teste honesto.

Para cada janela:
  1. TREINO (ex. 4 anos): escolhe o conjunto de lookbacks (ensemble) com o melhor
     RETORNO/RISCO no passado. Seleção por risco, não por lucro máximo — é isso que
     evita pegar um pico isolado de ruído (a lição central do PRD).
  2. TESTE (ex. 1 ano CEGO): aplica a config escolhida out-of-sample.
  3. Rola a janela para frente e repete.

Os retornos OOS de todas as janelas são concatenados numa única curva — esse é o
desempenho realista do sistema. Comparado SEMPRE contra Buy & Hold no mesmo período.

A seleção de parâmetros acontece SÓ com dados de treino; o teste nunca influencia a
escolha. Não há grid-search fino aqui (poucos candidatos, lookbacks fixos) — menos
graus de liberdade = menos overfitting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from trendfit.engine.backtest import BacktestResult, backtest, buy_and_hold
from trendfit.engine.ensemble import ensemble_position
from trendfit.layers.regime import regime_allow

# Conjuntos candidatos de lookbacks (1 só "knob" diversificado por candidato).
DEFAULT_ENSEMBLES: dict[str, list[int]] = {
    "curto": [10, 20, 30],
    "medio": [20, 40, 60],
    "longo": [40, 60, 100],
    "amplo": [15, 30, 55, 90],
}


def selection_score(res: BacktestResult) -> float:
    """Retorno por unidade de risco (estilo Calmar). Penaliza drawdown.

    Configs que perdem dinheiro ou não têm histórico recebem score negativo.
    """
    if res.n_days < 30 or res.total_return <= 0:
        return -1.0
    return res.total_return / (abs(res.max_drawdown) + 0.01)


@dataclass
class WFStep:
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    chosen: str
    lookbacks: list[int]
    oos_return_veto: float
    oos_return_noveto: float


@dataclass
class WalkForwardResult:
    oos_equity: pd.Series              # curva OOS concatenada (com veto) — base 1.0
    oos_returns: pd.Series
    oos_weights: pd.Series             # peso aplicado por dia (0..1) no período OOS
    oos_metrics: dict
    oos_metrics_noveto: dict
    benchmark: BacktestResult          # Buy & Hold no mesmo período OOS
    steps: list[WFStep] = field(default_factory=list)
    oos_period: tuple[pd.Timestamp, pd.Timestamp] | None = None

    @property
    def beat_buy_and_hold(self) -> bool:
        return self.oos_metrics["total_return"] > self.benchmark.total_return

    @property
    def veto_helped(self) -> bool:
        return self.oos_metrics["total_return"] > self.oos_metrics_noveto["total_return"]


def _precompute_weights(
    df: pd.DataFrame, ensembles: dict[str, list[int]], kind: str
) -> dict[str, np.ndarray]:
    """Pesos do ensemble (sem veto) para cada candidato, sobre o df inteiro. Causal."""
    return {name: ensemble_position(df, lbs, kind) for name, lbs in ensembles.items()}


def walk_forward(
    df: pd.DataFrame,
    ensembles: dict[str, list[int]] | None = None,
    kind: str = "donchian",
    train_days: int = 365 * 4,
    test_days: int = 365,
    ma_window: int = 200,
    cost_bps: float = 0.0,
) -> WalkForwardResult:
    """Roda o walk-forward completo e devolve resultado OOS + benchmark."""
    ensembles = ensembles or DEFAULT_ENSEMBLES
    n = len(df)
    if n < train_days + test_days:
        raise ValueError(
            f"histórico insuficiente: {n} dias < treino {train_days} + teste {test_days}"
        )

    weights_by_cfg = _precompute_weights(df, ensembles, kind)
    allow = regime_allow(df, ma_window)            # vetor de veto (True = libera)
    allow_f = allow.astype(float)

    steps: list[WFStep] = []
    # Vetores de peso OOS contínuos (montados janela a janela) — sem costura.
    oos_w_veto = np.full(n, np.nan)
    oos_w_noveto = np.full(n, np.nan)
    first_start = train_days
    last_end = train_days

    i = train_days
    while i + test_days <= n:
        # --- TREINO: escolhe melhor config por retorno/risco no passado ---
        best_name, best_score = None, -np.inf
        for name, w in weights_by_cfg.items():
            res_tr = backtest(df, w * allow_f, i - train_days, i, cost_bps)
            score = selection_score(res_tr)
            if score > best_score:
                best_score, best_name = score, name
        chosen_w = weights_by_cfg[best_name]

        # --- TESTE CEGO: grava os pesos escolhidos no slot OOS desta janela ---
        j0, j1 = i, i + test_days
        oos_w_veto[j0:j1] = (chosen_w * allow_f)[j0:j1]
        oos_w_noveto[j0:j1] = chosen_w[j0:j1]
        last_end = j1

        # métricas por janela (informativas, no slice isolado)
        res_v = backtest(df, chosen_w * allow_f, j0, j1, cost_bps)
        res_nv = backtest(df, chosen_w, j0, j1, cost_bps)
        steps.append(
            WFStep(
                train_end=df.index[i],
                test_start=df.index[j0],
                test_end=df.index[min(j1, n - 1)],
                chosen=best_name,
                lookbacks=ensembles[best_name],
                oos_return_veto=res_v.total_return,
                oos_return_noveto=res_nv.total_return,
            )
        )
        i += test_days

    # --- Um único backtest contínuo sobre todo o span OOS (sem emendas) ---
    end_idx = min(last_end, n)
    res_v = backtest(df, np.nan_to_num(oos_w_veto), first_start, end_idx, cost_bps)
    res_nv = backtest(df, np.nan_to_num(oos_w_noveto), first_start, end_idx, cost_bps)
    bh = buy_and_hold(df, first_start, end_idx)

    return WalkForwardResult(
        oos_equity=res_v.equity,
        oos_returns=res_v.daily_returns,
        oos_weights=res_v.weights,
        oos_metrics=res_v.summary(),
        oos_metrics_noveto=res_nv.summary(),
        benchmark=bh,
        steps=steps,
        oos_period=(df.index[first_start], df.index[end_idx - 1]),
    )
