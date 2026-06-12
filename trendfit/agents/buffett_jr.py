"""BuffettJr — agente conversacional com contexto ao vivo e RAG.

Memória SQLite em db/buffett_jr.db. Injeção contextual via portfolio + asset_cockpit.
RAG integrado via RagIndex sobre docs/books/ (gracioso se vazio).

LINHA VERMELHA (inegociável, no system prompt e garantida por testes):
- Agente INFORMA postura e ACONSELHA — nunca aciona sinal de trade
- Nunca prevê preço ou probabilidade de movimento
- Nunca contradiz o regime (regime decide timing, Bruno decide ação)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from trendfit.agents.llm_provider import CascadeProvider, LLMProvider
from trendfit.agents.rag import RagIndex, RagResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """Você é o Buffett Jr — assessor técnico de investimentos do Bruno Liberato Girardi.

PERSONALIDADE (voz gaúcha):
- Trata o usuário como "Brunão" (direto, familiar)
- Técnico, assertivo e motivador
- Português brasileiro coloquial
- Cita dados com precisão, mas comunica de forma acessível
- Opinião forte quando há base técnica

CONTEXTO AO VIVO (dados atualizados no momento):
- Portfolio: {portfolio}
- Decisão do dia (regime mecânico): {decision}
- Ativos monitorados: {assets}

RESTRIÇÕES (LINHA VERMELHA — inegociável):
1. NUNCA acione sinal de trade ou ordem
2. NUNCA faça previsão de preço ou probabilidade de movimento
3. NUNCA contradiga o regime (regime decide timing, Bruno decide a ação)
4. Seu papel é INFORMAR postura, contexto, estatísticas — ACONSELHAR estratégia
5. Se perguntarem sobre trade, diga: "Isso é decisão tua — regime já marcou caminho"

CONTEXTO DO REGIME:
- Regime é o motor mecânico validado em walk-forward
- Postura (bullish/neutro/bearish) é contexto, não sinal
- Valuation é histórico, não previsão
- Post-exit stats são fatos (o que veio depois em passado)

FONTES:
{rag_context}

