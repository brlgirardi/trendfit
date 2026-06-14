"""Testes da camada de postura (allocation) — trava a regra-mãe display-only.

A postura INFORMA, o regime DECIDE. asset_posture nunca pode emitir sinal/peso/ordem;
é só leitura descritiva. (Fase 5 refutou valuation como gatilho — aqui é contexto.)
"""

from trendfit.allocation import asset_posture

_BASE = {"regime": "BULL", "price": 100.0, "dist_ma": 0.1, "has_real_valuation": True}
_ENV = {"level": "FAVORÁVEL"}


def test_asset_posture_considers_valuation():
    """A postura MUDA com o valuation (barato vs caro em extremo)."""
    cheap = asset_posture({**_BASE, "val_pct": 20.0, "val_label": "CAPE 14"}, {}, _ENV)
    expensive = asset_posture({**_BASE, "val_pct": 95.0, "val_label": "CAPE 42"}, {}, _ENV)
    assert cheap["posture"] == "ACUMULAR"
    assert expensive["posture"] == "CAUTELOSO"
    assert cheap["posture"] != expensive["posture"]


def test_asset_posture_is_display_only():
    """Regra-mãe: asset_posture só retorna campos DESCRITIVOS — nunca sinal/peso/ordem."""
    out = asset_posture({**_BASE, "val_pct": 95.0, "val_label": "CAPE 42"}, {}, _ENV)
    assert set(out.keys()) == {"posture", "rationale", "scenarios", "color"}
    forbidden = {"signal", "weight", "action", "frac", "order", "sinal", "peso", "trade"}
    assert not (set(out.keys()) & forbidden)


def test_asset_posture_valuation_never_sells_in_bull():
    """Valuation em extremo NÃO vira venda: vira CAUTELOSO (margem de segurança), e o
    racional deixa explícito que o timing segue o regime (PHASE5)."""
    out = asset_posture({**_BASE, "val_pct": 99.0, "val_label": "CAPE 44"}, {}, _ENV)
    assert out["posture"] in ("CAUTELOSO", "NEUTRO")  # nunca "VENDER"
    assert "valuation" in out["rationale"].lower()


def test_asset_posture_proxy_valuation_not_extreme():
    """Sem valuation real (proxy de preço), val_extreme não dispara — só CAPE/MVRV reais
    levam ao CAUTELOSO por valuation extremo."""
    out = asset_posture(
        {"regime": "BULL", "price": 100.0, "dist_ma": 0.1,
         "val_pct": 95.0, "has_real_valuation": False}, {}, _ENV,
    )
    # caro pelo proxy, mas sem euforia/funding e sem valuation real → não vira CAUTELOSO
    assert out["posture"] == "NEUTRO"
