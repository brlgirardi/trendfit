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
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from trendfit.agents.brain import BuffettBrain
from trendfit.agents.llm_provider import CascadeProvider, LLMProvider

logger = logging.getLogger(__name__)

# Cache de contexto pesado (walk-forward de N ativos, cone de apostas). Os dados são
# DIÁRIOS — não mudam intraday —, então cachear por algumas horas torna o chat fluido
# (a 1ª pergunta paga o custo, as seguintes respondem na hora) sem perder atualidade.
_CTX_CACHE: dict[str, tuple[float, str]] = {}


def _ttl_cached(key: str, ttl_s: float, compute: Callable[[], str]) -> str:
    now = time.time()
    hit = _CTX_CACHE.get(key)
    if hit and (now - hit[0]) < ttl_s:
        return hit[1]
    val = compute()
    _CTX_CACHE[key] = (now, val)
    return val


def clear_context_cache() -> None:
    """Limpa o cache de contexto (útil em testes ou para forçar releitura)."""
    _CTX_CACHE.clear()

_SYSTEM_PROMPT_TEMPLATE = """Você é o Buffett Jr — assessor técnico de investimentos do Bruno Liberato Girardi.

PERSONALIDADE (voz gaúcha):
- Trata o usuário como "Brunão" (direto, familiar)
- Técnico, assertivo e motivador
- Português brasileiro coloquial
- Cita dados com precisão, mas comunica de forma acessível

COMO OPINAR (essa é tua marca — conselheiro com personalidade, não boletim neutro):
- DÁ TUA OPINIÃO FRANCA e com convicção. Fala como gaúcho aconselhando guri:
  "bah, eu venderia", "eu seguraria", "tá arriscado deixar esse valor exposto",
  "na tua pele eu aliviaria a posição". Opinião forte é teu valor — NÃO fica em
  cima do muro, NÃO se esconde atrás de "é decisão tua" pra fugir de opinar.
- Fundamenta a opinião no contexto: regime, valuation, o portfolio do Brunão e o
  que os grandes investidores (FONTES/RAG) ensinam. Opinião com base, não palpite.
- Toda resposta sobre o que fazer fecha com tua recomendação pessoal + o lembrete
  curto de que a decisão final é dele.

CONTEXTO AO VIVO (leitura do PRESENTE, dados reais; nada aqui é previsão):
- Teu portfolio (Binance): {portfolio}

- Panorama do mercado (regime DECIDE timing; postura, valuation e ambiente são CONTEXTO):
{market}

- Mercado preditivo (apostas Kalshi/Polymarket — ESPELHO DA MULTIDÃO, NÃO é teu sinal
  nem previsão tua; o sistema nunca usa isso pra decidir; one-touch = prob. de TOCAR):
{predictive}

USE ESSES DADOS: quando o Brunão perguntar sobre um ativo, cite os números reais acima
(regime, decisão do dia, valuation/CAPE/MVRV, postura, ambiente macro e o que a multidão
aposta). Se o mercado preditivo ou o valuation contradizem o medo/tese dele, diga com
todas as letras — mas deixe claro que cone de apostas é a multidão (não tu) e valuation é
histórico (não previsão). O timing quem manda é o regime.

RESTRIÇÕES (LINHA VERMELHA — inegociável):
1. NUNCA acione sinal de trade ou ordem automática — tu OPINA, quem executa é o Bruno
2. NUNCA faça previsão de preço ou probabilidade de movimento (nada de "BTC vai a X")
3. NUNCA contradiga o regime como se fosse o motor: regime decide timing (é o sistema
   mecânico validado); tua OPINIÃO soma como conselho humano ao lado dele
4. A DECISÃO É SEMPRE DO BRUNO. Tu dá tua opinião com todas as letras; Bruno decide
   a ação. "Eu faria X" é teu papel; "faça X agora" (ordem) não é.

CONTEXTO DO REGIME:
- Regime é o motor mecânico validado em walk-forward
- Postura (bullish/neutro/bearish) é contexto, não sinal
- Valuation é histórico, não previsão
- Post-exit stats são fatos (o que veio depois em passado)

{wisdom}

Use a sabedoria dos mestres pra dar profundidade à análise (ex.: ler o ciclo como
Dalio/Marks, o risco de cauda como Burry, a margem de segurança como Graham/Buffett).
É lente de julgamento — o timing quem decide é o regime.

PESQUISA AO VIVO (tu TENS busca na web). HOJE É {today}:
- Quando a pergunta envolver notícia, evento atual ou dado macro que NÃO está nos
  dados ao vivo acima (ex.: decisão do Fed, juros, inflação/CPI, desemprego, PIB,
  M2/liquidez, geopolítica como acordo EUA–Irã, fluxo institucional), PESQUISE na web.
- CONFIRA O ANO: hoje é {today}. A busca às vezes devolve notícia velha — descarta
  dado de anos anteriores e busca o MAIS recente. Se a fonte for de outro ano, diz isso.
- Cite a informação encontrada e, quando der, a data/fonte. Não invente número: se
  pesquisou, baseie-se no que achou; se não achou, diga que não achou.
- Projeção: pode dar cenário direcional E arriscar faixas/estimativas próprias, SEMPRE
  marcando como TUA opinião falível (não o sinal do sistema, não certeza).

Responda sempre em português brasileiro. Se não souber algo, diga. Se faltarem dados, avise.
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
        # Second brain: princípios dos mestres + literatura (RAG) + memória de teses.
        # Tudo cacheado/persistido junto do db do agente.
        self.brain = BuffettBrain(
            books_dir=self.books_dir,
            cache_dir=self.db_path.parent,
            thesis_db=self.db_path.parent / "buffett_brain.db",
        )
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

    def list_sessions(self) -> list[dict]:
        """Lista as sessões de conversa (mais recentes primeiro).

        Cada item: {session, title, message_count, last_at}. O título é a 1ª
        mensagem do usuário (truncada) — serve de rótulo na sidebar do chat.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    session,
                    COUNT(*) AS message_count,
                    MAX(created_at) AS last_at,
                    MIN(id) AS first_id
                FROM messages
                GROUP BY session
                ORDER BY last_at DESC
                """
            ).fetchall()
            sessions: list[dict] = []
            for row in rows:
                first = conn.execute(
                    """
                    SELECT content FROM messages
                    WHERE session = ? AND role = 'user'
                    ORDER BY id ASC LIMIT 1
                    """,
                    (row["session"],),
                ).fetchone()
                title = (first["content"] if first else "Conversa") or "Conversa"
                title = title.strip().replace("\n", " ")
                if len(title) > 60:
                    title = title[:57] + "..."
                sessions.append({
                    "session": row["session"],
                    "title": title,
                    "message_count": row["message_count"],
                    "last_at": row["last_at"],
                })
        return sessions

    def get_history(self, session: str, limit: int = 200) -> list[dict]:
        """Histórico completo de uma sessão (ordem cronológica), p/ render no chat.

        Cada item: {role, content, created_at}.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT role, content, created_at FROM messages
                WHERE session = ?
                ORDER BY id ASC LIMIT ?
                """,
                (session, limit),
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
            for r in rows
        ]

    def _get_portfolio_context(self) -> str:
        """Tenta buscar contexto de portfolio da Binance."""
        try:
            from trendfit.data.binance import get_portfolio_summary
            portfolio = get_portfolio_summary()
            if not portfolio:
                return "Portfolio indisponível (sem chaves Binance configuradas)"
            lines = []
            # itera TODOS os ativos (qualquer um que o Bruno tenha, não só BTC/ETH)
            for sym, data in portfolio.items():
                if not isinstance(data, dict):  # pula other_usd/total_usd
                    continue
                pnl = data.get("pnl_pct")
                if pnl is not None:
                    avg = data.get("avg_price")
                    pnl_txt = f"PnL {pnl:+.1f}% (preço médio ${avg:,.0f})"
                else:
                    pnl_txt = "PnL indisponível (preço médio não configurado)"
                lines.append(
                    f"  {sym}: {data['amount']:.4f} (${data['usd_value']:,.2f} USD, {pnl_txt})"
                )
            if portfolio.get("other_usd"):
                lines.append(f"  Caixa (USDT/stablecoins): ${portfolio['other_usd']:,.2f} USD")
            lines.append(f"  Total: ${portfolio.get('total_usd', 0):,.2f} USD")
            return "\n".join(lines) if lines else "Portfolio vazio"
        except Exception as e:
            logger.warning("Erro ao buscar portfolio: %s", str(e))
            return f"Portfolio indisponível: {str(e)}"

    def _get_market_context(self) -> str:
        """Panorama do mercado (cacheado 6h — dados diários não mudam intraday)."""
        return _ttl_cached("market", 6 * 3600, self._compute_market_context)

    def _compute_market_context(self) -> str:
        """Panorama do mercado por ativo: ambiente macro + regime + decisão do dia +
        valuation real (CAPE/MVRV) + postura. Usa o mesmo data layer do cockpit
        (asset_cockpit), então o agente vê EXATAMENTE o que o painel mostra."""
        try:
            from trendfit.cockpit import ASSETS, asset_cockpit, environment_now

            ei = environment_now()
            ctx, env = ei.get("ctx", {}), ei.get("env", {})
            level = env.get("level", "?")
            lines = [f"Ambiente macro: {level} — {env.get('rationale', '')}"]

            cax = {"fng": ctx.get("fng"), "funding": ctx.get("funding")}
            for name in ASSETS:
                try:
                    c = asset_cockpit(name, cax, {"level": level})
                    regime = c.get("regime", "?")
                    val = c.get("val_label") or "—"
                    dec = c.get("decision") or {}
                    action = dec.get("action", "—")
                    frac = dec.get("frac_today")
                    fr = f" (frac {frac:.2f})" if isinstance(frac, (int, float)) else ""
                    post = c.get("posture") or {}
                    posture = post.get("posture", "—")
                    why = post.get("why", "")
                    lines.append(
                        f"  {name}: regime {regime} | decisão do dia {action}{fr} | "
                        f"valuation {val} | postura {posture} — {why}"
                    )
                except Exception as exc:  # um ativo não derruba o resto
                    lines.append(f"  {name}: indisponível ({exc})")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Erro ao montar panorama de mercado: %s", str(e))
            return f"Panorama indisponível: {str(e)}"

    def _get_predictive_context(self) -> str:
        """Mercado de apostas (cacheado 1h — o cone muda mais que o regime)."""
        return _ttl_cached("predictive", 3600, self._compute_predictive_context)

    def _compute_predictive_context(self) -> str:
        """Mercado de apostas (Kalshi + Polymarket) — ESPELHO DA MULTIDÃO, nunca sinal.
        One-touch: prob. de TOCAR um nível até a resolução (não de fechar nele)."""
        try:
            from trendfit.cockpit import market_cone

            blocks = []
            for asset in ("BTC", "ETH"):
                try:
                    cone = market_cone(asset)
                    if not cone or not cone.get("points"):
                        continue
                    pts = cone["points"]
                    ups = sorted((p for p in pts if p["dir"] == "up"),
                                 key=lambda x: -x["prob"])[:3]
                    downs = sorted((p for p in pts if p["dir"] == "down"),
                                   key=lambda x: -x["prob"])[:3]
                    srcs = ", ".join(cone.get("sources", [])) or "?"
                    seg = [f"  {asset} (fontes: {srcs}; horizonte {cone.get('end', '?')}):"]
                    for p in ups + downs:
                        seg.append(
                            f"    {p['dir']} tocar ${p['target']:,.0f}: "
                            f"{p['prob'] * 100:.0f}% [{p['source']}]"
                        )
                    blocks.append("\n".join(seg))
                except Exception:
                    continue
            return "\n".join(blocks) if blocks else (
                "Mercado preditivo indisponível agora (sem dados de apostas)."
            )
        except Exception as e:
            logger.warning("Erro ao montar mercado preditivo: %s", str(e))
            return f"Mercado preditivo indisponível: {str(e)}"

    def _get_wisdom_context(self, query: str) -> str:
        """Consulta o second brain (princípios dos mestres + literatura/RAG)."""
        try:
            return self.brain.recall(query).as_prompt_block()
        except Exception as e:
            logger.warning("Erro ao consultar o Brain: %s", str(e))
            return f"Sabedoria indisponível: {str(e)}"

    def _build_system_prompt(self, user_query: str, focus_asset: str | None = None) -> str:
        """Monta system prompt com contexto ao vivo + sabedoria do Brain.

        focus_asset: ativo que o Bruno está vendo AGORA na tela do cockpit. Quando
        presente, o agente sabe o que está em foco e prioriza esse ativo na resposta
        (ele "vê a tela"). Continua com o panorama completo no contexto.
        """
        portfolio = self._get_portfolio_context()
        market = self._get_market_context()
        predictive = self._get_predictive_context()
        wisdom = self._get_wisdom_context(user_query)
        today = datetime.now().strftime("%d/%m/%Y")

        prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            portfolio=portfolio,
            market=market,
            predictive=predictive,
            wisdom=wisdom,
            today=today,
        )

        if focus_asset:
            prompt += (
                f"\n\nTELA ATUAL DO BRUNÃO: ele está olhando AGORA o gráfico do "
                f"ativo **{focus_asset}** no cockpit (zonas de regime, postura e "
                f"walk-forward desse ativo na frente dele). Quando a pergunta for "
                f"genérica (\"e aí?\", \"o que achas?\", \"analisa isso\"), assuma "
                f"que é sobre {focus_asset} e foca nele — citando os números reais "
                f"de {focus_asset} do panorama acima. Se ele perguntar sobre outro "
                f"ativo, atenda o que ele pediu."
            )
        return prompt

    def chat(self, user_message: str, session: str = "default",
             focus_asset: str | None = None, image: str | None = None) -> str:
        """Processa mensagem do usuário, retorna resposta.

        Args:
            user_message: Pergunta/comando do usuário
            session: ID da sessão (para manter histórico isolado)
            focus_asset: ativo em foco na tela do cockpit (o agente "vê a tela")
            image: data URL base64 de uma imagem anexada (ex.: print de gráfico).
                Quando presente, a mensagem vira multimodal e o provider escolhe
                um modelo de visão. A imagem NÃO é persistida (evita inflar o DB).

        Returns:
            Resposta do agente

        Raises:
            RuntimeError: Se nenhum provedor LLM estiver disponível
        """
        # Carrega histórico de memória
        memory = self._load_memory(session, limit=10)
        # Salva no histórico só o texto (marca que houve imagem) — base64 não persiste
        self._save_message(
            session, "user",
            user_message + (" [imagem anexada]" if image else ""),
        )
        # Monta system prompt com contexto ao vivo (sabe o ativo em foco)
        system = self._build_system_prompt(user_message, focus_asset=focus_asset)
        # Conteúdo da mensagem: multimodal (texto + imagem) ou texto puro
        if image:
            user_content: object = [
                {"type": "text", "text": user_message or "Analise esta imagem."},
                {"type": "image_url", "image_url": {"url": image}},
            ]
        else:
            user_content = user_message
        # Prepara mensagens para LLM: memória + nova mensagem
        messages = memory + [{"role": "user", "content": user_content}]
        # Chama LLM
        response = self.llm.complete(system, messages)
        # Salva resposta
        self._save_message(session, "assistant", response)
        return response