Responda sempre em português brasileiro. Se não souber algo, diga. Se faltarem dados (Binance/RAG), avise.
"""


class BuffettJr:
    """Agente conversacional com memória SQLite e contexto ao vivo."""

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        db_path: str | Path = "db/buffett_jr.db",
        books_dir: str | Path = "docs/books",
    ):
        self.db_path = Path(db_path).resolve()
        self.books_dir = Path(books_dir).resolve()
        self.llm = llm_provider or CascadeProvider()
        self.rag = RagIndex(books_dir=self.books_dir)
        self._init_db()

    def _init_db(self) -> None:
        """Cria tabela de memória conversacional se não existir."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _load_memory(self, session: str, limit: int = 10) -> list[dict]:
        """Carrega últimas N mensagens da sessão."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session = ?
                ORDER BY id DESC LIMIT ?
                """,
                (session, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def _save_message(self, session: str, role: str, content: str) -> None:
        """Salva mensagem na memória SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO messages (session, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session, role, content, datetime.now().isoformat()),
            )
            conn.commit()

    def _get_portfolio_context(self) -> str:
        """Tenta buscar contexto de portfolio da Binance."""
        try:
            from trendfit.data.binance import get_portfolio_summary
            portfolio = get_portfolio_summary()
            if not portfolio:
                return "Portfolio indisponível (sem chaves Binance configuradas)"
            lines = []
            for sym in ["BTC", "ETH"]:
                if sym in portfolio:
                    data = portfolio[sym]
                    lines.append(
                        f"  {sym}: {data['amount']:.4f} ({data['usd_value']}$ USD, "
                        f"PnL {data.get('pnl_pct', 'N/A')}%)"
                    )
            if portfolio.get("other_usd"):
                lines.append(f"  USDT/Outros: {portfolio['other_usd']}$ USD")
            lines.append(f"  Total: {portfolio.get('total_usd', 'N/A')}$ USD")
            return "\n".join(lines) if lines else "Portfolio vazio"
        except Exception as e:
            logger.warning("Erro ao buscar portfolio: %s", str(e))
            return f"Portfolio indisponível: {str(e)}"

    def _get_decision_context(self) -> str:
        """Tenta buscar decisão do dia (regime mecânico)."""
        try:
            from trendfit.cockpit import daily_decision, environment_now, load_asset_df
            from trendfit.engine.walkforward import walk_forward_grid
            from trendfit.engine.strategy import target_weights, StrategyConfig
            from trendfit.cockpit import ASSETS, load_profile, _candidates
            import pandas as pd

            prof = load_profile()
            e, w, g = prof["engine"], prof["walkforward"], prof["grid"]

            lines = []
            for asset_name in ASSETS.keys():
                try:
                    df = load_asset_df(asset_name)
                    if len(df) < (w["train_days"] + w["test_days"] + 30):
                        continue

                    cands = _candidates(e, g)
                    wf = walk_forward_grid(
                        df, cands, train_days=w["train_days"], test_days=w["test_days"],
                        cost_bps=e["cost_bps"]
                    )
                    last = wf.steps[-1]
                    cfg = StrategyConfig(
                        ma_window=e["ma_window"],
                        band=float(last.chosen.split("|b")[1].split("|")[0]),
                        mode="long_asym",
                        asym=float(last.chosen.split("|a")[1].split("|")[0]),
                        atr_k=float(last.chosen.split("|k")[1])
                    )
                    w_live = pd.Series(target_weights(df, last.lookbacks, cfg), index=df.index)
                    dec = daily_decision(w_live, [], df["Close"])
                    if dec:
                        action = dec.get("action", "?")
                        lines.append(f"  {asset_name}: {action} (frac={dec.get('frac_today', 0):.2f})")
                except Exception:
                    pass

            return "\n".join(lines) if lines else "Decisão indisponível (sem histórico suficiente)"
        except Exception as e:
            logger.warning("Erro ao buscar decisão: %s", str(e))
            return f"Decisão indisponível: {str(e)}"

    def _get_assets_context(self) -> str:
        """Tenta buscar lista de ativos monitorados."""
        try:
            from trendfit.cockpit import list_assets
            assets = list_assets()
            return ", ".join(assets) if assets else "Nenhum ativo configurado"
        except Exception as e:
            logger.warning("Erro ao buscar ativos: %s", str(e))
            return f"Ativos indisponíveis: {str(e)}"

    def _get_rag_context(self, query: str) -> str:
        """Busca contexto RAG relevante (ou nota se índice vazio)."""
        try:
            results = self.rag.search(query, top_k=3)
            if not results:
                return "RAG: nenhum documento relevante encontrado (índice vazio?)"
            lines = ["RAG (livros):"]
            for res in results:
                lines.append(f"  [{res.source} | score {res.score:.2f}] {res.chunk[:200]}...")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Erro RAG: %s", str(e))
            return f"RAG indisponível: {str(e)}"

    def _build_system_prompt(self, user_query: str) -> str:
        """Monta system prompt com contexto ao vivo."""
        portfolio = self._get_portfolio_context()
        decision = self._get_decision_context()
        assets = self._get_assets_context()
        rag = self._get_rag_context(user_query)

        return _SYSTEM_PROMPT_TEMPLATE.format(
            portfolio=portfolio,
            decision=decision,
            assets=assets,
            rag_context=rag,
        )

    def chat(self, user_message: str, session: str = "default") -> str:
        """Processa mensagem do usuário, retorna resposta.

        Args:
            user_message: Pergunta/comando do usuário
            session: ID da sessão (para manter histórico isolado)

        Returns:
            Resposta do agente

        Raises:
            RuntimeError: Se nenhum provedor LLM estiver disponível
        """
        # Carrega histórico de memória
        memory = self._load_memory(session, limit=10)
        # Salva mensagem do usuário
        self._save_message(session, "user", user_message)
        # Monta system prompt com contexto ao vivo
        system = self._build_system_prompt(user_message)
        # Prepara mensagens para LLM: memória + nova mensagem
        messages = memory + [{"role": "user", "content": user_message}]
        # Chama LLM
        response = self.llm.complete(system, messages)
        # Salva resposta
        self._save_message(session, "assistant", response)
        return response
