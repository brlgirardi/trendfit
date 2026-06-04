"""Painel de decisão VISUAL do sistema TrendFit (BTC) — sinais no gráfico + estado de hoje.

Mostra, no período recente:
  - preço + MA200 (linha de regime)
  - sombreamento dos períodos de regime BEAR (sistema fora)
  - markers ▲ COMPRA / ▼ VENDA (saída p/ caixa) que o sistema deu
  - anotação destacada do ESTADO DE HOJE (comprado X% / FORA-HOLD)

Os pesos OOS (honestos, walk-forward) vão até a última janela fechada; o trecho recente
usa a config mais recente escolhida no treino (o que o sistema faria operando ao vivo).
Exporta PNG (reports/btc_live.png) e HTML interativo (reports/btc_live.html).
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
from trendfit.engine.signal import current_signal, paired_trades  # noqa: E402
from trendfit.engine.strategy import StrategyConfig, target_weights  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402
from trendfit.report.report import add_trade_overlays  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"
PNG = ROOT / "reports" / "btc_live.png"
HTML = ROOT / "reports" / "btc_live.html"
START = "2023-06-01"  # janela visual (recente e legível)


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    dcfg = prof["data"]
    exchanges = [tuple(x) for x in dcfg["exchanges"]]
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
    # config mais recente: parse do nome 'curto|a1.0|b0.05|k4.0'
    nm = last.chosen
    asym = float(nm.split("|a")[1].split("|")[0])
    bnd = float(nm.split("|b")[1].split("|")[0])
    atrk = float(nm.split("|k")[1])
    cfg = StrategyConfig(ma_window=e["ma_window"], band=bnd, mode="long_asym", asym=asym, atr_k=atrk)

    # pesos ao vivo (config recente) sobre todo o df; usa OOS honesto onde existe
    w_live = pd.Series(target_weights(df, last.lookbacks, cfg), index=df.index)
    w_full = w_live.copy()
    w_full.loc[wf.oos_weights.index] = wf.oos_weights.values  # OOS honesto onde disponível

    price = df["Close"]
    sig = current_signal(df, last.lookbacks, kind=e["kind"], ma_window=e["ma_window"])

    # recorte visual
    pr = price.loc[START:]
    ma200 = price.rolling(e["ma_window"]).mean().loc[START:]
    wv = w_full.loc[START:]
    # trades completos (entrada->saída) com resultado — omite microajustes do peso fracionário
    trades = paired_trades(wv, pr, threshold=0.05)

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pr.index, y=pr.values, name="BTC", line=dict(color="#f59e0b", width=1.5)))
    fig.add_trace(go.Scatter(x=ma200.index, y=ma200.values, name="MA200 (regime)",
                             line=dict(color="#3b82f6", width=1.3, dash="dash")))
    # sombreamento bear
    bear = (pr < ma200).fillna(False)
    spans, start = [], None
    idx, vals = bear.index, bear.to_numpy()
    for i, v in enumerate(vals):
        if v and start is None:
            start = idx[i]
        elif not v and start is not None:
            spans.append((start, idx[i])); start = None
    if start is not None:
        spans.append((start, idx[-1]))
    for x0, x1 in spans:
        fig.add_vrect(x0=x0.isoformat(), x1=x1.isoformat(), fillcolor="#ef4444",
                      opacity=0.07, line_width=0, layer="below")

    # cada trade = segmento entrada->saída colorido pelo RESULTADO (verde lucro/vermelho perda) + %
    if not trades.empty:
        add_trade_overlays(fig, trades, go)

    # anotação do ESTADO DE HOJE
    fora = sig.recommended_weight <= 0
    estado = ("⏸  HOJE: FORA / HOLD\nnada a fazer — aguardando\nreentrada acima da MA200"
              if fora else f"✔ HOJE: COMPRADO {sig.recommended_weight*100:.0f}%")
    cor = "#ef4444" if fora else "#16a34a"
    fig.add_trace(go.Scatter(x=[sig.date], y=[sig.price], mode="markers", name="HOJE",
                  marker=dict(symbol="circle", color=cor, size=13, line=dict(width=2, color="white")),
                  hovertemplate=f"HOJE {sig.date.date()}<br>$%{{y:,.0f}}<extra></extra>"))
    fig.add_annotation(x=sig.date, y=sig.price, text=estado.replace(chr(10), "<br>"),
                       showarrow=True, arrowhead=2, arrowcolor=cor, arrowwidth=2, ax=-120, ay=-70,
                       bordercolor=cor, borderwidth=2, borderpad=6, bgcolor="white",
                       font=dict(size=12, color=cor), align="left")

    gap = (sig.ma_value / sig.price - 1) * 100 if sig.price else float("nan")
    sub = (f"HOJE {sig.date.date()} · ${sig.price:,.0f} · {'FORA/HOLD' if fora else f'COMPRADO {sig.recommended_weight*100:.0f}%'} · "
           f"regime {'BEAR' if not sig.regime_bull else 'BULL'} · MA200 ${sig.ma_value:,.0f} (reentrada ~+{gap:.0f}%)")
    fig.update_layout(
        title=dict(text=f"TrendFit — Sinais BTC no gráfico (config {last.lookbacks})<br><sub>{sub}</sub>"),
        template="plotly_white", hovermode="x unified", height=720, width=1500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="USD")

    HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(HTML), include_plotlyjs="cdn")
    # kaleido (PNG) não serializa pandas Timestamp: converte x de traces E anotações p/ string
    for tr in fig.data:
        if getattr(tr, "x", None) is not None:
            tr.x = [pd.Timestamp(v).strftime("%Y-%m-%d") if v is not None else None for v in tr.x]
    for ann in fig.layout.annotations:
        if getattr(ann, "x", None) is not None and not isinstance(ann.x, str):
            ann.x = pd.Timestamp(ann.x).strftime("%Y-%m-%d")
    fig.write_image(str(PNG), scale=2)
    print(f"OK | hoje {sig.date.date()} ${sig.price:,.0f} | "
          f"{'FORA/HOLD' if fora else f'COMPRADO {sig.recommended_weight*100:.0f}%'} | "
          f"trades={len(trades)} (ganho {int((trades['win']).sum()) if not trades.empty else 0}/"
          f"{len(trades)}) no recorte desde {START}")
    print(f"PNG: {PNG}\nHTML: {HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
