"""Testes do Buffett Brain (princípios dos mestres + literatura/RAG)."""

import tempfile
from pathlib import Path

import pytest

from trendfit.agents.brain import (
    INVESTORS,
    SHARED_WISDOM,
    BrainResult,
    BuffettBrain,
    ThesisStore,
    principles_context,
    relevant_investors,
)


@pytest.fixture
def temp_dirs():
    """books_dir, cache_dir e thesis_db temporários (vazios)."""
    with tempfile.TemporaryDirectory() as books, tempfile.TemporaryDirectory() as cache:
        yield Path(books), Path(cache)


def _brain(books, cache):
    """BuffettBrain com tudo isolado em tmp (sem tocar db/ do repo)."""
    return BuffettBrain(books_dir=books, cache_dir=cache,
                        thesis_db=Path(cache) / "brain.db")


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
    brain = _brain(books, cache)
    res = brain.recall("vale segurar BTC com o regime em baixa?")
    assert isinstance(res, BrainResult)
    assert res.principles
    assert isinstance(res.investors, list) and res.investors
    assert res.literature == []  # sem livros indexados


def test_brain_result_to_dict_serializable(temp_dirs):
    """BrainResult.to_dict() é JSON-serializável (contrato HTTP-ready)."""
    import json

    books, cache = temp_dirs
    brain = _brain(books, cache)
    d = brain.recall("ciclo de mercado").to_dict()
    assert set(d.keys()) == {"query", "principles", "investors", "literature", "open_theses"}
    json.dumps(d)  # não pode levantar


def test_brain_as_prompt_block(temp_dirs):
    """as_prompt_block monta texto pronto pro system prompt."""
    books, cache = temp_dirs
    brain = _brain(books, cache)
    block = brain.recall("risco e ciclo").as_prompt_block()
    assert "SABEDORIA DOS MESTRES" in block
    assert "Consenso dos mestres" in block


# --- Memória de teses (julgamento adaptável) ---


def test_thesis_store_record_and_open(tmp_path):
    """Registra teses e lê as abertas."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    tid = store.record("BTC", "Regime BEAR + cone negativo: risco alto de segurar.",
                       alert_level=8, evidence="regime FICO_FORA; cone 86% tocar 60k")
    assert isinstance(tid, int)
    abertas = store.open_theses()
    assert len(abertas) == 1
    assert abertas[0].asset == "BTC"
    assert abertas[0].alert_level == 8
    assert abertas[0].status == "aberta"


def test_thesis_store_alert_level_clamped(tmp_path):
    """Nível de alerta é limitado a 1..10."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    store.record("ETH", "tese", alert_level=99)
    store.record("ETH", "tese", alert_level=-3)
    levels = sorted(t.alert_level for t in store.all())
    assert levels == [1, 10]


def test_thesis_store_review(tmp_path):
    """Reavaliar uma tese muda o status (confirma/refuta) e some das abertas."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    tid = store.record("BTC", "vai testar 55k", alert_level=7)
    store.review(tid, "confirmada", note="tocou 55k em julho")
    assert store.open_theses() == []
    todas = store.all()
    assert todas[0].status == "confirmada"
    assert "55k" in todas[0].review_note


def test_thesis_store_review_invalid_status(tmp_path):
    """Status inválido levanta erro (contrato)."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    tid = store.record("BTC", "x", alert_level=5)
    with pytest.raises(ValueError):
        store.review(tid, "talvez")


def test_thesis_store_filter_by_asset(tmp_path):
    """open_theses filtra por ativo."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    store.record("BTC", "tese btc", alert_level=6)
    store.record("ETH", "tese eth", alert_level=4)
    assert len(store.open_theses(asset="BTC")) == 1
    assert store.open_theses(asset="BTC")[0].asset == "BTC"


def test_brain_recall_includes_open_theses(temp_dirs):
    """recall traz as teses abertas pra reavaliação, e elas entram no prompt block."""
    books, cache = temp_dirs
    brain = _brain(books, cache)
    brain.remember_thesis("BTC", "Segurar em BEAR é arriscado", alert_level=8)
    res = brain.recall("o que faço com meu BTC?")
    assert len(res.open_theses) == 1
    assert "TUAS TESES EM ABERTO" in res.as_prompt_block()
