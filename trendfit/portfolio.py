"""F3 — Carteira & patrimônio. Buffett como GESTOR operacional (a parte Dalio).

O Bruno define alvos de alocação por ativo (em % do patrimônio OU em valores
absolutos US$). O sistema lê a carteira atual + o regime de cada ativo e devolve
um PLANO DE REBALANCEAMENTO gradual (tranches), modulado pelo regime.

LINHA VERMELHA (inegociável):
- SUGERE, nunca executa. Nenhuma ordem é enviada; a decisão e o clique são do Bruno.
- O regime MODULA o alvo: em BEAR o sistema está FORA, então o plano NÃO sugere
  comprar (no máximo aliviar) — coerente com o engine, que não segura em baixa.
- Tranches: rebalanceia em fatias (não tudo de uma vez), pra não tentar acertar o
  topo/fundo. É gestão de risco, não market-timing fino.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MODE_PCT = "pct"
MODE_ABS = "absolute"
_VALID_MODES = {MODE_PCT, MODE_ABS}

# ações que o plano pode sugerir (todas display-only)
ACT_BUY = "COMPRAR"
ACT_SELL = "VENDER"
ACT_REDUCE = "ALIVIAR"
ACT_HOLD = "MANTER"


@dataclass
class PortfolioTargets:
    """Alvos definidos pelo Bruno. mode='pct' (frações 0..1) ou 'absolute' (US$)."""

    mode: str
    targets: dict[str, float] = field(default_factory=dict)
    tranche_fraction: float = 0.34  # fatia do desvio por rebalanceamento (gradual)

    def __post_init__(self) -> None:
        if self.mode not in _VALID_MODES:
            raise ValueError(f"mode inválido: {self.mode} (use {sorted(_VALID_MODES)})")
        self.tranche_fraction = max(0.05, min(1.0, float(self.tranche_fraction)))

    def to_dict(self) -> dict:
        return {"mode": self.mode, "targets": self.targets,
                "tranche_fraction": self.tranche_fraction}


def load_targets(path: str | Path) -> PortfolioTargets | None:
    """Lê os alvos do usuário (db/user_portfolio.json). None se não existir."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return PortfolioTargets(
            mode=data.get("mode", MODE_PCT),
            targets={k: float(v) for k, v in data.get("targets", {}).items()},
            tranche_fraction=float(data.get("tranche_fraction", 0.34)),
        )
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def save_targets(path: str | Path, targets: PortfolioTargets) -> None:
    """Persiste os alvos (db/user_portfolio.json, gitignored)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(targets.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _target_usd(asset: str, spec: PortfolioTargets, total_usd: float) -> float:
    """Alvo NOMINAL em US$ (antes da modulação por regime)."""
    raw = spec.targets.get(asset, 0.0)
    if spec.mode == MODE_PCT:
        return max(0.0, raw) * total_usd
    return max(0.0, raw)  # absoluto


def rebalance_plan(
    holdings_usd: dict[str, float],
    spec: PortfolioTargets,
    regimes: dict[str, str],
    cash_usd: float = 0.0,
) -> dict:
    """Monta o plano de rebalanceamento.

    holdings_usd: {ativo: valor atual US$} (da Binance/sistema).
    spec: alvos do Bruno. regimes: {ativo: 'BULL'|'BEAR'|'—'} (do sistema).
    cash_usd: caixa disponível (stablecoins).

    Retorna {patrimonio_usd, cash_usd, items:[...]}. Cada item é uma SUGESTÃO."""
    invested = sum(max(0.0, v) for v in holdings_usd.values())
    patrimonio = invested + max(0.0, cash_usd)

    # universo = ativos com posição OU com alvo definido
    universo = sorted(set(holdings_usd) | set(spec.targets))
    items: list[dict] = []
    for asset in universo:
        current = max(0.0, holdings_usd.get(asset, 0.0))
        regime = regimes.get(asset, "—")
        target = _target_usd(asset, spec, patrimonio)  # alvo NOMINAL (o que o Bruno quer)

        # desvio contra o alvo nominal; a AÇÃO é que o regime modula (não o alvo exibido).
        deviation = current - target  # >0 = acima do alvo; <0 = abaixo
        tranche = round(abs(deviation) * spec.tranche_fraction, 2)

        if abs(deviation) < max(1.0, 0.02 * patrimonio):  # dentro de 2% → ok
            action, note = ACT_HOLD, "Dentro do alvo (sem ação relevante)."
        elif deviation < 0:  # abaixo do alvo → comprar, MAS não em BEAR
            if regime == "BEAR":
                action, tranche = ACT_HOLD, 0.0
                note = ("Abaixo do alvo, MAS regime BEAR: o sistema está fora — "
                        "não comprar agora (esperar virar BULL).")
            else:
                action = ACT_BUY
                note = f"Abaixo do alvo: comprar ~${tranche:,.0f} por tranche (gradual)."
        else:  # acima do alvo → vender/aliviar
            action = ACT_REDUCE if regime == "BEAR" else ACT_SELL
            extra = " (regime BEAR reforça aliviar)" if regime == "BEAR" else ""
            note = f"Acima do alvo: reduzir ~${tranche:,.0f} por tranche{extra}."

        items.append({
            "asset": asset,
            "current_usd": round(current, 2),
            "current_pct": round(current / patrimonio * 100, 1) if patrimonio else 0.0,
            "target_usd": round(target, 2),
            "target_pct": round(target / patrimonio * 100, 1) if patrimonio else 0.0,
            "deviation_usd": round(deviation, 2),
            "regime": regime,
            "action": action,
            "tranche_usd": tranche,
            "note": note,
        })

    return {"patrimonio_usd": round(patrimonio, 2), "cash_usd": round(max(0.0, cash_usd), 2),
            "items": items}
