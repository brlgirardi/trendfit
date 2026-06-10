"""TrendFit — Cockpit interativo (Fase 1: multi-ativo).

Casca Streamlit sobre o data layer puro (trendfit/cockpit.py). Troca de ativo, gráfico
com sinais do sistema (entrar/sair/HOJE), indicador por ativo, postura do Buffett Jr,
walkforward OOS (params reais) + ambiente macro e termômetro Polymarket no topo.

Rodar:  ./.venv/bin/streamlit run app/cockpit_app.py
Linha vermelha: classifica/postura/contexto — NUNCA prevê preço nem dá ordem.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
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
    market_cone,
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


# ---------------- decisão do dia (tradução mecânica do peso fracionário) ----------------
DECISION_STYLE = {
    "COMPRO": ("🟢", "#16a34a", "COMPRO"),
    "COMPRO_MAIS": ("🟢", "#16a34a", "COMPRO MAIS"),
    "MANTENHO": ("🔵", "#2563eb", "MANTENHO"),
    "REDUZO": ("🟠", "#d97706", "REDUZO"),
    "SAIO": ("🔴", "#ef4444", "SAIO 100%"),
    "FICO_FORA": ("⚪", "#64748b", "FICO FORA"),
}
COSTS_PATH = ROOT / "db" / "user_costs.json"  # dado pessoal LOCAL (db/ é gitignored)


def _load_costs() -> dict:
    try:
        return json.loads(COSTS_PATH.read_text())
    except Exception:
        return {}


def _save_costs(d: dict) -> None:
    COSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    COSTS_PATH.write_text(json.dumps(d, indent=2))


def _br(iso: str | None) -> str:
    return f"{date.fromisoformat(iso):%d/%m/%Y}" if iso else "—"


def _decision_text(dec: dict, plan: dict | None, px: float) -> tuple[str, str]:
    """(frase principal, detalhe) — leitura mecânica do sinal, sem previsão."""
    f, fp = dec["frac_today"], dec.get("frac_prev")
    pe = dec.get("post_exit")
    seguro = ""
    if pe:
        seguro = (f"das {pe['n']} saídas no período, {pe['n_loss']} cristalizaram prejuízo e, "
                  f"mesmo assim, após sair o preço caiu em média mais "
                  f"{abs(pe['avg_drop_after']) * 100:.0f}% (mediana {abs(pe['median_drop_after']) * 100:.0f}%)")
    stop = ""
    if plan and plan.get("sell_level"):
        # sem escape de $: estes textos vão num bloco HTML (_decision_card), onde o
        # markdown não dispara LaTeX — \$ apareceria literal
        stop = (f"Stop atual: ${plan['sell_level']:,.0f} ({(plan['sell_level'] / px - 1) * 100:+.1f}% daqui), "
                f"por {plan['sell_kind']}.")
    if dec["action"] == "MANTENHO":
        return (f"Mantenho {f:.0%} comprado",
                f"Ensemble estável desde {_br(dec['last_change'])}. {stop} O stop sobe junto com o topo.")
    if dec["action"] == "COMPRO":
        return (f"Compro {f:.0%}", f"O sistema ENTROU hoje (estava em caixa). {stop}")
    if dec["action"] == "COMPRO_MAIS":
        return (f"Compro mais → {f:.0%}",
                f"A fração subiu de {fp:.0%}: mais membros do ensemble confirmaram a tendência. {stop}")
    if dec["action"] == "REDUZO":
        return (f"Reduzo → {f:.0%}",
                f"A fração caiu de {fp:.0%}: parte do ensemble perdeu a tendência — vendo a diferença hoje. {stop}")
    if dec["action"] == "SAIO":
        det = "O sistema ZEROU a posição hoje."
        if seguro:
            det += f" Histórico: {seguro}. O stop é o seguro, não a falha."
        return ("Saio 100% HOJE — mesmo com prejuízo", det)
    # FICO_FORA
    buy = f"Recompra acima de ${plan['buy_level']:,.0f} ({(plan['buy_level'] / px - 1) * 100:+.1f}% daqui)." \
        if plan and plan.get("buy_level") else ""
    det = f"Sem posição desde {_br(dec['last_change'])}. {buy}"
    if seguro:
        det += f" Por que não compro 'no fundo': {seguro}."
    return ("Fico fora (caixa)", det)


def _decision_card(dec: dict | None, plan: dict | None, px: float) -> None:
    if not dec:
        return
    emoji, color, label = DECISION_STYLE[dec["action"]]
    head, detail = _decision_text(dec, plan, px)
    st.markdown(
        f"<div style='border-left:6px solid {color};background:{color}14;"
        f"padding:0.8rem 1rem;border-radius:0 10px 10px 0;margin:0.3rem 0 0.6rem'>"
        f"<span style='font-size:1.3rem;font-weight:800;color:{color}'>🎯 Decisão de hoje: "
        f"{emoji} {label}</span> "
        f"<span style='font-size:1.02rem;font-weight:600'>— {head}</span><br>"
        f"<span style='color:#94a3b8;font-size:0.92rem'>{detail}</span></div>",
        unsafe_allow_html=True)


def _my_position(asset: str, dec: dict | None, plan: dict | None, trades: list[dict], px: float) -> None:
    """Tradução da decisão para o custo PESSOAL. O custo NUNCA altera a ação — só traduz."""
    if not dec:
        return
    with st.expander("💼 Minha posição (opcional) — traduz a decisão para o SEU custo"):
        costs = _load_costs()
        cur = float(costs.get(asset, 0.0))
        c1, c2 = st.columns([1, 2.2])
        mycost = c1.number_input("Meu preço médio (US$)", min_value=0.0, value=cur,
                                 step=100.0, key=f"cost_{asset}",
                                 help="Fica salvo localmente (db/user_costs.json), fora do git.")
        if abs(mycost - cur) > 1e-9:
            costs[asset] = mycost
            _save_costs(costs)
        if mycost <= 0:
            c2.caption("Informe seu preço médio para ver o P&L pessoal e o que cada ação cristaliza.")
            return
        pnl = px / mycost - 1
        # \$ escapa o $ no markdown do Streamlit (dois $ na mesma linha viram LaTeX)
        lines = [f"**Seu P&L hoje:** {pnl:+.1%} (custo \\${mycost:,.0f} → preço \\${px:,.0f})."]
        if dec["action"] in ("MANTENHO", "COMPRO", "COMPRO_MAIS", "REDUZO") and plan and plan.get("sell_level"):
            lines.append(f"No stop do sistema (\\${plan['sell_level']:,.0f}) você cristalizaria "
                         f"{plan['sell_level'] / mycost - 1:+.1%}.")
        if dec["action"] == "SAIO":
            lines.append(f"Sair agora cristaliza **{pnl:+.1%}** do seu custo.")
        if dec["action"] == "FICO_FORA":
            closed = [t for t in trades if not t.get("open")]
            if closed:
                last = closed[-1]
                lines.append(f"⚠️ O sistema está FORA (saiu a \\${last['exit_px']:,.0f} em "
                             f"{_br(last['exit_date'])}). Se você ainda está posicionado, está fora do "
                             f"plano — sair agora cristaliza **{pnl:+.1%}**.")
        lines.append("_Seu custo NÃO altera a decisão do sistema — ela vem só do sinal. Isto apenas traduz._")
        c2.markdown("  \n".join(lines))


@st.cache_data(ttl=600, show_spinner=False)
def _cone(name: str):
    # cone do MERCADO DE APOSTAS (Kalshi + Polymarket) — contexto, NÃO sinal. ttl curto
    # (dado vivo de mercado). Some sozinho se a fonte cair.
    return market_cone(name)


CONE_HUE = {"up": (22, 163, 74), "down": (239, 68, 68)}      # alta verde · baixa vermelha
CONE_SYMBOL = {"kalshi": "diamond", "polymarket": "circle"}  # fonte por símbolo
CONE_ARROW = {"up": "↑", "down": "↓"}

# Corte de APRESENTAÇÃO (não toca o data layer, que segue completo/honesto): tira da
# leitura os alvos de prob desprezível e os absurdamente distantes do preço — eram eles
# que esticavam o eixo Y e achatavam o histórico. O que foi ocultado é avisado na legenda.
CONE_MIN_PROB = 0.05   # < 5% = ruído visual
CONE_MAX_MULT = 2.6    # alvo acima de 2,6× o preço de hoje sai da leitura
CONE_MIN_MULT = 0.30   # alvo abaixo de 0,30× o preço de hoje sai da leitura
CONE_TOP_N = 3         # só os 3 alvos mais prováveis de cada direção (o resto é poluição)


def _trim_cone(cone: dict | None, spot: float):
    """Corte de apresentação (não toca o coletor, que segue completo): filtra prob/distância
    e mantém só os TOP-N alvos mais prováveis de CADA direção (cima/baixo), agregando as
    fontes. Retorna (cone_filtrado|None, n_ocultados)."""
    if not cone:
        return cone, 0
    passed, hidden = [], 0
    for p in cone["points"]:
        if (p["prob"] >= CONE_MIN_PROB
                and spot * CONE_MIN_MULT <= p["target"] <= spot * CONE_MAX_MULT):
            passed.append(p)
        else:
            hidden += 1
    kept = []
    for d in ("up", "down"):  # só os N mais prováveis de cada lado — tira a poluição
        side = sorted((p for p in passed if p["dir"] == d), key=lambda p: p["prob"], reverse=True)
        kept.extend(side[:CONE_TOP_N])
        hidden += max(0, len(side) - CONE_TOP_N)
    if not kept:
        return None, hidden
    out = dict(cone)
    out["points"] = kept
    out["sources"] = [s for s in cone.get("sources", []) if any(p["source"] == s for p in kept)]
    return out, hidden


def _add_cone(fig, cone, today, spot):
    """Plota o cone do mercado de apostas À FRENTE de hoje. ESPELHO da multidão, não o
    sistema: raios faint hoje→alvo (opacidade∝prob) + marcadores por fonte/direção
    (tamanho/opacidade∝prob, rótulo de %, OI no hover). Some sozinho se não houver cone."""
    if not cone or not cone.get("end"):
        return
    try:
        end_d = date.fromisoformat(cone["end"])
    except (ValueError, TypeError):
        return
    # duas colunas no futuro: Kalshi na resolução, Polymarket ~18d antes (lado a lado,
    # sem sobrepor — duas multidões independentes). Raios dão o formato de leque.
    col_x = {"kalshi": cone["end"], "polymarket": (end_d - timedelta(days=18)).isoformat()}
    for p in cone["points"]:
        r, g, b = CONE_HUE[p["dir"]]
        a = 0.05 + 0.55 * p["prob"]
        fig.add_trace(go.Scatter(x=[today, col_x[p["source"]]], y=[spot, p["target"]],
                                 mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color=f"rgba({r},{g},{b},{a:.3f})",
                                           width=0.8 + 2.2 * p["prob"])), row=1, col=1)
    groups: dict[tuple, list] = {}
    for p in cone["points"]:
        groups.setdefault((p["source"], p["dir"]), []).append(p)
    for (src, d), pts in groups.items():
        r, g, b = CONE_HUE[d]
        hov = []
        for p in pts:
            txt = (f"{'tocar acima de' if d == 'up' else 'tocar abaixo de'} "
                   f"${p['target']:,.0f}<br>{p['prob']*100:.0f}% · {src}")
            if p.get("oi"):
                txt += f" · OI {p['oi']:,.0f}"
            hov.append(txt + "<br><i>mercado de apostas, não o sistema</i>")
        fig.add_trace(go.Scatter(
            x=[col_x[src]] * len(pts), y=[p["target"] for p in pts], mode="markers+text",
            name=f"{src.capitalize()} {CONE_ARROW[d]}",
            marker=dict(size=[7 + 26 * p["prob"] for p in pts], symbol=CONE_SYMBOL[src],
                        color=[f"rgba({r},{g},{b},{0.25 + 0.7*p['prob']:.3f})" for p in pts],
                        line=dict(width=0.5, color="rgba(255,255,255,0.45)")),
            text=[f"{p['prob']*100:.0f}%" for p in pts],
            textposition="middle left" if src == "kalshi" else "middle right",
            textfont=dict(size=9, color=f"rgba({r},{g},{b},0.95)"),
            hovertext=hov, hoverinfo="text"), row=1, col=1)
    fig.add_vline(x=today, line=dict(color="#94a3b8", width=1, dash="dot"), row=1, col=1)
    fig.add_annotation(x=cone["end"], y=1.0, yref="paper", xref="x", xanchor="right",
                       text="🎲 apostas →", showarrow=False,
                       font=dict(size=10, color="#a855f7"))
    # foca os últimos ~13 meses + a região futura p/ o cone ter protagonismo (interativo:
    # o usuário pode dar zoom out p/ ver todo o histórico).
    try:
        left = (date.fromisoformat(today) - timedelta(days=400)).isoformat()
        fig.update_xaxes(range=[left, (end_d + timedelta(days=15)).isoformat()])
    except (ValueError, TypeError):
        pass


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


def _chart(c: dict, cone: dict | None = None, candles: bool = False):
    s = c["series"]
    ov = s.get("val_overlay")  # subplot de valuation: MVRV (BTC) ou CAPE (SP500)
    has_ov = ov is not None and any(v is not None for v in ov["values"])
    rows = 3 if has_ov else 2
    heights = [0.6, 0.2, 0.2] if has_ov else [0.72, 0.28]
    titles = ["", "RSI(14) · contexto"] + ([f"{ov['name']} · contexto"] if has_ov else [])
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=heights, subplot_titles=titles)
    use_candles = candles and s.get("high_low") and s.get("open") is not None
    if use_candles:
        fig.add_trace(go.Candlestick(x=s["date"], open=s["open"], high=s["high"],
                                     low=s["low"], close=s["price"], name=c["name"],
                                     increasing_line_color="#16a34a",
                                     decreasing_line_color="#ef4444"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=s["date"], y=s["price"], name=c["name"],
                                 line=dict(color="#f59e0b", width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=s["date"], y=s["ma200"], name="MA200 (regime)",
                             line=dict(color="#3b82f6", width=1.2, dash="dash")), row=1, col=1)
    # VERDE suave = sistema COMPRADO (entrada→saída; trade aberto vai até hoje). Sem cor =
    # FORA/caixa. Codificação ÚNICA e limpa (sem faixa vermelha nem setas); os pontos e o
    # resultado de cada trade ficam na tabela "Trades do sistema" abaixo do gráfico.
    for _t in c.get("trades", []):
        fig.add_vrect(x0=_t["entry_date"], x1=(_t.get("exit_date") or s["date"][-1]),
                      fillcolor="#16a34a", opacity=0.13, line_width=0, layer="below", row=1, col=1)
    sig = c.get("signal")
    if sig:
        fig.add_trace(go.Scatter(x=[s["date"][-1]], y=[c["price"]], mode="markers", name="HOJE",
                                 marker=dict(symbol="circle", size=14,
                                             color="#ef4444" if sig["fora"] else "#16a34a",
                                             line=dict(width=2, color="white"))), row=1, col=1)
    # níveis de AÇÃO do sistema: onde COMPRA (fora) ou onde SAI/stop (comprado)
    plan = c.get("plan")
    if plan and plan["state"] == "fora" and plan.get("buy_level"):
        fig.add_hline(y=plan["buy_level"], line=dict(color="#16a34a", width=1.2, dash="dash"),
                      annotation_text=f"🟢 compra ↑ ${plan['buy_level']:,.0f}",
                      annotation_position="bottom right",
                      annotation_font=dict(color="#16a34a", size=10), row=1, col=1)
    elif plan and plan["state"] == "comprado" and plan.get("sell_level"):
        fig.add_hline(y=plan["sell_level"], line=dict(color="#ef4444", width=1.2, dash="dash"),
                      annotation_text=f"🔴 stop/sai ↓ ${plan['sell_level']:,.0f}",
                      annotation_position="top right",
                      annotation_font=dict(color="#ef4444", size=10), row=1, col=1)
    fig.add_trace(go.Scatter(x=s["date"], y=s["rsi"], line=dict(color="#a855f7", width=1.1),
                             showlegend=False), row=2, col=1)
    for lvl, col in ((70, "#ef4444"), (30, "#16a34a")):
        fig.add_hline(y=lvl, line=dict(color=col, width=1, dash="dot"), row=2, col=1)
    if has_ov:
        fig.add_trace(go.Scatter(x=s["date"], y=ov["values"], line=dict(color="#06b6d4", width=1.1),
                                 showlegend=False), row=3, col=1)
        fig.add_hline(y=ov["ref"], line=dict(color="#94a3b8", width=1, dash="dot"),
                      annotation_text=f"ref {ov['ref']:.0f}" if ov["ref"] >= 5 else "",
                      annotation_position="top left", row=3, col=1)
    if cone:  # cone do MERCADO DE APOSTAS à frente de hoje (contexto, não o sistema)
        _add_cone(fig, cone, s["date"][-1], c["price"])
    fig.update_layout(template="plotly_dark", height=560, margin=dict(l=10, r=44, t=30, b=10),
                      hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)",
                      xaxis_rangeslider_visible=False,  # candlestick não traz o slider
                      legend=dict(orientation="h", y=1.04, x=1, xanchor="right"))
    fig.update_xaxes(type="date")  # garante região futura proporcional (não categórica)
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
        if floor:  # \$ evita o modo LaTeX do markdown (dois $ na mesma linha)
            bits.append(f"piso 50/50 **~\\${floor:,.0f}**")
        for t, p in d["up"][:2]:
            bits.append(f"tocar \\${t:,.0f} **{p*100:.0f}%**")
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

# ---------------- decisão do dia + minha posição ----------------
_decision_card(c.get("decision"), c.get("plan"), c["price"])
_my_position(asset, c.get("decision"), c.get("plan"), c.get("trades", []), c["price"])

# ---------------- plano de ação do sistema (onde comprar / vender) ----------------
plan = c.get("plan")
if plan:
    px = c["price"]
    if plan["state"] == "fora":
        bl, gap = plan["buy_level"], (plan["buy_level"] / px - 1) * 100
        msg = (f"📍 **Plano do sistema — está FORA (caixa).**  🟢 **Compra** quando o preço "
               f"**recuperar ~\\${bl:,.0f}** ({gap:+.1f}% daqui) — cruzar a MA200 + banda de regime. "
               f"Abaixo disso segue em caixa: não pega faca caindo.")
        closed = [t for t in c.get("trades", []) if not t.get("open")]
        if closed:  # o que ficar em caixa POUPOU: última saída vs queda desde então
            last = closed[-1]
            prices, dates = c["series"]["price"], c["series"]["date"]
            if last["exit_date"] in dates:
                low_after = min(prices[dates.index(last["exit_date"]):])
                drop = (low_after / last["exit_px"] - 1) * 100
                if drop < -8:
                    msg += (f"  \n💡 **Por que NÃO compra no fundo:** a última saída foi a "
                            f"\\${last['exit_px']:,.0f}; desde então o preço caiu até \\${low_after:,.0f} "
                            f"(**{drop:.0f}%**). Ficar em caixa te poupou desse tombo — comprar 'no fundo' "
                            f"na queda teria pego essa faca. O sistema só entra quando a virada CONFIRMA.")
        st.info(msg)
    elif plan["state"] == "comprado" and plan.get("sell_level"):
        sl, gap = plan["sell_level"], (plan["sell_level"] / px - 1) * 100
        st.success(f"📍 **Plano do sistema — está COMPRADO.**  🔴 **Vende/sai** se **perder "
                   f"~\\${sl:,.0f}** ({gap:+.1f}% daqui) — stop por {plan['sell_kind']}. "
                   f"Acima disso segura a tendência e deixa o lucro correr (o stop sobe junto).")

ctrl = st.columns([1.2, 1.4, 2.4])
candles = False
if c["series"].get("high_low"):  # só ativos com OHLC real (BTC/ETH); sintéticos ficam linha
    candles = ctrl[0].radio("Visualização", ["📈 Linha", "🕯️ Candles"], horizontal=True,
                            label_visibility="collapsed", index=0).endswith("Candles")
show_cone = ctrl[1].checkbox("🎲 Sobrepor cone de apostas", value=False,
                             help="Mostra o que o mercado de apostas precifica. Desligado por padrão "
                                  "para o gráfico do SISTEMA ficar limpo.")
cone_full, cone_hidden = _trim_cone(_cone(asset), c["price"])
cone = cone_full if show_cone else None
st.plotly_chart(_chart(c, cone, candles=candles), width="stretch")
if cone_full:  # placar é TEXTO (limpo) e aparece sempre que há mercado; o cone visual é opcional
    ups = sorted((p for p in cone_full["points"] if p["dir"] == "up"), key=lambda p: -p["prob"])
    downs = sorted((p for p in cone_full["points"] if p["dir"] == "down"), key=lambda p: -p["prob"])
    placar = []
    if ups:
        placar.append(f"🟢 maior **alta**: tocar ${ups[0]['target']:,.0f} (**{ups[0]['prob']*100:.0f}%**)")
    if downs:
        placar.append(f"🔴 maior **baixa**: tocar ${downs[0]['target']:,.0f} (**{downs[0]['prob']*100:.0f}%**)")
    if placar:
        extra = "" if show_cone else " · ligue o cone acima p/ ver no gráfico"
        st.markdown("📊 **Mercado preditivo** — " + " · ".join(placar)
                    + f"  <span style='color:#94a3b8'>· one-touch; espelho da multidão, não o "
                    f"sistema{extra}</span>", unsafe_allow_html=True)
    if show_cone:
        src = " + ".join(s.capitalize() for s in cone_full["sources"])
        hidden_note = (f" {cone_hidden} alvo(s) ocultados para leitura (dado completo no coletor)."
                       if cone_hidden else "")
        st.caption(f"🎲 **Cone ({src})** — o que a multidão precifica para *tocar* cada preço até "
                   f"{cone_full['end']}, **não o sistema**. Some em 1º/jan quando a aposta vence."
                   f"{hidden_note}")

# ---------------- trades do sistema (onde COMPROU / VENDEU no histórico) ----------------
trades = c.get("trades", [])
if trades:
    last_d = c["series"]["date"][-1]
    closed = [t for t in trades if not t.get("open")]
    wins = sum(1 for t in closed if t["ret"] > 0)
    wr = f"{wins/len(closed)*100:.0f}%" if closed else "—"
    rows_t = []
    for t in trades:
        end = t["exit_date"] or last_d
        days = (date.fromisoformat(end) - date.fromisoformat(t["entry_date"])).days
        rows_t.append({"Entrada": t["entry_date"], "Compra": f"${t['entry_px']:,.0f}",
                       "Saída": t["exit_date"] or "🟢 ABERTO", "Venda": f"${t['exit_px']:,.0f}",
                       "Retorno": f"{t['ret']*100:+.1f}%", "Dias": days})
    with st.expander(f"📋 Trades do sistema no período visível ({len(trades)}) — onde COMPROU e VENDEU"):
        st.dataframe(rows_t, width="stretch", hide_index=True)
        st.caption(f"{len(closed)} fechado(s) · {wins} vencedor(es) (win rate {wr}). O total honesto "
                   f"(retorno **e risco** vs B&H) está no walkforward OOS abaixo — aqui é só o QUANDO; "
                   f"entre os trades o sistema fica em CAIXA (faixa verde no gráfico = comprado).")

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
            st.caption(f"🎲 Espelho do mercado: ~{nb[1]*100:.0f}% de chance de tocar \\${nb[0]:,.0f} "
                       f"(perto do gatilho da MA200 \\${sig['ma_value']:,.0f}). Contexto, não ordem.")
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
