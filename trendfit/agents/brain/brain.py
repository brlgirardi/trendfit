"""BuffettBrain — second brain do Buffett Jr (microsserviço-ready).

Agrega as fontes de conhecimento que dão SABEDORIA ao assessor:
  1. princípios destilados dos mestres (principles.py — knowledge base curada)
  2. literatura (RAG sobre docs/books — cartas, livros, memos; gracioso se vazio)
  3. (extensível) dados macro e memória de teses entram pelo mesmo contrato

Contrato estável (pensado pra virar HTTP sem quebrar):
    recall(query: str) -> BrainResult  →  BrainResult.to_dict() é JSON-serializável

LINHA VERMELHA: o Brain INFORMA o julgamento do assessor. Nunca aciona sinal,
nunca alimenta o engine. Regime decide timing; o Brain dá profundidade.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from trendfit.agents.brain.principles import principles_context, relevant_investors
from trendfit.agents.rag import RagIndex

logger = logging.getLogger(__name__)


@dataclass
class BrainResult:
    """Resultado de uma consulta ao Brain — contrato de saída do microsserviço."""

    query: str
    principles: str = ""           # princípios relevantes dos mestres (texto pronto)
    investors: list[str] = field(default_factory=list)  # quais mestres foram puxados
    literature: list[dict] = field(default_factory=list)  # [{source, score, excerpt}]

    def to_dict(self) -> dict:
        """Serialização estável (HTTP-ready)."""
        return {
            "query": self.query,
            "principles": self.principles,
            "investors": self.investors,
            "literature": self.literature,
        }

    def as_prompt_block(self) -> str:
        """Renderiza o conhecimento pra injetar no system prompt do agente."""
        parts = ["SABEDORIA DOS MESTRES (contexto de julgamento, nunca sinal):",
                 self.principles]
        if self.literature:
            parts.append("\nTrechos da literatura (RAG):")
            for lit in self.literature:
                parts.append(
                    f"  [{lit['source']} | score {lit['score']:.2f}] {lit['excerpt']}"
                )
        else:
            parts.append("\nLiteratura: índice vazio (sem livros/cartas indexados ainda).")
        return "\n".join(parts)


class BuffettBrain:
    """Second brain do Buffett Jr. Desacoplado do agente e do engine."""

    def __init__(
        self,
        books_dir: str | Path = "docs/books",
        cache_dir: str | Path = "db",
        max_investors: int = 3,
        top_k_literature: int = 3,
    ):
        self.max_investors = max_investors
        self.top_k_literature = top_k_literature
        # RAG é opcional/gracioso: se a indexação falhar, o Brain segue só com princípios
        try:
            self.rag: RagIndex | None = RagIndex(books_dir=books_dir, cache_dir=cache_dir)
        except Exception as exc:  # nunca derruba o Brain por causa do RAG
            logger.warning("Brain sem RAG (%s); seguindo só com princípios.", exc)
            self.rag = None

    def recall(self, query: str) -> BrainResult:
        """Consulta o conhecimento relevante à pergunta. Contrato do microsserviço."""
        principles = principles_context(query, limit=self.max_investors)
        investors = relevant_investors(query, limit=self.max_investors)

        literature: list[dict] = []
        if self.rag is not None:
            try:
                for res in self.rag.search(query, top_k=self.top_k_literature):
                    literature.append({
                        "source": res.source,
                        "score": float(res.score),
                        "excerpt": res.chunk[:280],
                    })
            except Exception as exc:
                logger.warning("Brain RAG search falhou (%s); seguindo sem literatura.", exc)

        return BrainResult(
            query=query,
            principles=principles,
            investors=investors,
            literature=literature,
        )
