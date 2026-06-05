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


def atr(df: pd.DataFrame, window: int = 22) -> np.ndarray:
    """Average True Range — volatilidade para dimensionar o trailing stop."""
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(window).mean().to_numpy()


def donchian_long_asym(high, low, close, entry_lb: int, exit_lb: int) -> np.ndarray:
    """Donchian long-only ASSIMÉTRICO: entra ao romper a máxima de `entry_lb` dias,
    mas só sai ao romper a mínima de `exit_lb` dias (exit_lb > entry_lb => segura
    mais a tendência, aguentando repiques). Estado em {0, 1}."""
    hh = high.rolling(entry_lb).max().shift(1).to_numpy()
    ll = low.rolling(exit_lb).min().shift(1).to_numpy()
    c = close.to_numpy()
    out = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if not np.isnan(hh[i]) and c[i] > hh[i]:
            cur = 1.0
        elif not np.isnan(ll[i]) and c[i] < ll[i]:
            cur = 0.0
        out[i] = cur
    return out


def ensemble_long_asym(df: pd.DataFrame, lookbacks: list[int], asym: float) -> np.ndarray:
    """Ensemble long-only assimétrico em [0,1]: cada membro entra em `lb` e sai em
    `round(lb*asym)`. asym=1 -> canal simétrico; asym>1 -> segura mais a tendência."""
    high, low, close = df["High"], df["Low"], df["Close"]
    acc = np.zeros(len(df))
    for lb in lookbacks:
        exit_lb = max(2, round(lb * asym))
        acc += donchian_long_asym(high, low, close, lb, exit_lb)
    return acc / len(lookbacks)


def _chandelier_overlay(
    w: np.ndarray,
    close: np.ndarray,
    atr_arr: np.ndarray,
    k: float,
    ratchet_gain: float = 0.0,
    ratchet_k: float = 0.0,
) -> np.ndarray:
    """Trailing stop (chandelier): com posição aberta, sai se o preço cair mais de
    k*ATR do topo desde a entrada. Depois de stopado, fica fora até o sinal zerar e
    reabrir (evita reentrada imediata no mesmo dia).

    RATCHET (let-winners-run): se ratchet_gain>0 E ratchet_k>0, quando o trade já
    andou ratchet_gain a favor (pico desde a entrada, ex +30%), o trailing ALARGA de
    k para ratchet_k — protege apertado no começo e deixa a perna já lucrada esticar
    perto do topo. O gatilho usa o PICO (high_since/entry-1), que é monotônico no
    trade, então a catraca TRAVA: uma vez alargada, não re-aperta numa correção. O
    lucro é medido no PREÇO desde a entrada (peso fracionário do ensemble não entra);
    entry_price é fixado no 1º bar do trade e reseta junto com high_since. Com
    ratchet_gain=0 ou ratchet_k=0 o comportamento é idêntico ao trailing k constante."""
    if k <= 0:
        return w
    use_ratchet = ratchet_gain > 0 and ratchet_k > 0
    out = w.copy()
    high_since = None
    entry_price = None
    stopped = False
    for i in range(len(out)):
        if stopped:
            if w[i] == 0:
                stopped = False
            out[i] = 0.0
            continue
        if out[i] > 0:
            if high_since is None:
                entry_price = close[i]
            high_since = close[i] if high_since is None else max(high_since, close[i])
            eff_k = k
            if use_ratchet and entry_price > 0 and high_since / entry_price - 1.0 >= ratchet_gain:
                eff_k = ratchet_k
            if not np.isnan(atr_arr[i]) and close[i] < high_since - eff_k * atr_arr[i]:
                out[i] = 0.0
                stopped = True
                high_since = None
                entry_price = None
        else:
            high_since = None
            entry_price = None
    return out


@dataclass
class StrategyConfig:
    kind: str = "donchian_sym"
    ma_window: int = 200
    band: float = 0.0          # histerese do regime (ex 0.03 = 3%)
    mode: str = "long_only"    # "long_only" | "long_short" | "long_asym"
    min_hold: int = 1          # dias mínimos de cooldown (1 = desligado)
    asym: float = 1.0          # canal de saída = entrada * asym (long_asym)
    atr_window: int = 22       # janela do ATR p/ trailing stop
    atr_k: float = 0.0         # múltiplo de ATR do trailing (0 = desligado)
    ratchet_gain: float = 0.0  # lucro do trade (pico/entrada) p/ alargar o trailing (0 = desligado)
    ratchet_k: float = 0.0     # múltiplo de ATR largo após atingir ratchet_gain (0 = desligado)


def target_weights(df: pd.DataFrame, lookbacks: list[int], cfg: StrategyConfig) -> np.ndarray:
    """Peso-alvo em [-1, +1] combinando ensemble simétrico + regime com histerese.

    long_only : só long, e só quando regime bull (net negativo -> 0).
    long_short: long quando bull+net>0; short quando bear+net<0; senão caixa.
    """
    reg = regime_hysteresis(df["Close"], cfg.ma_window, cfg.band)
    w = np.zeros(len(df))
    if cfg.mode == "long_asym":
        # canal assimétrico (segura a tendência) + veto de regime + trailing ATR
        net = ensemble_long_asym(df, lookbacks, cfg.asym)
        w = np.where(reg > 0, net, 0.0)
        w = _chandelier_overlay(
            w, df["Close"].to_numpy(), atr(df, cfg.atr_window), cfg.atr_k,
            cfg.ratchet_gain, cfg.ratchet_k,
        )
        return _apply_cooldown(w, cfg.min_hold)

    net = ensemble_net(df, lookbacks)
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
