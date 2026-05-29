"""Camadas de confluência. Sprint 1: apenas o veto de regime v1 (MA200).

Fases futuras adicionam on-chain (MVRV, ETF flow), macro (FRED) e sentimento.
A interface é estável: cada camada devolve um vetor booleano `allow` alinhado
ao índice do DataFrame, dizendo se o regime permite exposição naquele dia.
"""

from trendfit.layers.regime import regime_allow

__all__ = ["regime_allow"]
