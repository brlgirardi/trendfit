"""F3 — Painel de Carteira & patrimônio (Streamlit multipage).

Define alvos de alocação (% ou US$), lê a carteira real da Binance + o regime de
cada ativo, e mostra um plano de rebalanceamento gradual (tranches).

LINHA VERMELHA: SUGERE, nunca executa. O regime modula (não compra em BEAR); a
decisão e a ordem são sempre do Bruno.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trendfit.cockpit import ASSETS, asset_cockpit, get_binance_portfolio  # noqa: E402
from trendfit.portfolio import (  # noqa: E402
    MODE_ABS,
    MODE_PCT,
    PortfolioTargets,
    load_targets,
    rebalance_plan,
    save_targets,
)

st.set_page_config(page_title="Carteira", page_icon="💼", layout="wide")
st.title("💼 Carteira & patrimônio")
st.caption(
    "Define teus alvos de alocação; o sistema lê a carteira real + o regime de cada "
    "ativo e sugere o rebalanceamento em tranches. **Sugere, nunca executa — o regime "
    "decide o timing (não compra em BEAR), a decisão e a ordem são sempre tuas.**"
)

TARGETS_PATH = ROOT / "db" / "user_portfolio.json"
_ACTION_COLOR = {"COMPRAR": "🟢", "VENDER": "🟠", "ALIVIAR": "🔴", "MANTER": "⚪"}


@st.cache_data(ttl=3600, show_spinner=False)
def _regime(name: str) -> str:
    try:
        return asset_cockpit(name, with_walkforward=False).get("regime", "—")
    except Exception:
        return "—"


@st.cache_data(ttl=600, show_spinner=False)
def _holdings() -> dict:
    try:
        return get_binance_portfolio() or {}
    except Exception:
        return {}


pf = _holdings()
holdings_usd = {k: v["usd_value"] for k, v in pf.items() if isinstance(v, dict)}
cash_usd = float(pf.get("other_usd", 0.0)) if pf else 0.0

saved = load_targets(TARGETS_PATH)
default_mode = saved.mode if saved else MODE_PCT

st.subheader("1) Teus alvos de alocação")
mode = st.radio(
    "Modo do alvo", [MODE_PCT, MODE_ABS], horizontal=True,
    index=0 if default_mode == MODE_PCT else 1,
    format_func=lambda m: "Percentual (% do patrimônio)" if m == MODE_PCT else "Valor absoluto (US$)",
)
tranche = st.slider("Tamanho da tranche (fração do desvio por rebalanceamento)",
                    0.1, 1.0, value=saved.tranche_fraction if saved else 0.34, step=0.01)

cols = st.columns(len(ASSETS))
targets: dict[str, float] = {}
for col, name in zip(cols, ASSETS):
    prev = (saved.targets.get(name, 0.0) if saved else 0.0)
    with col:
        if mode == MODE_PCT:
            val = st.number_input(f"{name} (%)", min_value=0.0, max_value=100.0,
                                  value=float(prev * 100 if saved and saved.mode == MODE_PCT else 0.0),
                                  step=5.0, key=f"t_{name}")
            targets[name] = val / 100.0
        else:
            val = st.number_input(f"{name} (US$)", min_value=0.0,
                                  value=float(prev if saved and saved.mode == MODE_ABS else 0.0),
                                  step=100.0, key=f"t_{name}")
            targets[name] = val

if mode == MODE_PCT:
    soma = sum(targets.values()) * 100
    st.caption(f"Soma dos alvos: **{soma:.0f}%** "
               + ("✅" if abs(soma - 100) < 0.1 else "⚠️ (idealmente 100%; o resto fica em caixa)"))

if st.button("💾 Salvar alvos", type="primary"):
    save_targets(TARGETS_PATH, PortfolioTargets(mode=mode, targets=targets, tranche_fraction=tranche))
    st.success("Alvos salvos.")
    st.cache_data.clear()

st.divider()
st.subheader("2) Plano de rebalanceamento")

if not holdings_usd:
    st.info("Sem carteira da Binance (configura `BINANCE_API_KEY`/`SECRET` no `.env`). "
            "Mostro o plano assim que houver posições.")
else:
    spec = PortfolioTargets(mode=mode, targets=targets, tranche_fraction=tranche)
    regimes = {name: _regime(name) for name in ASSETS}
    plan = rebalance_plan(holdings_usd, spec, regimes, cash_usd=cash_usd)

    c1, c2 = st.columns(2)
    c1.metric("Patrimônio total", f"${plan['patrimonio_usd']:,.2f}")
    c2.metric("Caixa (stablecoins)", f"${plan['cash_usd']:,.2f}")

    st.dataframe(
        [{"Ativo": i["asset"], "Atual": f"${i['current_usd']:,.0f} ({i['current_pct']:.0f}%)",
          "Alvo": f"${i['target_usd']:,.0f} ({i['target_pct']:.0f}%)",
          "Regime": i["regime"], "Ação": f"{_ACTION_COLOR.get(i['action'], '')} {i['action']}",
          "Tranche": f"${i['tranche_usd']:,.0f}" if i["tranche_usd"] else "—",
          "Nota": i["note"]}
         for i in plan["items"]],
        width="stretch", hide_index=True,
    )
    st.caption("Tranche = quanto mover por vez (rebalanceamento gradual). "
               "O regime modula: ativo em BEAR nunca recebe sugestão de compra.")
