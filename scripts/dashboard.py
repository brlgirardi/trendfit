"""Dashboard TrendFit BTC — painel HTML auto-contido (status + gráfico + anomalias).

Gera reports/dashboard.html: cabeçalho com a AÇÃO de hoje, tendência diária, cards
(RSI/MVRV/regime/distância MA200), detector de anomalia (flash crash / movimento
anômalo) e o gráfico de sinais. Pensado pra ser regenerado por cron e servido (VPS,
Vercel static, GitHub Pages). Auto-refresh embutido (recarrega a página).

FILOSOFIA: o sinal é DIÁRIO (muda no fechamento). Anomalias intradiárias são FLAGADAS
mas NÃO mudam o sinal — a ação em flash crash é "não reagir, aguardar o fechamento".
Casos genuinamente estranhos: o painel recomenda revisar manualmente, não automatiza
julgamento de cauda.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.signal import current_signal, position_events  # noqa: E402
from trendfit.engine.strategy import StrategyConfig, target_weights  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"
OUT = ROOT / "reports" / "dashboard.html"
START = "2023-06-01"
REFRESH_MIN = 60


def _rsi(close, period=14):
    d = close.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    rs = up.ewm(alpha=1/period, adjust=False).mean() / dn.ewm(alpha=1/period, adjust=False).mean()
    return float((100 - 100/(1+rs)).iloc[-1])


def _load_ctx():
    try:
        from trendfit.data.external import load_series
        mv = load_series(DB, "mvrv")
        if mv.empty:
            return None
        return float(mv.iloc[-1]), (mv < mv.iloc[-1]).mean() * 100
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    dcfg = prof["data"]; exchanges = [tuple(x) for x in dcfg["exchanges"]]
    with OHLCVCache(DB) as cache:
        df = fetch_ohlcv_daily(cache, cache_symbol=dcfg["cache_symbol"],
                               timeframe=dcfg["timeframe"], exchanges=exchanges)
    df = df[~df.index.duplicated(keep="last")].sort_index()

    cands = []
    for lname, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for bnd, atrk in g["variants"]:
                cands.append((f"{lname}|a{asym}|b{bnd}|k{atrk}", lbs,
                              StrategyConfig(ma_window=e["ma_window"], band=bnd,
                                             mode="long_asym", asym=asym, atr_k=atrk)))
    wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"],
                           cost_bps=e["cost_bps"])
    last = wf.steps[-1]
    nm = last.chosen
    cfg = StrategyConfig(ma_window=e["ma_window"], band=float(nm.split("|b")[1].split("|")[0]),
                         mode="long_asym", asym=float(nm.split("|a")[1].split("|")[0]),
                         atr_k=float(nm.split("|k")[1]))
    w_live = pd.Series(target_weights(df, last.lookbacks, cfg), index=df.index)
    w_full = w_live.copy(); w_full.loc[wf.oos_weights.index] = wf.oos_weights.values

    price = df["Close"]
    sig = current_signal(df, last.lookbacks, kind=e["kind"], ma_window=e["ma_window"])
    fora = sig.recommended_weight <= 0

    # tendência diária: preço vs MA20 + inclinação MA20
    ma20 = price.rolling(20).mean()
    trend_up = bool(price.iloc[-1] > ma20.iloc[-1] and ma20.iloc[-1] > ma20.iloc[-6])
    # anomalia: retorno diário extremo (flash crash / spike)
    ret1 = float(price.iloc[-1] / price.iloc[-2] - 1)
    vol30 = float(price.pct_change().iloc[-30:].std())
    anomaly = abs(ret1) > max(0.10, 4 * vol30)  # >10% ou >4 desvios
    rsi_now = _rsi(price)
    ctx = _load_ctx()
    gap = (sig.ma_value / sig.price - 1) * 100 if sig.price else float("nan")

    # ---- gráfico (sinais) ----
    import plotly.graph_objects as go
    pr = price.loc[START:]; ma200 = price.rolling(e["ma_window"]).mean().loc[START:]
    ev = position_events(w_full.loc[START:], pr, threshold=0.05)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pr.index, y=pr.values, name="BTC", line=dict(color="#f59e0b", width=1.5)))
    fig.add_trace(go.Scatter(x=ma200.index, y=ma200.values, name="MA200", line=dict(color="#3b82f6", width=1.2, dash="dash")))
    bear = (pr < ma200).fillna(False); spans=[]; st=None; idx=bear.index; vals=bear.to_numpy()
    for i,v in enumerate(vals):
        if v and st is None: st=idx[i]
        elif not v and st is not None: spans.append((st,idx[i])); st=None
    if st is not None: spans.append((st, idx[-1]))
    for x0,x1 in spans:
        fig.add_vrect(x0=x0.isoformat(), x1=x1.isoformat(), fillcolor="#ef4444", opacity=0.07, line_width=0, layer="below")
    buys = ev[ev["kind"]=="entry"] if not ev.empty else ev
    sells = ev[ev["kind"]=="exit"] if not ev.empty else ev
    if not buys.empty:
        fig.add_trace(go.Scatter(x=buys["date"], y=buys["price"], mode="markers", name="COMPRA",
            marker=dict(symbol="triangle-up", color="#16a34a", size=13)))
    if not sells.empty:
        fig.add_trace(go.Scatter(x=sells["date"], y=sells["price"], mode="markers", name="VENDA",
            marker=dict(symbol="triangle-down", color="#ef4444", size=13)))
    fig.add_trace(go.Scatter(x=[sig.date], y=[sig.price], mode="markers", name="HOJE",
        marker=dict(symbol="circle", color=("#ef4444" if fora else "#16a34a"), size=12, line=dict(width=2,color="white"))))
    fig.update_layout(template="plotly_white", hovermode="x unified", height=520,
                      margin=dict(l=40,r=20,t=20,b=30),
                      legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1))
    chart = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # ---- HTML ----
    acao = "FORA / HOLD" if fora else f"COMPRADO {sig.recommended_weight*100:.0f}%"
    acao_cor = "#ef4444" if fora else "#16a34a"
    anom_html = (f'<div class="banner warn">⚠️ MOVIMENTO ANÔMALO HOJE ({ret1*100:+.1f}% no dia). '
                 f'Possível flash crash. AÇÃO: não reaja intradiário — o sinal é no fechamento. '
                 f'Se for algo estrutural/estranho, revise manualmente antes de agir.</div>') if anomaly else ""
    mv_txt = f"{ctx[0]:.2f} (pct {ctx[1]:.0f}%)" if ctx else "—"
    rsi_tag = "sobrevendido" if rsi_now < 30 else "sobrecomprado" if rsi_now > 70 else "neutro"
    html = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH_MIN*60}">
<title>TrendFit BTC — Painel</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px}}
 .wrap{{max-width:1200px;margin:0 auto}}
 h1{{font-size:18px;color:#94a3b8;font-weight:600;margin:0 0 4px}}
 .acao{{font-size:34px;font-weight:800;color:{acao_cor};margin:2px 0 12px}}
 .row{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px}}
 .card{{background:#1e293b;border-radius:12px;padding:14px 18px;min-width:150px}}
 .card .k{{font-size:12px;color:#94a3b8}} .card .v{{font-size:20px;font-weight:700;margin-top:3px}}
 .banner{{border-radius:10px;padding:12px 16px;margin-bottom:14px;font-weight:600}}
 .warn{{background:#7f1d1d;color:#fecaca}} .info{{background:#1e3a5f;color:#bfdbfe}}
 .chart{{background:#fff;border-radius:12px;padding:8px}}
 .foot{{color:#64748b;font-size:12px;margin-top:14px;line-height:1.5}}
</style></head><body><div class="wrap">
 <h1>TrendFit · Bitcoin · sinal do sistema (config {last.lookbacks})</h1>
 <div class="acao">{acao} &nbsp;·&nbsp; ${sig.price:,.0f}</div>
 {anom_html}
 <div class="banner info">Tendência diária: <b>{'↑ ALTA' if trend_up else '↓ BAIXA/LATERAL'}</b> ·
   regime <b>{'BULL' if sig.regime_bull else 'BEAR'}</b> ·
   {'reentrada exige preço > MA200 (~+'+format(gap,'.0f')+'%)' if fora else 'mantém enquanto regime/trailing seguram'}</div>
 <div class="row">
  <div class="card"><div class="k">Ação do sistema</div><div class="v" style="color:{acao_cor}">{acao}</div></div>
  <div class="card"><div class="k">Preço BTC</div><div class="v">${sig.price:,.0f}</div></div>
  <div class="card"><div class="k">MA200 (regime)</div><div class="v">${sig.ma_value:,.0f}</div></div>
  <div class="card"><div class="k">RSI(14) <span style="color:#64748b">·informativo</span></div><div class="v">{rsi_now:.0f} <span style="font-size:13px;color:#94a3b8">{rsi_tag}</span></div></div>
  <div class="card"><div class="k">MVRV <span style="color:#64748b">·informativo</span></div><div class="v">{mv_txt}</div></div>
  <div class="card"><div class="k">Variação no dia</div><div class="v">{ret1*100:+.1f}%</div></div>
 </div>
 <div class="chart">{chart}</div>
 <div class="foot">▲ verde = COMPRA · ▼ vermelho = VENDA (caixa) · faixa vermelha = regime bear (fora) ·
   ponto = hoje. Atualiza a cada {REFRESH_MIN} min (se o backend regenerar). Sinal é DIÁRIO (muda no
   fechamento); RSI/MVRV são informativos e NÃO acionam o sistema (testados, não melhoram).
   Última barra: {sig.date.date()}. <b>Não é recomendação de investimento.</b></div>
</div></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"OK | {sig.date.date()} ${sig.price:,.0f} | {acao} | tendência {'ALTA' if trend_up else 'BAIXA/LATERAL'} "
          f"| anomalia={anomaly} (dia {ret1*100:+.1f}%) | RSI {rsi_now:.0f}")
    print(f"HTML: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
