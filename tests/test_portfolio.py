"""Testes da F3 — Carteira & patrimônio (alvos, desvios, tranches, modulação regime)."""

import pytest

from trendfit.portfolio import (
    ACT_BUY,
    ACT_HOLD,
    ACT_REDUCE,
    ACT_SELL,
    PortfolioTargets,
    load_targets,
    rebalance_plan,
    save_targets,
)


def test_targets_invalid_mode():
    with pytest.raises(ValueError):
        PortfolioTargets(mode="xpto")


def test_targets_roundtrip(tmp_path):
    spec = PortfolioTargets(mode="pct", targets={"BTC": 0.4, "ETH": 0.2}, tranche_fraction=0.5)
    path = tmp_path / "user_portfolio.json"
    save_targets(path, spec)
    loaded = load_targets(path)
    assert loaded is not None
    assert loaded.mode == "pct"
    assert loaded.targets["BTC"] == 0.4
    assert loaded.tranche_fraction == 0.5


def test_load_targets_missing(tmp_path):
    assert load_targets(tmp_path / "nao_existe.json") is None


def test_rebalance_pct_below_target_bull_buys():
    """Abaixo do alvo + regime BULL → COMPRAR (em tranche)."""
    spec = PortfolioTargets(mode="pct", targets={"BTC": 0.5}, tranche_fraction=0.5)
    plan = rebalance_plan({"BTC": 2000.0}, spec, {"BTC": "BULL"}, cash_usd=2000.0)
    btc = next(i for i in plan["items"] if i["asset"] == "BTC")
    assert plan["patrimonio_usd"] == 4000.0
    assert btc["target_usd"] == 2000.0  # 50% de 4000
    # já está no alvo (2000) → MANTER
    assert btc["action"] == ACT_HOLD


def test_rebalance_below_target_buys_tranche():
    spec = PortfolioTargets(mode="pct", targets={"BTC": 1.0}, tranche_fraction=0.5)
    plan = rebalance_plan({"BTC": 1000.0}, spec, {"BTC": "BULL"}, cash_usd=3000.0)
    btc = next(i for i in plan["items"] if i["asset"] == "BTC")
    assert btc["action"] == ACT_BUY
    # desvio = 1000 - 4000 = -3000; tranche = 3000 * 0.5 = 1500
    assert btc["tranche_usd"] == 1500.0


def test_regime_bear_never_buys():
    """Abaixo do alvo MAS regime BEAR → não compra (sistema está fora)."""
    spec = PortfolioTargets(mode="pct", targets={"BTC": 1.0})
    plan = rebalance_plan({"BTC": 1000.0}, spec, {"BTC": "BEAR"}, cash_usd=3000.0)
    btc = next(i for i in plan["items"] if i["asset"] == "BTC")
    assert btc["action"] == ACT_HOLD
    assert "BEAR" in btc["note"]


def test_above_target_sells_bull_reduces_bear():
    spec = PortfolioTargets(mode="absolute", targets={"BTC": 1000.0}, tranche_fraction=1.0)
    bull = rebalance_plan({"BTC": 5000.0}, spec, {"BTC": "BULL"})
    bear = rebalance_plan({"BTC": 5000.0}, spec, {"BTC": "BEAR"})
    assert next(i for i in bull["items"] if i["asset"] == "BTC")["action"] == ACT_SELL
    assert next(i for i in bear["items"] if i["asset"] == "BTC")["action"] == ACT_REDUCE


def test_absolute_mode_target():
    """mode absolute: alvo em US$ fixo, independente do patrimônio."""
    spec = PortfolioTargets(mode="absolute", targets={"ETH": 3000.0})
    plan = rebalance_plan({"ETH": 1000.0}, spec, {"ETH": "BULL"}, cash_usd=5000.0)
    eth = next(i for i in plan["items"] if i["asset"] == "ETH")
    assert eth["target_usd"] == 3000.0
    assert eth["action"] == ACT_BUY


def test_plan_never_emits_orders():
    """Linha vermelha: o plano só sugere (ações descritivas), nunca campos de execução."""
    spec = PortfolioTargets(mode="pct", targets={"BTC": 0.5, "ETH": 0.5})
    plan = rebalance_plan({"BTC": 1000.0, "ETH": 100.0}, spec,
                          {"BTC": "BULL", "ETH": "BEAR"}, cash_usd=500.0)
    for item in plan["items"]:
        assert item["action"] in {ACT_BUY, ACT_SELL, ACT_REDUCE, ACT_HOLD}
        assert "order_id" not in item and "execute" not in item
