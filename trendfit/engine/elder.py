"""Sistema Elder (Triple Screen) — EXPERIMENTO APARTADO do engine principal.

Metodologia de Alexander Elder (Trading for a Living): três telas em timeframes
diferentes para o timing fino de entrada/saída.

  Tela 1 — MARÉ (semanal): MACD-histogram. Define a direção permitida. Só compra
           se a maré semanal está de alta. (Causal: usa só a semana já FECHADA.)
  Tela 2 — ONDA (diário): um oscilador (Force Index do Elder, ou Estocástico) acha
           o PULLBACK contra a maré — oscilador oversold dentro de maré de alta =
           zona de compra (comprar na correção, não no topo).
  Tela 3 — ENTRADA/SAÍDA (diário): entra quando o repique confirma (rompe a máxima
           do dia anterior); sai por stop trailing ATR ou quando a maré vira.

LINHA VERMELHA / regra-mãe do projeto:
- Este módulo é SEPARADO. NÃO toca no engine k=3 (trendfit/engine/strategy.py),
  não realimenta o regime, não vira o sinal oficial. É um candidato a ser validado
  OOS e comparado — só entra em produção se sobreviver ao walk-forward cego.
- Sem look-ahead: a maré semanal é defasada (shift) para usar apenas dados passados.
- Intraday (3º timeframe do Elder clássico) exige coleta de dados intraday — fica
  como extensão futura; esta v1 usa semanal (maré) + diário (onda/entrada), que é o
  Triple Screen praticável com os dados diários que temos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def _ema(x: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(x).ewm(span=span, adjust=False).mean().to_numpy()


def macd_histogram(close: np.ndarray, fast: int = 12, slow: int = 26,
                   signal: int = 9) -> np.ndarray:
    """MACD-histogram = (EMA_fast - EMA_slow) - EMA_signal(MACD)."""
    macd = _ema(close, fast) - _ema(close, slow)
    return macd - _ema(macd, signal)


def force_index(close: np.ndarray, volume: np.ndarray, span: int = 13) -> np.ndarray:
    """Force Index de Elder = EMA(span) de (variação de preço × volume)."""
    chg = np.diff(close, prepend=close[0])
    return _ema(chg * volume, span)


def stochastic_k(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                 n: int = 14) -> np.ndarray:
    """%K do estocástico (0..100). Usado quando não há volume confiável."""
    h = pd.Series(high).rolling(n, min_periods=1).max().to_numpy()
    l = pd.Series(low).rolling(n, min_periods=1).min().to_numpy()
    rng = np.where((h - l) == 0, np.nan, h - l)
    k = 100.0 * (close - l) / rng
    return np.nan_to_num(k, nan=50.0)


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 14) -> np.ndarray:
    """Average True Range (Wilder via EMA)."""
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close),
    ])
    return _ema(tr, window)


@dataclass
class ElderConfig:
    """Parâmetros do Triple Screen (escolhidos só no treino no walk-forward)."""
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    oscillator: str = "force"        # "force" (precisa volume) ou "stoch"
    force_span: int = 13
    stoch_n: int = 14
    stoch_oversold: float = 30.0
    atr_window: int = 14
    atr_k: float = 3.0


def _weekly_tide(df: pd.DataFrame, cfg: ElderConfig) -> np.ndarray:
    """Tela 1 — maré semanal CAUSAL: MACD-hist da semana FECHADA, subindo = alta.

    Reamostra para semanal, calcula o MACD-hist, mede a inclinação (hist sobe = maré
    de alta) e defasa 1 semana (shift) antes de reindexar ao diário — assim cada dia
    só enxerga a maré da última semana já encerrada (sem look-ahead)."""
    wk = df["Close"].resample("W").last().dropna()
    if len(wk) < cfg.macd_slow + cfg.macd_signal + 2:
        return np.zeros(len(df), dtype=bool)
    hist = macd_histogram(wk.to_numpy(), cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    rising = np.zeros(len(wk), dtype=bool)
    rising[1:] = hist[1:] > hist[:-1]
    tide_wk = pd.Series(rising, index=wk.index).shift(1).fillna(False)
    # reindexa para o diário: cada dia herda a maré da última semana fechada
    daily = tide_wk.reindex(df.index, method="ffill").fillna(False)
    return daily.to_numpy().astype(bool)


def triple_screen_position(df: pd.DataFrame, cfg: ElderConfig | None = None) -> np.ndarray:
    """Vetor de posição 0/1 alinhado ao df (long-only). Decisão do dia i usa apenas
    dados até i — o backtest aplica o peso ao retorno de i+1, então é causal."""
    cfg = cfg or ElderConfig()
    n = len(df)
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy() if "High" in df else close
    low = df["Low"].to_numpy() if "Low" in df else close

    tide_up = _weekly_tide(df, cfg)

    # Tela 2 — oscilador no diário (oversold = pullback dentro da maré de alta)
    if cfg.oscillator == "force" and "Volume" in df and df["Volume"].abs().sum() > 0:
        osc = force_index(close, df["Volume"].to_numpy(), cfg.force_span)
        oversold = osc < 0.0  # Force Index negativo = pressão vendedora de curto (pullback)
    else:
        k = stochastic_k(high, low, close, cfg.stoch_n)
        oversold = k < cfg.stoch_oversold

    a = atr(high, low, close, cfg.atr_window)

    pos = np.zeros(n)
    state = 0
    high_since = 0.0
    for i in range(1, n):
        if state == 0:
            # Tela 3: na maré de alta, após pullback (oversold ontem), entra ao romper
            # a máxima do dia anterior (confirmação do repique).
            if tide_up[i] and oversold[i - 1] and high[i] > high[i - 1]:
                state = 1
                high_since = high[i]
        else:
            high_since = max(high_since, high[i])
            stop = high_since - cfg.atr_k * a[i]
            # sai se a maré virou (perde a 1ª tela) ou estourou o trailing stop
            if (not tide_up[i]) or close[i] < stop:
                state = 0
        pos[i] = state
    return pos
