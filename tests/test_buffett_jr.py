"""Testes para BuffettJr e LLMProvider (sem rede real)."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trendfit.agents.buffett_jr import BuffettJr
from trendfit.agents.llm_provider import (
    CascadeProvider,
    GeminiProvider,
    GroqProvider,
    LLMProvider,
    MoonShotProvider,
)


class FakeLLMProvider(LLMProvider):
    """Provider fake para testes (sem rede)."""

    def __init__(self, response: str = "Entendido, Brunão."):
        self.response = response
        self.call_count = 0
        self.last_system = None
        self.last_messages = None

    def complete(self, system: str, messages: list[dict]) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_messages = messages
        return self.response


class FailingLLMProvider(LLMProvider):
    """Provider que sempre falha (para testes de failover)."""

    def complete(self, system: str, messages: list[dict]) -> str:
        raise RuntimeError("Provider falhou propositalmente")


@pytest.fixture
def temp_db():
    """Cria diretório temporário para SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "buffett_jr.db"


@pytest.fixture
def temp_books_dir():
    """Cria diretório temporário para docs/books."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def fake_llm():
    """Provider fake para testes."""
    return FakeLLMProvider(response="Beleza, Brunão. Análise pronta.")


def test_buffett_jr_init(temp_db, temp_books_dir, fake_llm):
    """Testa inicialização do BuffettJr."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)
    # resolve() pois no macOS /tmp é symlink de /private/tmp
    assert agent.db_path == temp_db.resolve()
    assert agent.llm is fake_llm
    assert temp_db.exists()  # DB criado


def test_buffett_jr_memory_persistence(temp_db, temp_books_dir, fake_llm):
    """Testa persistência de memória SQLite."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    # Salva mensagens
    agent._save_message("session1", "user", "Qual é a postura hoje?")
    agent._save_message("session1", "assistant", "Bullish no BTC.")
    agent._save_message("session1", "user", "E no ETH?")

    # Carrega memória
    memory = agent._load_memory("session1")
    assert len(memory) == 3
    assert memory[0]["content"] == "Qual é a postura hoje?"
    assert memory[1]["content"] == "Bullish no BTC."
    assert memory[2]["content"] == "E no ETH?"


def test_buffett_jr_memory_isolation(temp_db, temp_books_dir, fake_llm):
    """Testa isolamento entre sessões."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    # Sessão 1
    agent._save_message("session1", "user", "Pergunta da sessão 1")
    # Sessão 2
    agent._save_message("session2", "user", "Pergunta da sessão 2")

    # Carrega cada sessão
    mem1 = agent._load_memory("session1")
    mem2 = agent._load_memory("session2")

    assert len(mem1) == 1
    assert len(mem2) == 1
    assert mem1[0]["content"] == "Pergunta da sessão 1"
    assert mem2[0]["content"] == "Pergunta da sessão 2"


def test_buffett_jr_chat(temp_db, temp_books_dir, fake_llm):
    """Testa fluxo de chat."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    response = agent.chat("Qual é a postura?", session="test")
    assert response == "Beleza, Brunão. Análise pronta."

    # Verifica que foi salvo em memória
    memory = agent._load_memory("test")
    assert len(memory) == 2  # user + assistant
    assert memory[0]["role"] == "user"
    assert memory[1]["role"] == "assistant"


def test_buffett_jr_system_prompt_contains_redlines(temp_db, temp_books_dir, fake_llm):
    """Verifica que system prompt contém LINHA VERMELHA (restrições de trade/previsão)."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    # Dispara um chat para capturar o system prompt
    agent.chat("Test", session="test_redlines")

    system_prompt = fake_llm.last_system
    assert "NUNCA acione sinal de trade" in system_prompt
    assert "NUNCA faça previsão de preço" in system_prompt
    assert "NUNCA contradiga o regime" in system_prompt
    assert "regime decide timing" in system_prompt
    assert "Bruno decide" in system_prompt


def test_buffett_jr_system_prompt_includes_context(temp_db, temp_books_dir, fake_llm):
    """Verifica que system prompt inclui contexto ao vivo."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    agent.chat("Contexto?", session="test_context")
    system_prompt = fake_llm.last_system

    # Deve incluir seções de contexto (mesmo que indisponíveis)
    assert "Portfolio:" in system_prompt
    assert "Decisão do dia" in system_prompt
    assert "Ativos monitorados:" in system_prompt


def test_buffett_jr_graceful_degradation_no_binance(temp_db, temp_books_dir, fake_llm):
    """Testa degradação graciosa sem Binance (sem crash)."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    # Sem BINANCE_API_KEY, deve retornar aviso, não crash
    portfolio = agent._get_portfolio_context()
    assert isinstance(portfolio, str)
    assert len(portfolio) > 0
    # Pode ser "indisponível" ou um erro controlado
    assert "indisponível" in portfolio.lower() or "erro" in portfolio.lower()


