"""Alerta diário TrendFit — todos os ativos.

Compara a decisão de hoje com o estado salvo e emite aviso APENAS quando algo mudou.
Sem mudança → saída silenciosa (cron-friendly).

Primeiro run (state vazio) → imprime estado inicial de todos os ativos e salva baseline.

Uso:
    .venv/bin/python scripts/alert_daily.py

Cron diário às 8h (exemplo):
    0 8 * * * cd /path/to/Trendfit && .venv/bin/python scripts/alert_daily.py >> /tmp/trendfit_alert.log 2>&1
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.cockpit import asset_cockpit  # noqa: E402

ASSETS = ["BTC", "ETH", "Ouro", "SP500"]
STATE = ROOT / "db" / "alert_state.json"

ACTION_EMOJI = {
    "COMPRO": "🟢",
    "COMPRO_MAIS": "🟢",
    "MANTENHO": "⚪",
    "REDUZO": "🟡",
    "SAIO": "🔴",
    "FICO_FORA": "⚫",
}

WEIGHT_CHANGE_THRESHOLD = 0.15


def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def _changed(prev: dict, now: dict) -> bool:
    if not prev:
        return True
    if prev.get("action") != now.get("action"):
        return True
    w_prev = prev.get("weight_now", 0.0) or 0.0
    w_now = now.get("weight_now", 0.0) or 0.0
    return abs(w_now - w_prev) >= WEIGHT_CHANGE_THRESHOLD


def _fmt_action(d: dict) -> str:
    action = d.get("action", "—")
    emoji = ACTION_EMOJI.get(action, "❓")
    w = d.get("weight_now", 0.0) or 0.0
    return f"{emoji} {action}  ({w*100:.0f}% comprado)"


def main() -> int:
    state = _load_state()
    new_state: dict = {}
    alerts: list[str] = []
    first_run = not state

    for asset in ASSETS:
        try:
            cockpit = asset_cockpit(asset)
            dec = cockpit.get("decision", {})
            if not dec:
                continue
            price = cockpit.get("price")
            action = dec.get("action", "—")
            w_now = dec.get("weight_now", 0.0) or 0.0
            regime = cockpit.get("regime", "—")
            posture = cockpit.get("posture", {}).get("posture", "—")
            new_state[asset] = {
                "action": action,
                "weight_now": round(w_now, 3),
                "regime": regime,
                "posture": posture,
                "price": price,
            }
            prev = state.get(asset, {})
            if _changed(prev, new_state[asset]):
                prev_str = (f"antes: {_fmt_action(prev)}" if prev else "primeiro registro")
                alerts.append(
                    f"  {asset:<6}  {_fmt_action(new_state[asset])}"
                    f"  ←  {prev_str}"
                    f"  |  regime {regime}  postura {posture}"
                    f"  |  ${price:,.0f}" if price else
                    f"  {asset:<6}  {_fmt_action(new_state[asset])}"
                    f"  ←  {prev_str}"
                    f"  |  regime {regime}  postura {posture}"
                )
        except Exception:  # noqa: BLE001 — nunca bloqueia outros ativos
            alerts.append(f"  {asset:<6}  ⚠️ ERRO ao carregar  — {traceback.format_exc().splitlines()[-1]}")

    if alerts or first_run:
        from datetime import date
        print("=" * 76)
        print(f" ALERTA TrendFit {'— ESTADO INICIAL' if first_run else '— MUDANÇA DETECTADA'}  ({date.today()})")
        print("=" * 76)
        for line in alerts:
            print(line)
        if not alerts and first_run:
            for asset, d in new_state.items():
                price = d.get("price")
                price_str = f"  |  ${price:,.0f}" if price else ""
                print(f"  {asset:<6}  {_fmt_action(d)}  |  regime {d['regime']}  postura {d['posture']}{price_str}")
        print("=" * 76)

    if new_state:
        STATE.write_text(json.dumps(new_state, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
