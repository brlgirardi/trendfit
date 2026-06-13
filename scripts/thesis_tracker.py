"""Acompanhamento das teses do Buffett Jr — registra, avalia e pontua.

Pedido do Bruno: monitorar as opiniões do agente ao longo do tempo pra ver se ele
ACERTA ou ERRA (aprendizado). Fluxo do WFA honesto:
  1. registra a leitura de hoje (postura + preço-snapshot + horizonte)
  2. semanas depois, `evaluate` coleta o preço atual e julga as teses vencidas
  3. `score` mostra a taxa de acerto

Uso (da raiz do projeto):
  python scripts/thesis_tracker.py list
  python scripts/thesis_tracker.py score
  python scripts/thesis_tracker.py evaluate            # resolve as vencidas
  python scripts/thesis_tracker.py record BTC defensivo 8 "Regime BEAR, sair" --horizon 14

O preço de cada ativo vem do mesmo data layer do cockpit (load_asset_df).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trendfit.agents.brain import ThesisStore  # noqa: E402

DB_DEFAULT = "db/buffett_brain.db"


def _price(asset: str) -> float | None:
    """Preço de fechamento mais recente do ativo (via cockpit). None se falhar."""
    try:
        from trendfit.cockpit import load_asset_df
        df = load_asset_df(asset)
        return float(df["Close"].iloc[-1])
    except Exception as exc:  # ativo desconhecido / sem dados
        print(f"  [aviso] sem preço para {asset}: {exc}")
        return None


def cmd_list(store: ThesisStore, _args) -> None:
    rows = store.all()
    if not rows:
        print("Nenhuma tese registrada ainda.")
        return
    for t in rows:
        ret = f"{t.return_pct * 100:+.1f}%" if t.return_pct is not None else "—"
        print(f"#{t.id} [{t.created_at[:10]}] {t.asset} {t.stance} alerta{t.alert_level} "
              f"| status={t.status} ret={ret} | {t.thesis[:70]}")


def cmd_score(store: ThesisStore, _args) -> None:
    sb = store.scoreboard()
    acc = f"{sb['accuracy'] * 100:.0f}%" if sb["accuracy"] is not None else "s/ dados"
    print(f"PLACAR — total {sb['total']} | abertas {sb['open']} | "
          f"acertos {sb['hit']} | erros {sb['miss']} | neutras {sb['neutral']}")
    print(f"Taxa de acerto: {acc}")
    for asset, d in sb["by_asset"].items():
        a = f"{d['accuracy'] * 100:.0f}%" if d.get("accuracy") is not None else "s/ dados"
        print(f"  {asset}: acertos {d['acerto']} erros {d['erro']} → {a}")


def cmd_evaluate(store: ThesisStore, _args) -> None:
    due = store.due()
    if not due:
        print("Nenhuma tese vencida pra avaliar agora.")
        return
    for t in due:
        price = _price(t.asset)
        if price is None:
            continue
        status = store.resolve(t.id, price, note="auto-avaliação por horizonte")
        print(f"#{t.id} {t.asset} {t.stance}: ${t.price_at:,.0f} → ${price:,.0f} "
              f"=> {status.upper()}")
    print()
    cmd_score(store, _args)


def cmd_record(store: ThesisStore, args) -> None:
    price = args.price if args.price is not None else _price(args.asset)
    tid = store.record(args.asset, args.thesis, args.alert, evidence=args.evidence,
                       stance=args.stance, price_at=price, horizon_days=args.horizon)
    print(f"Tese #{tid} registrada: {args.asset} {args.stance} alerta{args.alert} "
          f"@ ${price:,.0f} (horizonte {args.horizon}d)" if price
          else f"Tese #{tid} registrada (sem preço-snapshot).")


def main() -> None:
    p = argparse.ArgumentParser(description="Acompanhamento das teses do Buffett Jr")
    p.add_argument("--db", default=DB_DEFAULT, help="caminho do db de teses")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="lista todas as teses")
    sub.add_parser("score", help="placar de acerto")
    sub.add_parser("evaluate", help="resolve as teses vencidas com o preço atual")

    r = sub.add_parser("record", help="registra uma tese manualmente")
    r.add_argument("asset")
    r.add_argument("stance", choices=["defensivo", "neutro", "acumular"])
    r.add_argument("alert", type=int)
    r.add_argument("thesis")
    r.add_argument("--evidence", default="")
    r.add_argument("--price", type=float, default=None, help="snapshot (default: coleta)")
    r.add_argument("--horizon", type=int, default=14)

    args = p.parse_args()
    store = ThesisStore(db_path=args.db)
    {"list": cmd_list, "score": cmd_score, "evaluate": cmd_evaluate,
     "record": cmd_record}[args.cmd](store, args)


if __name__ == "__main__":
    main()
