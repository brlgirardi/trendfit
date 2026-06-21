"""API REST do Buffett Jr — chat conversacional com memoria e contexto ao vivo.

Camada fina sobre trendfit.agents.buffett_jr.BuffettJr. O agente ja ve o mesmo
data layer do cockpit (asset_cockpit), entao quando o front manda o ativo em foco
(`asset`), o Buffett "ve a tela" e prioriza esse ativo na resposta.

Endpoints (prefixo /api/buffett):
  POST /chat              {message, session?, asset?}  -> {reply, session}
  GET  /sessions          -> [{session, title, message_count, last_at}]
  GET  /history/{session} -> [{role, content, created_at}]
  POST /session           -> {session}   (gera id novo de conversa)

LINHA VERMELHA: o agente INFORMA e ACONSELHA. Nunca aciona sinal nem preve preco.
O BuffettJr e instanciado UMA vez (lazy) — carregar o second brain/RAG e caro.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/buffett", tags=["buffett"])

# Singleton lazy: a 1a chamada paga o custo de montar o agente (brain + RAG + LLM).
_AGENT = None
_AGENT_ERROR: str | None = None


def get_agent():
    """Instancia o BuffettJr uma vez. Levanta 503 amigavel se faltar dependencia."""
    global _AGENT, _AGENT_ERROR
    if _AGENT is not None:
        return _AGENT
    if _AGENT_ERROR is not None:
        # Ja falhou antes (ex.: nenhum provider LLM) — nao tenta de novo a cada request.
        raise HTTPException(status_code=503, detail={"error": _AGENT_ERROR})
    try:
        from trendfit.agents.buffett_jr import BuffettJr

        _AGENT = BuffettJr()
        return _AGENT
    except Exception as exc:  # noqa: BLE001 — vira 503 claro pro front
        _AGENT_ERROR = (
            f"Buffett Jr indisponivel: {exc}. Configure um provedor LLM: "
            f"key gratuita do Groq (console.groq.com -> GROQ_API_KEY no .env) "
            f"ou Gemini (aistudio.google.com -> GEMINI_API_KEY)."
        )
        logger.warning(_AGENT_ERROR, exc_info=True)
        raise HTTPException(status_code=503, detail={"error": _AGENT_ERROR}) from exc


class ChatRequest(BaseModel):
    message: str
    session: str | None = None
    asset: str | None = None  # ativo em foco na tela do cockpit (o agente "ve a tela")
    image: str | None = None  # data URL base64 de imagem anexada (print de grafico etc.)


class ChatResponse(BaseModel):
    reply: str
    session: str


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Processa uma mensagem. Cria sessao nova se nenhuma vier. Resposta + session id."""
    message = (req.message or "").strip()
    # Aceita mensagem vazia SE houver imagem anexada (só a imagem ja e um pedido).
    if not message and not req.image:
        raise HTTPException(status_code=400, detail={"error": "campo 'message' vazio"})

    session = req.session or _new_session_id()
    agent = get_agent()
    try:
        reply = agent.chat(message, session=session, focus_asset=req.asset, image=req.image)
    except RuntimeError as exc:  # falha de LLM em runtime (quota/timeout/sem provider)
        raise HTTPException(
            status_code=503,
            detail={
                "error": (
                    f"Buffett Jr nao conseguiu responder: {exc}. "
                    "Provavel falta de provedor LLM — configure GROQ_API_KEY "
                    "(gratis em console.groq.com) ou GEMINI_API_KEY no .env."
                )
            },
        ) from exc
    return ChatResponse(reply=reply, session=session)


@router.get("/sessions")
def sessions() -> list[dict]:
    """Lista as conversas (mais recentes primeiro) para a sidebar de historico."""
    return get_agent().list_sessions()


@router.get("/history/{session}")
def history(session: str) -> list[dict]:
    """Historico cronologico de uma conversa, para render no chat."""
    return get_agent().get_history(session)


@router.post("/session")
def new_session() -> dict:
    """Gera um id de sessao novo (conversa em branco). Nao grava nada ainda."""
    return {"session": _new_session_id()}


def _new_session_id() -> str:
    """Id curto e legivel para a sessao (suficiente para isolar conversas)."""
    return uuid.uuid4().hex[:12]
