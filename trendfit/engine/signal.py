"""Leitura do sinal atual do sistema (núcleo + veto) para o último dado disponível.

NÃO é recomendação de investimento — é a saída mecânica do sistema na última barra.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trendfit.engine.indicators import STATE_FUNCS
from trendfit.layers.regime import regime_allow


def position_events(weights: pd.Series, price: pd.Series, threshold: float = 0.01) -> pd.DataFrame:
    """Converte a série de pesos (0..1) em eventos discretos de entrada/saída.

    Retorna um DataFrame com colunas: date, kind, w_from, w_to, price, label.
    kind ∈ {entry, scale_in, scale_out, exit}. Como o núcleo é long-only, não há
    short — "exit" é ir para caixa (peso 0), seja por rompimento ou por veto.
    """
    w = weights.reindex(price.index).fillna(0.0)
    prev = w.shift(1).fillna(0.0)
    delta = w - prev
    events = []
    for date, d in delta.items():
        if abs(d) < threshold:
            continue
        wf, wt = float(prev[date]), float(w[date])
        if d > 0:
            kind = "entry" if wf <= threshold else "scale_in"
        else:
            kind = "exit" if wt <= threshold else "scale_out"
        label = {
            "entry": "Entrada LONG",
            "scale_in": "Aumenta posição",
            "scale_out": "Reduz posição",
            "exit": "Saída (caixa)",
        }[kind]
        events.append(
            {
                "date": date,
                "kind": kind,
                "w_from": wf,
                "w_to": wt,
                "price": float(price.get(date, np.nan)),
                "label": f"{label} {wf*100:.0f}%→{wt*100:.0f}%",
            }
        )
    return pd.DataFrame(events)


def paired_trades(weights: pd.Series, price: pd.Series, threshold: float = 0.05) -> pd.DataFrame:
    """Pareia entradas (caixa->comprado) com saídas (comprado->caixa) em trades completos,
    com o RESULTADO de cada um. Colunas: entry, exit, p_in, p_out, ret, win, days, open.

    Um trade ainda aberto (sem saída até a última barra) é fechado virtualmente no último
    preço (open=True), pra mostrar o resultado corrente. Resultado long: p_out/p_in - 1.
    """
    ev = position_events(weights, price, threshold=threshold)
    rows, op = [], None
    for _, r in ev.iterrows():
        if r["kind"] == "entry":
            op = r
        elif r["kind"] == "exit" and op is not None:
            ret = r["price"] / op["price"] - 1
            rows.append({"entry": op["date"], "exit": r["date"], "p_in": op["price"],
                         "p_out": r["price"], "ret": ret, "win": ret > 0,
                         "days": (r["date"] - op["date"]).days, "open": False})
            op = None
    if op is not None:  # trade aberto até hoje
        last_d, last_p = price.index[-1], float(price.iloc[-1])
        ret = last_p / op["price"] - 1
        rows.append({"entry": op["date"], "exit": last_d, "p_in": op["price"], "p_out": last_p,
                     "ret": ret, "win": ret > 0, "days": (last_d - op["date"]).days, "open": True})
    return pd.DataFrame(rows)


@dataclass
class CurrentSignal:
    date: pd.Timestamp
    price: float
    ensemble_vote: float          # 0..1 (fração de lookbacks long)
    per_lookback: dict[int, bool]
    regime_bull: bool
    ma_value: float
    recommended_weight: float     # voto * veto
    reading: str


def current_signal(
    df: pd.DataFrame,
    lookbacks: list[int],
    kind: str = "donchian",
    ma_window: int = 200,
) -> CurrentSignal:
    func = STATE_FUNCS[kind]
    high, low, close = df["High"], df["Low"], df["Close"]
    per_lb = {}
    votes = 0.0
    for lb in lookbacks:
        st = func(high, low, close, lb)
        long_now = bool(st[-1] > 0)
        per_lb[lb] = long_now
        votes += st[-1]
    vote = votes / len(lookbacks)

    allow = regime_allow(df, ma_window)
    ma = df["Close"].rolling(ma_window).mean().to_numpy()
    bull = bool(allow[-1])
    weight = vote if bull else 0.0

    if weight >= 0.66:
        reading = "COMPRADO forte — tendência confirmada"
    elif weight >= 0.33:
        reading = "PARCIAL — tendência mista"
    elif weight > 0:
        reading = "LEVE — sinal fraco"
    else:
        reading = "FORA — sem tendência de alta confirmada / regime bear"

    return CurrentSignal(
        date=df.index[-1],
        price=float(df["Close"].iloc[-1]),
        ensemble_vote=vote,
        per_lookback=per_lb,
        regime_bull=bull,
        ma_value=float(ma[-1]) if not np.isnan(ma[-1]) else float("nan"),
        recommended_weight=weight,
        reading=reading,
    )
