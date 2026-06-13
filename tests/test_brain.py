"""Testes do Buffett Brain (princípios dos mestres + literatura/RAG)."""

import tempfile
from pathlib import Path

import pytest

from trendfit.agents.brain import (
    INVESTORS,
    SHARED_WISDOM,
    BrainResult,
    BuffettBrain,
    principles_context,
    relevant_investors,
)


@pytest.fixture
def temp_dirs():
    """books_dir e cache_dir temporários (vazios)."""
    with tempfile.TemporaryDirectory() as books, tempfile.TemporaryDirectory() as cache:
        yield Path(books), Path(cache)


def test_investors_knowledge_base_shape():
    """Cada investidor tem os campos essenciais preenchidos."""
    assert len(INVESTORS) >= 6
    for key, d in INVESTORS.items():
        assert d["name"]
        assert d["core"]
        assert len(d["principles"]) >= 3
        assert len(d["warnings"]) >= 1
        assert len(d["tags"]) >= 3
        assert d["on_context"]
    assert len(SHARED_WISDOM) >= 4


def test_relevant_investors_matches_macro():
    """Pergunta macro/liquidez deve puxar Dalio."""
    keys = relevant_investors("como a liquidez e o M2 afetam o ciclo de dívida?")
    assert "dalio" in keys
    assert len(keys) <= 3


def test_relevant_investors_matches_tail_risk():
    """Pergunta sobre bolha/alavancagem deve puxar Burry."""
    keys = relevant_investors("tem risco de bolha e alavancagem escondida?")
    assert "burry" in keys


def test_relevant_investors_by_name():
    """Citar o nome do investidor puxa ele com prioridade."""
    keys = relevant_investors("o que o Graham diria sobre isso?")
    assert "graham" in keys


def test_relevant_investors_fallback():
    """Sem casamento de tags, cai nos pilares (não retorna vazio)."""
    keys = relevant_investors("xyzqwk blarg")
    assert len(keys) == 3
    assert "buffett" in keys


def test_principles_context_is_text():
    """principles_context retorna texto com o consenso e ao menos um mestre."""
    ctx = principles_context("margem de segurança e valuation")
    assert "Consenso dos mestres" in ctx
    assert "Graham" in ctx or "Buffett" in ctx


def test_brain_recall_without_literature(temp_dirs):
    """Brain com books vazio: princípios presentes, literatura vazia, sem crash."""
    books, cache = temp_dirs
    brain = BuffettBrain(books_dir=books, cache_dir=cache)
    res = brain.recall("vale segurar BTC com o regime em baixa?")
    assert isinstance(res, BrainResult)
    assert res.principles
    assert isinstance(res.investors, list) and res.investors
    assert res.literature == []  # sem livros indexados


def test_brain_result_to_dict_serializable(temp_dirs):
    """BrainResult.to_dict() é JSON-serializável (contrato HTTP-ready)."""
    import json

    books, cache = temp_dirs
    brain = BuffettBrain(books_dir=books, cache_dir=cache)
    d = brain.recall("ciclo de mercado").to_dict()
    assert set(d.keys()) == {"query", "principles", "investors", "literature"}
    json.dumps(d)  # não pode levantar


def test_brain_as_prompt_block(temp_dirs):
    """as_prompt_block monta texto pronto pro system prompt."""
    books, cache = temp_dirs
    brain = BuffettBrain(books_dir=books, cache_dir=cache)
    block = brain.recall("risco e ciclo").as_prompt_block()
    assert "SABEDORIA DOS MESTRES" in block
    assert "Consenso dos mestres" in block
