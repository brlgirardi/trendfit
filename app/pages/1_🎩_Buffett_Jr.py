"""Página de chat do Buffett Jr no cockpit (Streamlit multipage).

Aba separada — não toca no cockpit principal. Conversa com o assessor usando o mesmo
agente do terminal (Brain + dados ao vivo + busca web), com histórico persistido.

LINHA VERMELHA: informa e opina; nunca aciona ordem nem prevê preço como certeza.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trendfit.agents import BuffettJr  # noqa: E402

st.set_page_config(page_title="Buffett Jr", page_icon="🎩", layout="wide")

st.title("🎩 Buffett Jr — teu assessor")
st.caption(
    "Opina com a sabedoria dos mestres + teus dados ao vivo (regime, portfolio, cone, "
    "macro) e pesquisa na web. **Nunca aciona ordem nem prevê preço como certeza — o "
    "regime decide o timing, a decisão é sempre tua.**"
)

SESSION = "cockpit"


@st.cache_resource(show_spinner=False)
def _agent() -> BuffettJr:
    """Instancia o agente uma vez (indexa o Brain só na primeira carga)."""
    return BuffettJr(
        db_path=str(ROOT / "db" / "buffett_jr.db"),
        books_dir=str(ROOT / "docs" / "books"),
    )


def _load_history() -> list[dict]:
    try:
        mem = _agent()._load_memory(SESSION, limit=30)
        return [{"role": m["role"], "content": m["content"]} for m in mem]
    except Exception:
        return []


if "bj_messages" not in st.session_state:
    st.session_state.bj_messages = _load_history()

# barra de ações
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🧹 Limpar tela", width="stretch",
                 help="Limpa a conversa exibida (o histórico no banco é mantido)."):
        st.session_state.bj_messages = []
        st.rerun()

if not st.session_state.bj_messages:
    st.info("Manda a primeira pergunta — ex.: *\"Vale segurar meu BTC hoje?\"*, "
            "*\"O que o Dalio diria do macro agora?\"*, *\"Pesquisa o último dado do Fed.\"*")

# histórico
for m in st.session_state.bj_messages:
    is_user = m["role"] == "user"
    with st.chat_message("user" if is_user else "assistant", avatar="🧑" if is_user else "🎩"):
        st.markdown(m["content"])

# entrada
prompt = st.chat_input("Pergunta pro Buffett Jr…")
if prompt:
    st.session_state.bj_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="🎩"):
        with st.spinner("Lendo regime, macro e pesquisando ao vivo… (pode levar até 1 min)"):
            try:
                resp = _agent().chat(prompt, session=SESSION)
            except Exception as exc:
                resp = (f"⚠️ Não consegui responder agora: `{exc}`\n\n"
                        "Verifica se o `gemini` CLI está logado (ou se há uma API key de "
                        "LLM no `.env`). O resto do cockpit segue funcionando normalmente.")
        st.markdown(resp)
    st.session_state.bj_messages.append({"role": "assistant", "content": resp})
