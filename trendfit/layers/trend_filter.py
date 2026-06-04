"""Filtro anti-chop (Fase 3d) — não operar quando NÃO há tendência (mercado lateral).

Ataca o whipsaw: os trades-pipoca acontecem no lateral (preço grudado na MA, sem
direção). Em vez de tentar adivinhar topo/fundo (mean-reversion, refutada), este filtro
mede a FORÇA da tendência e reduz exposição quando ela é fraca — deixando o sistema
operar só quando há tendência de verdade pra capturar.

Duas medidas causais (sem look-ahead, entram com shift(1)):
  - ADX (Average Directional Index): clássico de força de tendência. ADX baixo = chop.
  - Inclinação da MA200: MA horizontal = lateral; subindo = tendência.

Cada uma vira um fator de exposição em [floor, 1]. threshold/floor são dimensão do grid
(escolha só no treino). 'off' sempre candidato — o sistema pode declinar o filtro.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ADX de Wilder (0..100). Mede força da tendência, não direção. Causal."""
    high, low, close = df["High"], df["Low"], df["Close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([(high - low),
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def adx_factor(df: pd.DataFrame, adx_lo: float = 15.0, adx_hi: float = 25.0,
               floor: float = 0.0, period: int = 14) -> np.ndarray:
    """Fator [floor, 1]: 1 quando ADX >= adx_hi (tendência forte), floor quando ADX <= adx_lo
    (chop), rampa linear no meio. Causal (shift(1))."""
    a = adx(df, period).shift(1)
    ramp = ((a - adx_lo) / (adx_hi - adx_lo)).clip(lower=0.0, upper=1.0)
    return (floor + (1.0 - floor) * ramp).fillna(1.0).to_numpy()


def maslope_factor(df: pd.DataFrame, ma_window: int = 200, slope_window: int = 20,
                   thr: float = 0.0, floor: float = 0.0) -> np.ndarray:
    """Fator [floor, 1] pela inclinação da MA: 1 quando a MA sobe (>thr), floor quando
    horizontal/cai. thr é a inclinação relativa mínima (ex. 0.0 = qualquer alta). Causal."""
    ma = df["Close"].rolling(ma_window).mean()
    slope = (ma - ma.shift(slope_window)) / ma.shift(slope_window)
    slope = slope.shift(1)
    # rampa de thr a thr+escala (escala = 0.05 sobre slope_window): floor->1
    ramp = ((slope - thr) / 0.05).clip(lower=0.0, upper=1.0)
    return (floor + (1.0 - floor) * ramp).fillna(1.0).to_numpy()