def test_buffett_jr_graceful_degradation_no_rag(temp_db, temp_books_dir, fake_llm):
    """Testa degradação graciosa com RAG vazio (sem crash)."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    # RAG vazio (books_dir vazio) não deve crash
    rag_context = agent._get_rag_context("Teste")
    assert isinstance(rag_context, str)
    assert len(rag_context) > 0


def test_cascade_provider_init_no_keys():
    """Testa que CascadeProvider falha se nenhuma chave disponível."""
    with patch.dict("os.environ", {}, clear=False):
        # Remove todas as chaves de API
        for key in ["GEMINI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY"]:
            try:
                del __import__("os").environ[key]
            except KeyError:
                pass
        with pytest.raises(RuntimeError, match="Nenhum provedor LLM disponível"):
            CascadeProvider()


def test_cascade_provider_failover():
    """Testa failover automático entre provedores."""
    failing = FailingLLMProvider()
    good = FakeLLMProvider(response="Backup OK")

    cascade = CascadeProvider(providers=[failing, good])
    response = cascade.complete("system", [{"role": "user", "content": "test"}])
    assert response == "Backup OK"


def test_cascade_provider_all_fail():
    """Testa erro quando todos os provedores falham."""
    failing1 = FailingLLMProvider()
    failing2 = FailingLLMProvider()

    cascade = CascadeProvider(providers=[failing1, failing2])
    with pytest.raises(RuntimeError, match="Todos os provedores falharam"):
        cascade.complete("system", [{"role": "user", "content": "test"}])


@pytest.fixture
def no_api_keys():
    """Remove API keys do ambiente (isola testes de rede real)."""
    with patch.dict("os.environ", {}, clear=False):
        for key in ["GEMINI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY"]:
            os.environ.pop(key, None)
        yield


def test_gemini_provider_missing_key(no_api_keys):
    """Testa GeminiProvider sem key."""
    provider = GeminiProvider(api_key="")
    with pytest.raises(RuntimeError, match="API_KEY não configurada"):
        provider.complete("system", [])


def test_moonshot_provider_missing_key(no_api_keys):
    """Testa MoonShotProvider sem key."""
    provider = MoonShotProvider(api_key="")
    with pytest.raises(RuntimeError, match="API_KEY não configurada"):
        provider.complete("system", [])


def test_groq_provider_missing_key(no_api_keys):
    """Testa GroqProvider sem key."""
    provider = GroqProvider(api_key="")
    with pytest.raises(RuntimeError, match="API_KEY não configurada"):
        provider.complete("system", [])


def test_buffett_jr_memory_limit(temp_db, temp_books_dir, fake_llm):
    """Testa que apenas últimas N mensagens são carregadas."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    # Salva 20 mensagens
    for i in range(20):
        agent._save_message("big_session", "user", f"Message {i}")

    # Carrega últimas 10
    memory = agent._load_memory("big_session", limit=10)
    assert len(memory) == 10
    # Verificar que são as últimas (ordem preservada)
    assert "Message 10" in memory[0]["content"]
    assert "Message 19" in memory[9]["content"]


def test_buffett_jr_chat_includes_memory(temp_db, temp_books_dir, fake_llm):
    """Testa que chat envia histórico para LLM."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    # Primeira mensagem
    agent.chat("Pergunta 1", session="conv")
    # Segunda mensagem
    agent.chat("Pergunta 2", session="conv")

    # Verifica que last_messages inclui ambas
    messages = fake_llm.last_messages
    assert any("Pergunta 1" in m.get("content", "") for m in messages)
    assert any("Pergunta 2" in m.get("content", "") for m in messages)


def test_buffett_jr_system_prompt_has_voz_gaucha(temp_db, temp_books_dir, fake_llm):
    """Verifica voz gaúcha (Brunão, direto, técnico)."""
    agent = BuffettJr(llm_provider=fake_llm, db_path=temp_db, books_dir=temp_books_dir)

    agent.chat("Oi", session="voz_test")
    system_prompt = fake_llm.last_system

    # Deve mencionar "Brunão"
    assert "Brunão" in system_prompt
    # Deve ter instruções técnicas
    assert "LINHA VERMELHA" in system_prompt or "inegociável" in system_prompt.lower()
