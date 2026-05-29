"""Estratégia generalizada v2: Donchian simétrico (long/short) + regime com
histerese + cooldown anti-whipsaw.

Motivação (diagnóstico do núcleo v1): breakout puro compra topo/vende fundo e o
veto MA200 sem banda pica a posição perto da linha (39 viradas, 88% das recompras
acima da saída anterior). Esta versão ataca as duas causas:

  1. Donchian SIMÉTRICO: estado em {-1, +1} (stop-and-reverse) — permite short.
  2. Regime com BANDA DE HISTERESE: só vira bear abaixo de MA*(1-band) e só volta
     a bull acima de MA*(1+band); na zona morta mantém o regime anterior.
  3. COOLDOWN: trava mudanças de direção por N dias após uma mudança, cortando a
     pipoca de <=5 dias.

Cada parâmetro novo é poucos graus de liberdade e deve provar valor no
walk-forward OOS — não é para "consertar o gráfico" e sim para ganhar em
retorno/risco fora da amostra.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def donchian_state_symmetric(high: pd.Series, low: pd.Series, close: pd.Series, lb: int) -> np.ndarray:
    """Estado simétrico em {-1, +1}: +1 ao romper a máxima de N dias, -1 ao romper
    a mínima. Mantém o estado entre rupturas (stop-and-reverse). 0 só antes da 1ª ruptura."""
    hh = high.rolling(lb).max().shift(1).to_numpy()
    ll = low.rolling(lb).min().shift(1).to_numpy()
    c = close.to_numpy()
    out = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if not np.isnan(hh[i]) and c[i] > hh[i]:
            cur = 1.0
        elif not np.isnan(ll[i]) and c[i] < ll[i]:
            cur = -1.0
        out[i] = cur
    return out


def ensemble_net(df: pd.DataFrame, lookbacks: list[int]) -> np.ndarray:
    """Posição líquida do ensemble em [-1, +1] = média dos estados simétricos."""
    high, low, close = df["High"], df["Low"], df["Close"]
    acc = np.zeros(len(df))
    for lb in lookbacks:
        acc += donchian_state_symmetric(high, low, close, lb)
    return acc / len(lookbacks)


def regime_hysteresis(close: pd.Series, ma_window: int, band: float) -> np.ndarray:
    """Regime em {-1, 0, +1} com histerese. +1 quando close > MA*(1+band);
    -1 quando close < MA*(1-band); na zona morta mantém o estado anterior.
    0 apenas antes de haver MA suficiente."""
    ma = close.rolling(ma_window).mean().to_numpy()
    c = close.to_numpy()
    out = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if np.isnan(ma[i]):
            out[i] = 0.0
            continue
        if c[i] > ma[i] * (1 + band):
            cur = 1.0
        elif c[i] < ma[i] * (1 - band):
            cur = -1.0
        # zona morta: mantém cur
        out[i] = cur
    return out


def _apply_cooldown(w: np.ndarray, min_hold: int) -> np.ndarray:
    """Após uma mudança de peso, segura o novo peso por min_hold dias (ignora novas
    mudanças nesse intervalo). Corta a pipoca de trades muito curtos."""
    if min_hold <= 1:
        return w
    out = w.copy()
    last_change = -min_hold
    for i in range(1, len(out)):
        if i - last_change < min_hold:
            out[i] = out[i - 1]  # congela
        elif out[i] != out[i - 1]:
            last_change = i
    return out


@dataclass
class StrategyConfig:
    kind: str = "donchian_sym"
    ma_window: int = 200
    band: float = 0.0          # histerese do regime (ex 0.03 = 3%)
    mode: str = "long_only"    # "long_only" | "long_short"
    min_hold: int = 1          # dias mínimos de cooldown (1 = desligado)


def target_weights(df: pd.DataFrame, lookbacks: list[int], cfg: StrategyConfig) -> np.ndarray:
    """Peso-alvo em [-1, +1] combinando ensemble simétrico + regime com histerese.

    long_only : só long, e só quando regime bull (net negativo -> 0).
    long_short: long quando bull+net>0; short quando bear+net<0; senão caixa.
    """
    net = ensemble_net(df, lookbacks)
    reg = regime_hysteresis(df["Close"], cfg.ma_window, cfg.band)
    w = np.zeros(len(df))
    if cfg.mode == "long_only":
        long_mask = (reg > 0) & (net > 0)
        w[long_mask] = net[long_mask]
    elif cfg.mode == "long_short":
        long_mask = (reg > 0) & (net > 0)
        short_mask = (reg < 0) & (net < 0)
        w[long_mask] = net[long_mask]
        w[short_mask] = net[short_mask]
    else:
        raise ValueError(f"mode desconhecido: {cfg.mode!r}")
    return _apply_cooldown(w, cfg.min_hold)
