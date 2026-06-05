"""Dashboard TrendFit — painel HTML rico (status + gráfico com indicadores + radar multi-ativo).

BTC: preço + sinais (com o MOTIVO de cada trade), volume, RSI e MVRV em subplots.
Radar: gráficos dos outros ativos monitorados (Ouro, SP500) com regime.
Painel de alocação (regime+valuation) e detector de anomalia (flash crash).

IMPORTANTE — o que dispara compra/venda é SÓ o trade system (preço): regime MA200 +
rompimento Donchian (ensemble) + trailing ATR. Macro/MVRV/RSI são CONTEXTO informativo,
NÃO acionam o sistema (foram testados e refutados como sinal — ver docs/PHASE2-3.md).

Servido em http://localhost:5050/dashboard (scripts/serve.py). Regenerado pelo launchd.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.allocation import asset_posture, asset_view, environment_fragility, environment_read  # noqa: E402
from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.data.external import load_series  # noqa: E402
from trendfit.data.polymarket import fetch_btc_price_distribution, fifty_fifty_level, nearest_prob  # noqa: E402
from trendfit.engine.signal import current_signal, paired_trades  # noqa: E402
from trendfit.engine.strategy import StrategyConfig, target_weights  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402
from trendfit.report.report import add_trade_overlays  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"
OUT = ROOT / "reports" / "dashboard.html"
START = "2023-06-01"
REFRESH_MIN = 60


def _rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0); dn = -d.clip(upper=0.0)
    rs = (up.ewm(alpha=1/period, adjust=False).mean()
          / dn.ewm(alpha=1/period, adjust=False).mean())
    return 100 - 100/(1+rs)


def _bear_spans(pr, ma):
    bear = (pr < ma).fillna(False); spans = []; st = None
    idx, vals = bear.index, bear.to_numpy()
    for i, v in enumerate(vals):
        if v and st is None:
            st = idx[i]
        elif not v and st is not None:
            spans.append((st, idx[i])); st = None
    if st is not None:
        spans.append((st, idx[-1]))
    return spans


def _radar(name, close, go) -> str:
    close = close.dropna()
    if len(close) < 210:
        return f"<div style='color:#94a3b8'>{name}: histórico insuficiente</div>"
    pr = close.loc[START:]; ma = close.rolling(200).mean().loc[START:]
    regime = "BULL" if pr.iloc[-1] > ma.iloc[-1] else "BEAR"
    color = "#16a34a" if regime == "BULL" else "#ef4444"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pr.index, y=pr.values, name=name, line=dict(color="#f59e0b", width=1.4)))
    fig.add_trace(go.Scatter(x=ma.index, y=ma.values, name="MA200", line=dict(color="#3b82f6", width=1, dash="dash")))
    for x0, x1 in _bear_spans(pr, ma):
        fig.add_vrect(x0=x0.isoformat(), x1=x1.isoformat(), fillcolor="#ef4444", opacity=0.07, line_width=0, layer="below")
    fig.update_layout(template="plotly_white", height=240, margin=dict(l=45, r=10, t=34, b=20),
                      showlegend=False, title=dict(text=f"{name} · regime {regime} · ${pr.iloc[-1]:,.0f}",
                                                   font=dict(color=color, size=14)))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _scorecard(views, postures=None) -> str:
    """Scorecard transparente: por ativo, os critérios ✓/✗/⚠ + a POSTURA (Buffett Jr)
    + cenários condicionais. O regime (timing) MANDA; postura/cenários são leitura."""
    postures = postures or {}
    icon = {"ok": "<span style='color:#16a34a'>✓</span>", "bad": "<span style='color:#ef4444'>✗</span>",
            "warn": "<span style='color:#f59e0b'>⚠</span>"}
    cards = []
    for v in views:
        rows = "".join(
            f"<div class='crit'>{icon.get(c['state'], '·')} <b>{c['label']}</b>: {c['detail']}"
            f"<span class='muted'> — {c['peso']}</span></div>" for c in v.get("criteria", []))
        p = postures.get(v["name"])
        pblock = ""
        if p and p["posture"] != "—":
            scen = "".join(f"<div class='scen'>▸ {s}</div>" for s in p.get("scenarios", []))
            pblock = (f"<div class='posture' style='border-color:{p['color']}'>"
                      f"<span class='pbadge' style='background:{p['color']}'>{p['posture']}</span> "
                      f"<span class='muted'>postura — informa, regime decide</span>"
                      f"<div class='prat'>{p['rationale']}</div>{scen}</div>")
        cards.append(
            f"<div class='scard'><div class='sctop'>{v['name']} "
            f"<span class='muted'>· {v['n_ok']}/3 critérios a favor</span></div>{rows}"
            f"<div class='rat'>→ {v['rationale']}</div>{pblock}</div>")
    return "<div class='scards'>" + "".join(cards) + "</div>"


def _polymarket_panel(dist, price) -> str:
    """Faixa do MERCADO DE APOSTAS (Polymarket) — contexto puro, NÃO sinal. Mostra a
    prob. implícita de níveis-chave do BTC lado a lado com a postura. O sistema não usa
    estes números — é espelho da multidão. Some do painel se a API estiver indisponível."""
    if not dist:
        return ""
    up, down = dist.get("up", []), dist.get("down", [])
    chips = []
    floor = fifty_fifty_level(down)
    if floor:
        chips.append((f"~${floor:,.0f}", "piso 50/50 (cair até)", "#f59e0b"))
    for t, p in [tp for tp in up if tp[0] > price][:2]:                  # 2 alvos de alta
        chips.append((f"{p*100:.0f}%", f"tocar ${t:,.0f}", "#16a34a"))
    tail = nearest_prob(down, price * 0.5)                                # cauda de medo (~½ do preço)
    if tail:
        chips.append((f"{tail[1]*100:.0f}%", f"cair a ${tail[0]:,.0f}", "#ef4444"))
    if not chips:
        return ""
    chip_html = "".join(f"<span class='echip'><b style='color:{c}'>{v}</b> {lab}</span>"
                        for v, lab, c in chips)
    vol = dist.get("volume", 0)
    return (f"<div class='env' style='border-color:#a855f7'>"
            f"<div class='envtop'>🎲 Termômetro do mercado de apostas (Polymarket) "
            f"<span class='muted'>· é a multidão, NÃO o sistema · contexto, não aciona · "
            f"{dist.get('title', '')} · vol ${vol/1e6:.0f}M · ao vivo</span></div>"
            f"<div class='echips'>{chip_html}</div>"
            f"<div class='envrat'>Probabilidade IMPLÍCITA que o mercado de apostas precifica "
            f"para o BTC até {dist.get('end', '')}. O sistema NÃO usa estes números (não acionam, "
            f"não modulam) — ficam como espelho do que a multidão aposta, ao lado da postura.</div></div>")


def _environment_panel(env) -> str:
    """Painel do AMBIENTE macro (Buffett Jr): juros/VIX/dólar/sentimento → leitura do
    presente (FAVORÁVEL/MISTO/ADVERSO a risco). Não é previsão de direção."""
    icon = {"ok": "✓", "bad": "✗", "warn": "~"}
    col = {"ok": "#16a34a", "bad": "#ef4444", "warn": "#f59e0b"}
    chips = []
    for n in env["notes"]:
        c = col.get(n["state"], "#94a3b8")
        chips.append(f"<span class='echip' style='border-color:{c}'>"
                     f"<b style='color:{c}'>{icon.get(n['state'], '·')}</b> "
                     f"{n['label']}: {n['detail']}</span>")
    return (f"<div class='env' style='border-color:{env['color']}'>"
            f"<div class='envtop'>🎩 Leitura do sistema — Ambiente de risco: "
            f"<b style='color:{env['color']}'>{env['level']}</b> "
            f"<span class='muted'>(presente, não previsão · juros/VIX/dólar/sentimento)</span></div>"
            f"<div class='echips'>{''.join(chips)}</div>"
            f"<div class='envrat'>{env['rationale']}</div></div>")


def main() -> int:
    profile = json.loads((ROOT / "profiles" / "btc.json").read_text())
    e, w, g = profile["engine"], profile["walkforward"], profile["grid"]
    dcfg = profile["data"]; exchanges = [tuple(x) for x in dcfg["exchanges"]]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, cache_symbol=dcfg["cache_symbol"],
                               timeframe=dcfg["timeframe"], exchanges=exchanges)
    df = df[~df.index.duplicated(keep="last")].sort_index()

    # ETH close (mesmo motor; cripto segue a mesma linha do BTC — ver docs/PHASE4.md)
    eth_close = None
    try:
        with OHLCVCache(DB) as cache:
            ethdf = fetch_ohlcv_daily(cache, cache_symbol="ETH", timeframe="1d",
                                      exchanges=[("binance", "ETH/USDT"), ("kraken", "ETH/USD"), ("coinbase", "ETH/USD")])
        eth_close = ethdf[~ethdf.index.duplicated(keep="last")].sort_index()["Close"]
    except Exception:  # noqa: BLE001
        eth_close = None

    cands = []
    for lname, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                cands.append((f"{lname}|a{asym}|b{band}|k{atrk}", lbs,
                              StrategyConfig(ma_window=e["ma_window"], band=band,
                                             mode="long_asym", asym=asym, atr_k=atrk)))
    wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"], cost_bps=e["cost_bps"])
    last = wf.steps[-1]; nm = last.chosen
    cfg = StrategyConfig(ma_window=e["ma_window"], band=float(nm.split("|b")[1].split("|")[0]),
                         mode="long_asym", asym=float(nm.split("|a")[1].split("|")[0]), atr_k=float(nm.split("|k")[1]))
    w_live = pd.Series(target_weights(df, last.lookbacks, cfg), index=df.index)
    w_full = w_live.copy(); w_full.loc[wf.oos_weights.index] = wf.oos_weights.values

    price = df["Close"]
    sig = current_signal(df, last.lookbacks, kind=e["kind"], ma_window=e["ma_window"])
    fora = sig.recommended_weight <= 0
    ma20 = price.rolling(20).mean()
    trend_up = bool(price.iloc[-1] > ma20.iloc[-1] and ma20.iloc[-1] > ma20.iloc[-6])
    ret1 = float(price.iloc[-1] / price.iloc[-2] - 1)
    vol30 = float(price.pct_change().iloc[-30:].std())
    anomaly = abs(ret1) > max(0.10, 4 * vol30)
    rsi_last = float(_rsi_series(price).iloc[-1])
    gap = (sig.ma_value / sig.price - 1) * 100 if sig.price else float("nan")

    mv_full = load_series(DB, "mvrv")
    mvrv_pct = float((mv_full < mv_full.iloc[-1]).mean() * 100) if not mv_full.empty else None
    views = [
        asset_view("BTC", price, valuation_pct=mvrv_pct,
                   valuation_label=f"MVRV {mv_full.iloc[-1]:.2f}" if not mv_full.empty else ""),
    ]
    if eth_close is not None:
        views.append(asset_view("ETH", eth_close))
    views += [asset_view("Ouro", load_series(DB, "gold")), asset_view("SP500", load_series(DB, "spx"))]
    frag, frag_why = environment_fragility(views)
    frag_cor = {"ELEVADA": "#ef4444", "MODERADA": "#f59e0b", "BAIXA": "#16a34a"}.get(frag, "#94a3b8")

    # --- Buffett Jr: ambiente macro (global) + postura por ativo (leitura do presente) ---
    us10y, vix, dxy = load_series(DB, "us10y"), load_series(DB, "vix"), load_series(DB, "dxy")
    fng, fund = load_series(DB, "fng"), load_series(DB, "funding")
    lv = lambda s: float(s.iloc[-1]) if len(s) else None  # noqa: E731
    ctx = {
        "us10y": lv(us10y),
        "us10y_chg": float(us10y.iloc[-1] - us10y.iloc[-22]) if len(us10y) > 22 else None,
        "vix": lv(vix),
        "dxy_chg": float(dxy.iloc[-1] / dxy.iloc[-22] - 1) if len(dxy) > 22 else None,
        "fng": lv(fng), "funding": lv(fund),
    }
    env = environment_read(ctx)
    env_html = _environment_panel(env)
    postures = {}
    for v in views:
        cax = {"fng": ctx["fng"], "funding": ctx["funding"] if v["name"] in ("BTC", "ETH") else None}
        postures[v["name"]] = asset_posture(v, cax, env)
    scorecard_html = _scorecard(views, postures)

    # --- Polymarket: termômetro do mercado de apostas (contexto puro, não sinal) ---
    pm_dist = fetch_btc_price_distribution()
    pm_html = _polymarket_panel(pm_dist, float(sig.price))

    # ---------- gráfico BTC com subplots ----------
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    pr = price.loc[START:]; ma200 = price.rolling(e["ma_window"]).mean().loc[START:]
    vol = df["Volume"].loc[START:]; rsi_s = _rsi_series(price).loc[START:]
    mvrv_s = mv_full.reindex(price.index).ffill().loc[START:] if not mv_full.empty else None
    trades = paired_trades(w_full.loc[START:], pr, threshold=0.05)
    has_mvrv = mvrv_s is not None and mvrv_s.notna().any()
    n_rows = 4 if has_mvrv else 3
    heights = [0.50, 0.14, 0.18, 0.18] if has_mvrv else [0.58, 0.16, 0.26]
    titles = ("Preço + sinais (motivo no hover)", "Volume", "RSI(14) — informativo",
              "MVRV — informativo") if has_mvrv else ("Preço + sinais", "Volume", "RSI(14)")
    fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=heights, subplot_titles=titles)
    fig.add_trace(go.Scatter(x=pr.index, y=pr.values, name="BTC", line=dict(color="#f59e0b", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=ma200.index, y=ma200.values, name="MA200 (regime)",
                             line=dict(color="#3b82f6", width=1.2, dash="dash")), row=1, col=1)
    for x0, x1 in _bear_spans(pr, ma200):
        for rr in range(1, n_rows + 1):
            fig.add_vrect(x0=x0.isoformat(), x1=x1.isoformat(), fillcolor="#ef4444", opacity=0.06,
                          line_width=0, layer="below", row=rr, col=1)
    if not trades.empty:
        add_trade_overlays(fig, trades, go, row=1, col=1)
    fig.add_trace(go.Scatter(x=[sig.date], y=[sig.price], mode="markers", name="HOJE",
                  marker=dict(symbol="circle", color=("#ef4444" if fora else "#16a34a"), size=12,
                              line=dict(width=2, color="white"))), row=1, col=1)
    # volume (cor por dia de alta/baixa)
    up = (df["Close"] >= df["Open"]).loc[START:]
    fig.add_trace(go.Bar(x=vol.index, y=vol.values, name="Volume", marker_color=np.where(up, "#16a34a", "#ef4444"),
                         marker_line_width=0, opacity=0.5, showlegend=False), row=2, col=1)
    # RSI
    fig.add_trace(go.Scatter(x=rsi_s.index, y=rsi_s.values, name="RSI", line=dict(color="#a855f7", width=1.2),
                             showlegend=False), row=3, col=1)
    for lvl, c in ((70, "#ef4444"), (30, "#16a34a")):
        fig.add_hline(y=lvl, line=dict(color=c, width=1, dash="dot"), row=3, col=1)
    # MVRV
    if has_mvrv:
        fig.add_trace(go.Scatter(x=mvrv_s.index, y=mvrv_s.values, name="MVRV", line=dict(color="#06b6d4", width=1.2),
                                 showlegend=False), row=4, col=1)
        fig.add_hline(y=1.0, line=dict(color="#94a3b8", width=1, dash="dot"), row=4, col=1)
    fig.update_layout(template="plotly_white", hovermode="x unified", height=860,
                      margin=dict(l=50, r=20, t=30, b=20),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="USD", row=1, col=1)
    btc_chart = fig.to_html(full_html=False, include_plotlyjs="cdn")
    radar_html = ((_radar("ETH", eth_close, go) if eth_close is not None else "")
                  + _radar("Ouro", load_series(DB, "gold"), go) + _radar("SP500", load_series(DB, "spx"), go))

    # ---------- HTML ----------
    acao = "FORA / HOLD" if fora else f"COMPRADO {sig.recommended_weight*100:.0f}%"
    acao_cor = "#ef4444" if fora else "#16a34a"
    anom_html = (f'<div class="banner warn">⚠️ MOVIMENTO ANÔMALO HOJE ({ret1*100:+.1f}% no dia) — possível flash crash. '
                 f'NÃO reaja intradiário (o sinal é no fechamento). Se for estrutural/estranho, revise manualmente.</div>') if anomaly else ""
    mv_txt = f"{mv_full.iloc[-1]:.2f} (pct {mvrv_pct:.0f}%)" if not mv_full.empty else "—"
    rsi_tag = "sobrevendido" if rsi_last < 30 else "sobrecomprado" if rsi_last > 70 else "neutro"

    def _alloc_rows():
        out = []
        for v in views:
            rc = "#16a34a" if v["regime"] == "BULL" else "#ef4444" if v["regime"] == "BEAR" else "#94a3b8"
            tend = "↑" if v["slope"] > 0.005 else "↓" if v["slope"] < -0.005 else "→"
            p = postures.get(v["name"], {})
            pc, pl = p.get("color", "#cbd5e1"), p.get("posture", v["bias"])
            out.append(f"<tr><td><b>{v['name']}</b></td><td>${v['price']:,.0f}</td>"
                       f"<td style='color:{rc}'>{v['regime']} {tend}</td><td>{v['dist_ma']*100:+.0f}%</td>"
                       f"<td>{v['val_pct']:.0f}%</td><td style='color:{pc};font-weight:600'>{pl}</td></tr>")
        out.append("<tr><td><b>Caixa</b></td><td>—</td><td style='color:#94a3b8'>estável</td><td>—</td><td>—</td>"
                   "<td style='color:#cbd5e1'>reserva / dry powder</td></tr>")
        return "".join(out)

    html = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH_MIN*60}">
<title>TrendFit — Painel</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px}}
 .wrap{{max-width:1180px;margin:0 auto}}
 h1{{font-size:18px;color:#94a3b8;font-weight:600;margin:0 0 4px}}
 h2{{font-size:15px;color:#94a3b8;margin:22px 0 8px}}
 .acao{{font-size:34px;font-weight:800;color:{acao_cor};margin:2px 0 12px}}
 .row{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px}}
 .card{{background:#1e293b;border-radius:12px;padding:14px 18px;min-width:150px}}
 .card .k{{font-size:12px;color:#94a3b8}} .card .v{{font-size:20px;font-weight:700;margin-top:3px}}
 .banner{{border-radius:10px;padding:12px 16px;margin-bottom:14px;font-weight:600}}
 .warn{{background:#7f1d1d;color:#fecaca}} .info{{background:#1e3a5f;color:#bfdbfe}}
 .how{{background:#172033;border:1px solid #334155;border-radius:10px;padding:12px 16px;margin-bottom:14px;font-size:13px;line-height:1.6}}
 .chart{{background:#fff;border-radius:12px;padding:8px;margin-bottom:8px}}
 .radar{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
 .alloc{{background:#1e293b;border-radius:12px;padding:14px 18px;margin-bottom:14px}}
 .alloc table{{width:100%;border-collapse:collapse;font-size:14px}}
 .alloc th{{text-align:left;color:#94a3b8;padding:4px 8px;border-bottom:1px solid #334155}}
 .alloc td{{padding:6px 8px;border-bottom:1px solid #243049}}
 .frag{{margin-top:10px;font-size:13px}} .muted{{color:#64748b;font-weight:400}}
 .scards{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px}}
 .scard{{background:#172033;border:1px solid #334155;border-radius:10px;padding:12px 14px;font-size:13px}}
 .sctop{{font-weight:700;font-size:14px;margin-bottom:8px}}
 .crit{{padding:3px 0;line-height:1.4}} .rat{{margin-top:8px;color:#cbd5e1;font-style:italic;border-top:1px solid #243049;padding-top:8px}}
 .env{{background:#172033;border:1px solid #334155;border-left-width:4px;border-radius:10px;padding:12px 16px;margin-bottom:14px}}
 .envtop{{font-weight:700;font-size:14px;margin-bottom:8px}}
 .echips{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
 .echip{{background:#0f172a;border:1px solid #475569;border-radius:8px;padding:3px 9px;font-size:12px}}
 .envrat{{color:#cbd5e1;font-size:13px;font-style:italic}}
 .posture{{margin-top:8px;border-top:1px solid #243049;border-left:3px solid #475569;padding:8px 0 2px 10px}}
 .pbadge{{color:#0f172a;font-weight:800;font-size:11px;padding:2px 8px;border-radius:6px}}
 .prat{{color:#e2e8f0;font-size:12.5px;margin:6px 0 4px;line-height:1.5}}
 .scen{{color:#94a3b8;font-size:12px;line-height:1.5;margin-top:3px}}
 .foot{{color:#64748b;font-size:12px;margin-top:14px;line-height:1.5}}
</style></head><body><div class="wrap">
 <h1>TrendFit · Bitcoin · sinal do sistema (config {last.lookbacks})</h1>
 <div class="acao">{acao} &nbsp;·&nbsp; ${sig.price:,.0f}</div>
 {anom_html}
 <div class="banner info">Tendência diária: <b>{'↑ ALTA' if trend_up else '↓ BAIXA/LATERAL'}</b> · regime
   <b>{'BULL' if sig.regime_bull else 'BEAR'}</b> ·
   {'reentrada exige preço &gt; MA200 (~+'+format(gap,'.0f')+'%)' if fora else 'mantém enquanto regime/trailing seguram'}</div>
 <div class="how"><b>Como o sistema decide</b> (só preço — macro/RSI/MVRV NÃO acionam, são contexto):<br>
   🟢 <b>COMPRA</b> quando: preço &gt; MA200 (regime bull) <b>E</b> rompimento Donchian (ensemble vota comprado).<br>
   🔴 <b>VENDE</b> (caixa) quando: perde a MA200 (regime vira bear) <b>OU</b> dispara o trailing ATR.<br>
   Passe o mouse em cada trade no gráfico pra ver o motivo e o resultado.</div>
 {env_html}
 <div class="row">
  <div class="card"><div class="k">Ação do sistema</div><div class="v" style="color:{acao_cor}">{acao}</div></div>
  <div class="card"><div class="k">Preço BTC</div><div class="v">${sig.price:,.0f}</div></div>
  <div class="card"><div class="k">MA200 (regime)</div><div class="v">${sig.ma_value:,.0f}</div></div>
  <div class="card"><div class="k">RSI(14) <span class="muted">·info</span></div><div class="v">{rsi_last:.0f} <span style="font-size:13px;color:#94a3b8">{rsi_tag}</span></div></div>
  <div class="card"><div class="k">MVRV <span class="muted">·info</span></div><div class="v">{mv_txt}</div></div>
  <div class="card"><div class="k">Variação no dia</div><div class="v">{ret1*100:+.1f}%</div></div>
 </div>
 <div class="alloc"><div style="font-weight:700;margin-bottom:8px">Radar de Alocação · multi-ativo <span class="muted">(classifica, não prevê)</span></div>
  <table><tr><th>ativo</th><th>preço</th><th>regime</th><th>vs MA200</th><th>valuation</th><th>postura <span class="muted">(informa · regime decide)</span></th></tr>{_alloc_rows()}</table>
  <div class="frag">Fragilidade do ambiente: <b style="color:{frag_cor}">{frag}</b> <span class="muted">[{frag_why}]</span></div></div>
 {pm_html}
 <h2>Critérios da decisão — por que entrar / sair / segurar</h2>
 {scorecard_html}
 <h2>Bitcoin — preço, sinais, volume, RSI, MVRV</h2>
 <div class="chart">{btc_chart}</div>
 <h2>Radar — outros ativos monitorados</h2>
 <div class="radar">{radar_html}</div>
 <div class="foot">Trades: segmento entrada→saída colorido pelo RESULTADO (<b style="color:#16a34a">verde lucro</b>/<b style="color:#ef4444">vermelho perda</b>), % no hover.
   Faixa rosa = regime bear. Volume verde/vermelho = dia de alta/baixa. RSI/MVRV são <b>contexto, não acionam</b>.
   Ouro/SP500 podem estar alguns dias defasados (fonte externa). Última barra BTC: {sig.date.date()}.
   Atualiza a cada {REFRESH_MIN} min · /refresh força agora. <b>Não é recomendação de investimento.</b></div>
</div></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"OK | {sig.date.date()} ${sig.price:,.0f} | {acao} | tend {'ALTA' if trend_up else 'BAIXA'} "
          f"| RSI {rsi_last:.0f} | anomalia={anomaly} | trades_plot={len(trades)} | mvrv={'sim' if has_mvrv else 'nao'}")
    print(f"HTML: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
