"""Buffett Brain — second brain do Buffett Jr (microsserviço-ready).

Conhecimento desacoplado: princípios dos mestres + literatura (RAG).
Importa do agente via `from trendfit.agents.brain import BuffettBrain`.
"""

from trendfit.agents.brain.brain import BrainResult, BuffettBrain
from trendfit.agents.brain.principles import (
    INVESTORS,
    SHARED_WISDOM,
    principles_context,
    relevant_investors,
)

__all__ = [
    "BuffettBrain",
    "BrainResult",
    "INVESTORS",
    "SHARED_WISDOM",
    "principles_context",
    "relevant_investors",
]
