"""TrendFit — Cockpit interativo (Fase 1: multi-ativo).

Casca Streamlit sobre o data layer puro (trendfit/cockpit.py). Troca de ativo, gráfico
com sinais do sistema (entrar/sair/HOJE), indicador por ativo, postura do Buffett Jr,
walkforward OOS (params reais) + ambiente macro e termômetro Polymarket no topo.

Rodar:  ./.venv/bin/streamlit run app/cockpit_app.py
Linha vermelha: classifica/postura/contexto — NUNCA prevê preço nem dá ordem.
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.cockpit import (  # noqa: E402
    asset_cockpit,
    environment_now,
    lab_walkforward,
    list_assets,
    nearest_market_prob,
    polymarket_now,
)

st.set_page_config(page_title="TrendFit · Cockpit", page_icon="🧭", layout="wide")

POSTURE_COLOR = {"ACUMULAR": "#16a34a", "NEUTRO": "#3b82f6", "CAUTELOSO": "#f59e0b",
                 "DEFENSIVO": "#ef4444", "—": "#94a3b8"}
ENV_COLOR = {"FAVORÁVEL": "#16a34a", "MISTO": "#f59e0b", "ADVERSO": "#ef4444"}


@st.cache_data(ttl=3600, show_spinner=False)
def _env():
    return environment_now()


@st.cache_data(ttl=600, show_spinner=False)
def _pm():
    return polymarket_now()


@st.cache_data(ttl=3600, show_spinner=False)
def _cockpit(name: str, fng, funding, env_level: str):
    # args primitivos = cacheáveis; o data layer só usa fng/funding/level do ctx/env
    return asset_cockpit(name, {"fng": fng, "funding": funding}, {"level": env_level})


@st.cache_data(ttl=3600, show_spinner=False)
def _lab(name: str, asym: float, band: float, atr_k: float, rg: float, rk: float):
    return lab_walkforward(name, asym=asym, band=band, atr_k=atr_k, ratchet_gain=rg, ratchet_k=rk)


def _bear_spans(dates, price, ma200):
    spans, start = [], None
    for i, (p, m) in enumerate(zip(price, ma200)):
        bear = m is not None and p < m
        if bear and start is None:
            start = dates[i]
        elif not bear and start is not None:
            spans.append((start, dates[i]))
            start = None
    if start is not None:
        spans.append((start, dates[-1]))
    return spans


def _chart(c: dict):
    s = c["series"]
    has_mvrv = s.get("mvrv") is not None and any(v is not None for v in s["mvrv"])
    rows = 3 if has_mvrv else 2
    heights = [0.6, 0.2, 0.2] if has_mvrv else [0.72, 0.28]
    titles = ["Preço + sinais do sistema", "RSI(14) · contexto"] + (["MVRV · contexto"] if has_mvrv else [])
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=heights, subplot_titles=titles)
    fig.add_trace(go.Scatter(x=s["date"], y=s["price"], name=c["name"],
                             line=dict(color="#f59e0b", width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=s["date"], y=s["ma200"], name="MA200 (regime)",
                             line=dict(color="#3b82f6", width=1.2, dash="dash")), row=1, col=1)
    for x0, x1 in _bear_spans(s["date"], s["price"], s["ma200"]):
        fig.add_vrect(x0=x0, x1=x1, fillcolor="#ef4444", opacity=0.07, line_width=0, layer="below", row=1, col=1)
    for t in c.get("trades", []):
        fig.add_trace(go.Scatter(x=[t["entry_date"]], y=[t["entry_px"]], mode="markers", showlegend=False,
                                 marker=dict(symbol="triangle-up", color="#16a34a", size=11,
                                             line=dict(width=1, color="white")),
                                 hovertext=f"ENTRADA ${t['entry_px']:,.0f}"), row=1, col=1)
        if t.get("exit_date"):
            col = "#16a34a" if t["ret"] >= 0 else "#ef4444"
            fig.add_trace(go.Scatter(x=[t["exit_date"]], y=[t["exit_px"]], mode="markers", showlegend=False,
                                     marker=dict(symbol="triangle-down", color=col, size=11,
                                                 line=dict(width=1, color="white")),
                                     hovertext=f"SAÍDA ${t['exit_px']:,.0f} ({t['ret']*100:+.0f}%)"), row=1, col=1)
    sig = c.get("signal")
    if sig:
        fig.add_trace(go.Scatter(x=[s["date"][-1]], y=[c["price"]], mode="markers", name="HOJE",
                                 marker=dict(symbol="circle", size=14,
                                             color="#ef4444" if sig["fora"] else "#16a34a",
                                             line=dict(width=2, color="white"))), row=1, col=1)
    fig.add_trace(go.Scatter(x=s["date"], y=s["rsi"], line=dict(color="#a855f7", width=1.1),
                             showlegend=False), row=2, col=1)
    for lvl, col in ((70, "#ef4444"), (30, "#16a34a")):
        fig.add_hline(y=lvl, line=dict(color=col, width=1, dash="dot"), row=2, col=1)
    if has_mvrv:
        fig.add_trace(go.Scatter(x=s["date"], y=s["mvrv"], line=dict(color="#06b6d4", width=1.1),
                                 showlegend=False), row=3, col=1)
        fig.add_hline(y=1.0, line=dict(color="#94a3b8", width=1, dash="dot"), row=3, col=1)
    fig.update_layout(template="plotly_dark", height=560, margin=dict(l=10, r=10, t=30, b=10),
                      hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=1.04, x=1, xanchor="right"))
    return fig


# ---------------- topo: ambiente + Polymarket ----------------
st.title("🧭 TrendFit · Cockpit")
st.caption("Classifica regime · lê postura · mostra contexto — **nunca prevê preço nem dá ordem.** "
           "Timing (regime) é validado OOS e MANDA; postura e contexto INFORMAM.")

env = _env()["env"]
ctx = _env()["ctx"]
c1, c2 = st.columns([1, 1])
with c1:
    color = ENV_COLOR.get(env["level"], "#94a3b8")
    st.markdown(f"#### 🌐 Ambiente de risco: <span style='color:{color}'>{env['level']}</span>",
                unsafe_allow_html=True)
    st.caption(" · ".join(f"{n['label']}: {n['detail']}" for n in env["notes"]))
    st.caption(env["rationale"])
with c2:
    pm = _pm()
    if pm:
        d, price_now = pm["dist"], None
        st.markdown("#### 🎲 Mercado de apostas (Polymarket) <span style='color:#a855f7'>· a multidão, "
                    "não o sistema</span>", unsafe_allow_html=True)
        floor = pm["floor_5050"]
        bits = []
        if floor:
            bits.append(f"piso 50/50 **~${floor:,.0f}**")
        for t, p in d["up"][:2]:
            bits.append(f"tocar ${t:,.0f} **{p*100:.0f}%**")
        st.caption(" · ".join(bits))
        st.caption(f"{d['title']} · vol ${d['volume']/1e6:.0f}M · contexto, não aciona nada.")
    else:
        st.caption("🎲 Polymarket indisponível agora.")

st.divider()

# ---------------- seletor de ativo ----------------
asset = st.radio("Ativo", list_assets(), horizontal=True, label_visibility="collapsed")

with st.spinner(f"Rodando walkforward de {asset} (params OOS reais)…"):
    c = _cockpit(asset, ctx.get("fng"), ctx.get("funding"), env["level"])

sig = c.get("signal")
acao = "—"
if sig:
    acao = "FORA / caixa" if sig["fora"] else f"COMPRADO {sig['weight']*100:.0f}%"
rc = "#16a34a" if c["regime"] == "BULL" else "#ef4444"
pcolor = POSTURE_COLOR.get(c["posture"]["posture"], "#94a3b8")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Preço", f"${c['price']:,.0f}", help=f"em {c['asof']}")
k2.markdown(f"**Regime (timing)**<br><span style='color:{rc};font-size:1.5rem;font-weight:700'>"
            f"{c['regime']}</span><br><span style='color:#94a3b8'>{c['dist_ma']*100:+.0f}% da MA200</span>",
            unsafe_allow_html=True)
k3.markdown(f"**Sinal do sistema**<br><span style='color:{rc};font-size:1.4rem;font-weight:700'>{acao}</span>",
            unsafe_allow_html=True)
k4.markdown(f"**Postura (Buffett Jr)**<br><span style='color:{pcolor};font-size:1.4rem;font-weight:700'>"
            f"{c['posture']['posture']}</span><br><span style='color:#94a3b8'>informa, regime decide</span>",
            unsafe_allow_html=True)
k5.metric("Valuation", f"{c['val_pct']:.0f}%", help=c["val_label"] or "percentil de preço (proxy)")

st.plotly_chart(_chart(c), width="stretch")

# ---------------- postura + cenários ----------------
left, right = st.columns([1, 1])
with left:
    st.markdown(f"##### 🎩 Postura: <span style='color:{pcolor}'>{c['posture']['posture']}</span>",
                unsafe_allow_html=True)
    st.write(c["posture"]["rationale"])
    for sc in c["posture"].get("scenarios", []):
        st.markdown(f"▸ {sc}")
    if pm and not sig.get("regime_bull", True):
        nb = nearest_market_prob(pm["dist"], sig["ma_value"])
        if nb:
            st.caption(f"🎲 Espelho do mercado: ~{nb[1]*100:.0f}% de chance de tocar ${nb[0]:,.0f} "
                       f"(perto do gatilho da MA200 ${sig['ma_value']:,.0f}). Contexto, não ordem.")
with right:
    st.markdown("##### ✔︎ Critérios da decisão")
    for cr in c["view"].get("criteria", []):
        ic = {"ok": "🟢", "bad": "🔴", "warn": "🟡"}.get(cr["state"], "·")
        st.markdown(f"{ic} **{cr['label']}**: {cr['detail']}  \n<span style='color:#94a3b8;font-size:0.85em'>"
                    f"{cr['peso']}</span>", unsafe_allow_html=True)

# ---------------- walkforward OOS ----------------
wf = c.get("wf")
if wf:
    st.divider()
    st.markdown(f"##### 📊 Walkforward OOS (honesto, params escolhidos só no treino) · {wf['period']}")
    w1, w2, w3, w4, w5 = st.columns(5)
    w1.metric("Sistema", f"{wf['ret']*100:+.0f}%", f"{(wf['ret']-wf['bh_ret'])*100:+.0f}pp vs B&H")
    w2.metric("Buy & Hold", f"{wf['bh_ret']*100:+.0f}%")
    w3.metric("Drawdown sist.", f"{wf['dd']*100:.0f}%", f"vs B&H {wf['bh_dd']*100:.0f}%", delta_color="off")
    w4.metric("Sharpe", f"{wf['sharpe']:.2f}")
    w5.metric("Calmar", f"{wf['calmar']:.2f}")
    st.caption(f"Config escolhida pelo grid: `{wf['params']}` · lookbacks {wf['lookbacks']}. "
               f"O backtest faz parte do walkforward — estes são os parâmetros REAIS fora da amostra.")
    eq = wf["equity"]
    efig = go.Figure(go.Scatter(x=eq["date"], y=eq["val"], line=dict(color="#16a34a", width=1.4)))
    efig.update_layout(template="plotly_dark", height=220, margin=dict(l=10, r=10, t=10, b=10),
                       paper_bgcolor="rgba(0,0,0,0)", title="Curva de capital OOS (base 1.0)")
    st.plotly_chart(efig, width="stretch")

# ---------------- Fase 2: Laboratório de parâmetros (exploratório) ----------------
if wf:
    st.divider()
    with st.expander("🧪 Laboratório de parâmetros — exploração (NÃO é o número honesto)"):
        st.error("⚠️ **MODO EXPLORATÓRIO — leia antes de mexer.** Ajustar os parâmetros abaixo e "
                 "escolher o que dá o melhor retorno AQUI é **overfit** — o erro central que este "
                 "projeto existe para combater. O número **honesto** é o do grid acima, que escolhe os "
                 "parâmetros só no **treino** (sem olhar o futuro). Use isto para **entender o efeito** "
                 "de cada parâmetro — nunca para 'achar' a melhor config olhando o passado.")
        cc = st.columns(5)
        asym = cc[0].select_slider("asym (canal)", options=[1.0, 1.5, 2.0, 3.0], value=1.0)
        band = cc[1].select_slider("banda regime", options=[0.0, 0.03, 0.05, 0.08], value=0.05)
        atr_k = cc[2].select_slider("trailing k", options=[0.0, 2.0, 3.0, 4.0, 5.0, 6.0], value=3.0)
        rg = cc[3].select_slider("ratchet: lucro p/ alargar", options=[0.0, 0.3, 0.5], value=0.0)
        rk = cc[4].select_slider("ratchet: k largo", options=[0.0, 5.0, 6.0], value=0.0)
        if st.button("🔬 Rodar walkforward com estes parâmetros", type="primary"):
            with st.spinner("rodando walkforward exploratório…"):
                lab = _lab(asset, asym, band, atr_k, rg, rk)
            honest = wf["ret"]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Lab (seus params)", f"{lab['ret']*100:+.0f}%")
            m2.metric("Honesto (grid)", f"{honest*100:+.0f}%")
            m3.metric("Drawdown", f"{lab['dd']*100:.0f}%")
            m4.metric("Sharpe", f"{lab['sharpe']:.2f}")
            if lab["ret"] > honest + 0.02:
                st.error(f"🚩 Seu ajuste ({lab['ret']*100:+.0f}%) parece **bater** o honesto "
                         f"({honest*100:+.0f}%). Quase certo que é **overfit** — você escolheu olhando o "
                         "OOS. **Não adote.** O grid honesto continua sendo a referência.")
            elif lab["ret"] < honest - 0.02:
                st.info(f"Seu ajuste ({lab['ret']*100:+.0f}%) fica **abaixo** do honesto "
                        f"({honest*100:+.0f}%) — o grid escolhendo no treino faz melhor.")
            else:
                st.info(f"Seu ajuste ({lab['ret']*100:+.0f}%) ≈ honesto ({honest*100:+.0f}%). "
                        "Dentro do ruído — o número honesto segue sendo a referência.")
            st.caption(f"Config testada: `{lab['params']}` · lookbacks escolhidos no treino · {lab['period']}")

st.divider()
st.caption("Não é recomendação de investimento. Regime = timing validado OOS. Postura/macro/Polymarket = "
           "contexto que INFORMA, nunca aciona ordem. Ouro/SP500 usam OHLC sintético (só close) e dias úteis.")
