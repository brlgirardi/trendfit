"""TrendFit — sistema de trading multi-ativo por confluência.

Núcleo: ensemble trend-following (Donchian/HiLo multi-lookback) + veto de
regime + walk-forward multi-ciclo, com seleção por retorno/risco.

A IA entra como filtro de contexto e veto — nunca como gerador de sinal.
"""

__version__ = "0.1.0"
