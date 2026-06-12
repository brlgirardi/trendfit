"""Testes para o pipeline RAG."""

import json
import tempfile
from pathlib import Path

import pytest

from trendfit.agents.rag import RagIndex


@pytest.fixture
def temp_books_dir():
    """Cria diretório temporário para testes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_cache_dir():
    """Cria diretório temporário para cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_corpus(temp_books_dir):
    """Cria corpus de teste com vários textos."""
    texts = {
        "buffett.txt": """
        Warren Buffett on Long-term Value

        A essência do investimento bem-sucedido é comprar empresas excelentes
        por preços razoáveis. O mercado oferece oportunidades constantes onde
        preço de mercado diverge significativamente do valor intrínseco.

        O tempo é nosso maior aliado. Quanto mais longamente uma empresa ganha
        retornos superiores sobre capital, mais valor criará para acionistas.
        A paciência é a marca registrada do investidor inteligente.

        As melhores oportunidades vêm de discrepâncias criadas pelo pânico
        irracional. Medo é a emoção que mais distorce preços de mercado.
        """,
        "graham.txt": """
        Benjamin Graham on Margin of Safety

        A essência da abordagem defensiva é a margem de segurança. Não se deve
        comprar uma ação exceto com desconto substancial em relação ao seu
        valor calculado.

        O investidor deve sempre considerar o pior cenário possível. Se mesmo
        nesse cenário houver retorno aceitável, é seguro comprar. Margem de
        segurança separa investimento de especulação.

        Os números não mentem. Análise fundamental rigorosa de balanços e
        fluxos de caixa deve preceder toda decisão de compra.
        """,
    }

    for filename, content in texts.items():
        (temp_books_dir / filename).write_text(content, encoding="utf-8")

    return temp_books_dir


def test_rag_load_books(sample_corpus, temp_cache_dir):
    """Testa carregamento de livros."""
    rag = RagIndex(books_dir=sample_corpus, cache_dir=temp_cache_dir)
    assert len(rag._chunks) > 0
    assert rag._tfidf_vectors is not None
    assert rag._vocab is not None


def test_rag_search_basic(sample_corpus, temp_cache_dir):
    """Testa busca básica."""
    rag = RagIndex(books_dir=sample_corpus, cache_dir=temp_cache_dir)
    results = rag.search("valor intrínseco e preço de mercado", top_k=2)

    assert len(results) > 0
    assert len(results) <= 2
    assert all(hasattr(r, "chunk") for r in results)
    assert all(hasattr(r, "source") for r in results)
    assert all(hasattr(r, "score") for r in results)
    assert all(r.score >= 0 for r in results)


def test_rag_search_empty_index(temp_books_dir, temp_cache_dir):
    """Testa busca em índice vazio."""
    rag = RagIndex(books_dir=temp_books_dir, cache_dir=temp_cache_dir)
    results = rag.search("qualquer coisa", top_k=3)
    assert results == []


def test_rag_search_nonexistent_dir(temp_cache_dir):
    """Testa com diretório de livros inexistente."""
    nonexistent = Path("/tmp/nonexistent_rag_books_dir")
    rag = RagIndex(books_dir=nonexistent, cache_dir=temp_cache_dir)
    results = rag.search("teste", top_k=3)
    assert results == []


def test_rag_chunk_text(sample_corpus, temp_cache_dir):
    """Testa chunking de texto."""
    rag = RagIndex(books_dir=sample_corpus, cache_dir=temp_cache_dir)

    # Texto pequeno
    text_small = "Este é um parágrafo pequeno."
    chunks = rag._chunk_text(text_small)
    assert len(chunks) == 1

    # Texto grande
    text_large = "\n\n".join(["Parágrafo teste número {}.".format(i) for i in range(50)])
    chunks = rag._chunk_text(text_large)
    assert len(chunks) > 0
    for chunk in chunks:
        assert len(chunk) > 0


def test_rag_cache(sample_corpus, temp_cache_dir):
    """Testa salvamento e carregamento de cache."""
    rag1 = RagIndex(books_dir=sample_corpus, cache_dir=temp_cache_dir)
    results1 = rag1.search("margem de segurança", top_k=1)

    # Cria novo índice que carrega do cache
    rag2 = RagIndex(books_dir=sample_corpus, cache_dir=temp_cache_dir)
    results2 = rag2.search("margem de segurança", top_k=1)

    assert len(results1) == len(results2)
    if results1:
        assert results1[0].chunk == results2[0].chunk


def test_rag_top_k(sample_corpus, temp_cache_dir):
    """Testa parâmetro top_k."""
    rag = RagIndex(books_dir=sample_corpus, cache_dir=temp_cache_dir)

    results_1 = rag.search("investimento", top_k=1)
    results_3 = rag.search("investimento", top_k=3)

    assert len(results_1) <= 1
    assert len(results_3) <= 3
    assert len(results_1) <= len(results_3)


def test_rag_search_query_too_long(sample_corpus, temp_cache_dir):
    """Testa validação de query muito longa."""
    rag = RagIndex(books_dir=sample_corpus, cache_dir=temp_cache_dir)
    long_query = "a" * 1001
    with pytest.raises(ValueError, match="query muito longa"):
        rag.search(long_query)
