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
    """Registra teses e lê as abertas (com postura e snapshot de preço)."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    tid = store.record("BTC", "Regime BEAR + cone negativo: risco alto de segurar.",
                       alert_level=8, evidence="regime FICO_FORA; cone 86% tocar 60k",
                       stance="defensivo", price_at=64000.0, horizon_days=14)
    assert isinstance(tid, int)
    abertas = store.open_theses()
    assert len(abertas) == 1
    assert abertas[0].asset == "BTC"
    assert abertas[0].alert_level == 8
    assert abertas[0].stance == "defensivo"
    assert abertas[0].price_at == 64000.0
    assert abertas[0].status == "aberta"


def test_thesis_store_alert_level_clamped(tmp_path):
    """Nível de alerta é limitado a 1..10."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    store.record("ETH", "tese", alert_level=99)
    store.record("ETH", "tese", alert_level=-3)
    levels = sorted(t.alert_level for t in store.all())
    assert levels == [1, 10]


def test_thesis_store_invalid_stance(tmp_path):
    """Postura inválida levanta erro (contrato)."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    with pytest.raises(ValueError):
        store.record("BTC", "x", alert_level=5, stance="talvez")


def test_thesis_resolve_defensive_hit(tmp_path):
    """Postura defensiva + preço caiu = ACERTO."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    tid = store.record("BTC", "sair", alert_level=8, stance="defensivo", price_at=64000.0)
    status = store.resolve(tid, current_price=55000.0)  # -14%
    assert status == "acerto"
    t = store.all()[0]
    assert t.status == "acerto"
    assert t.return_pct < 0


def test_thesis_resolve_defensive_miss(tmp_path):
    """Postura defensiva + preço subiu forte = ERRO."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    tid = store.record("BTC", "sair", alert_level=8, stance="defensivo", price_at=64000.0)
    assert store.resolve(tid, current_price=75000.0) == "erro"  # +17%


def test_thesis_resolve_accumulate(tmp_path):
    """Postura acumular: ganha na alta, perde na queda."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    a = store.record("BTC", "comprar", alert_level=3, stance="acumular", price_at=60000.0)
    b = store.record("ETH", "comprar", alert_level=3, stance="acumular", price_at=2000.0)
    assert store.resolve(a, current_price=70000.0) == "acerto"  # +16%
    assert store.resolve(b, current_price=1600.0) == "erro"     # -20%


def test_thesis_scoreboard(tmp_path):
    """Placar agrega taxa de acerto geral e por ativo."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    a = store.record("BTC", "sair", alert_level=8, stance="defensivo", price_at=64000.0)
    b = store.record("BTC", "sair", alert_level=7, stance="defensivo", price_at=60000.0)
    store.resolve(a, 55000.0)   # acerto
    store.resolve(b, 70000.0)   # erro
    store.record("ETH", "esperar", alert_level=5, stance="neutro", price_at=2000.0)  # aberta
    sb = store.scoreboard()
    assert sb["total"] == 3
    assert sb["open"] == 1
    assert sb["hit"] == 1
    assert sb["miss"] == 1
    assert sb["accuracy"] == 0.5
    assert sb["by_asset"]["BTC"]["accuracy"] == 0.5


def test_thesis_due(tmp_path):
    """due() retorna teses cujo horizonte venceu."""
    store = ThesisStore(db_path=tmp_path / "t.db")
    store.record("BTC", "curto", alert_level=8, stance="defensivo",
                 price_at=64000.0, horizon_days=0)  # vence imediatamente
    store.record("ETH", "longo", alert_level=4, stance="neutro",
                 price_at=2000.0, horizon_days=365)  # não vence
    due = store.due()
    assert len(due) == 1
    assert due[0].asset == "BTC"


def test_brain_recall_includes_open_theses(temp_dirs):
    """recall traz as teses abertas pra reavaliação, e elas entram no prompt block."""
    books, cache = temp_dirs
    brain = _brain(books, cache)
    brain.remember_thesis("BTC", "Segurar em BEAR é arriscado", alert_level=8,
                          stance="defensivo", price_at=64000.0)
    res = brain.recall("o que faço com meu BTC?")
    assert len(res.open_theses) == 1
    assert "TUAS TESES EM ABERTO" in res.as_prompt_block()
