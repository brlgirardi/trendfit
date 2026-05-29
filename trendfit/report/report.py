"""Relatório do walk-forward: HTML interativo (Plotly) + resumo de console.

Mostra a equity curve do sistema (com veto) contra Buy & Hold no MESMO período
out-of-sample, a tabela de métricas e o detalhamento por janela do walk-forward.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trendfit.engine.signal import position_events
from trendfit.engine.walkforward import WalkForwardResult


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _contiguous_true_spans(mask: pd.Series) -> list[tuple]:
    """Lista de (início, fim) dos trechos contíguos onde mask é True (p/ sombreamento)."""
    spans, start = [], None
    idx = mask.index
    vals = mask.to_numpy()
    for i, v in enumerate(vals):
        if v and start is None:
            start = idx[i]
        elif not v and start is not None:
            spans.append((start, idx[i]))
            start = None
    if start is not None:
        spans.append((start, idx[-1]))
    return spans


def _add_event_markers(fig, events: pd.DataFrame, go) -> None:
    """Adiciona triângulos de entrada/saída sobre o gráfico de preço (row=2)."""
    styles = {
        "entry": dict(symbol="triangle-up", color="#16a34a", name="Entrada LONG"),
        "scale_in": dict(symbol="triangle-up-open", color="#16a34a", name="Aumenta posição"),
        "scale_out": dict(symbol="triangle-down-open", color="#f97316", name="Reduz posição"),
        "exit": dict(symbol="triangle-down", color="#ef4444", name="Saída (caixa)"),
    }
    for kind, st in styles.items():
        sub = events[events["kind"] == kind] if not events.empty else events
        if sub.empty:
            continue
        # tamanho do marker proporcional à magnitude da mudança de peso
        sizes = (8 + (sub["w_to"] - sub["w_from"]).abs() * 14).tolist()
        fig.add_trace(
            go.Scatter(
                x=sub["date"], y=sub["price"], mode="markers", name=st["name"],
                marker=dict(symbol=st["symbol"], color=st["color"], size=sizes,
                            line=dict(width=1, color=st["color"])),
                text=sub["label"], hovertemplate="%{text}<br>%{x|%Y-%m-%d} · $%{y:,.0f}<extra></extra>",
            ),
            row=2, col=1,
        )


def format_console_summary(wf: WalkForwardResult, asset: str = "BTC") -> str:
    """Resumo textual honesto para stdout / log / VERDICT."""
    m, mnv, bh = wf.oos_metrics, wf.oos_metrics_noveto, wf.benchmark
    p0, p1 = wf.oos_period
    lines = []
    lines.append("=" * 72)
    lines.append(f" WALK-FORWARD {asset} — Out-of-Sample real")
    lines.append(f" Período OOS: {p0.date()} -> {p1.date()}  ({m['n_days']} dias)")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"  {'':24}{'Retorno':>12}{'CAGR':>10}{'MaxDD':>10}{'Sharpe':>9}{'Exposição':>11}")
    lines.append(
        f"  {'Sistema (núcleo+veto)':24}{_pct(m['total_return']):>12}{_pct(m['cagr']):>10}"
        f"{_pct(m['max_drawdown']):>10}{m['sharpe']:>9.2f}{_pct(m['avg_exposure']):>11}"
    )
    lines.append(
        f"  {'Núcleo SEM veto':24}{_pct(mnv['total_return']):>12}{_pct(mnv['cagr']):>10}"
        f"{_pct(mnv['max_drawdown']):>10}{mnv['sharpe']:>9.2f}{_pct(mnv['avg_exposure']):>11}"
    )
    lines.append(
        f"  {'Buy & Hold':24}{_pct(bh.total_return):>12}{_pct(bh.cagr):>10}"
        f"{_pct(bh.max_drawdown):>10}{bh.sharpe:>9.2f}{_pct(bh.avg_exposure):>11}"
    )
    lines.append("")
    if wf.beat_buy_and_hold:
        edge = wf.oos_metrics["total_return"] - bh.total_return
        lines.append(f"  >>> SISTEMA bateu o Buy & Hold por {_pct(edge)} (retorno absoluto OOS)")
    else:
        gap = bh.total_return - wf.oos_metrics["total_return"]
        lines.append(f"  >>> Buy & Hold venceu por {_pct(gap)} em retorno — mas comparar drawdown:")
    dd_sys, dd_bh = m["max_drawdown"], bh.max_drawdown
    lines.append(f"      MaxDD sistema {_pct(dd_sys)} vs B&H {_pct(dd_bh)} "
                 f"(proteção de {_pct(dd_bh - dd_sys)})")
    lines.append(f"  >>> Veto {'AJUDOU' if wf.veto_helped else 'ATRAPALHOU'}: "
                 f"sistema {_pct(m['total_return'])} vs sem-veto {_pct(mnv['total_return'])}")
    lines.append("")
    lines.append("  Janelas walk-forward (config escolhida no treino, retorno OOS no teste cego):")
    for s in wf.steps:
        lines.append(
            f"    {s.test_start.date()}..{s.test_end.date()}  "
            f"escolheu '{s.chosen}' {s.lookbacks:}  "
            f"OOS: com_veto {_pct(s.oos_return_veto)} | sem_veto {_pct(s.oos_return_noveto)}"
        )
    lines.append("=" * 72)
    return "\n".join(lines)


def build_report(
    wf: WalkForwardResult,
    price: pd.Series,
    out_path: str | Path,
    asset: str = "BTC",
    ma_window: int = 200,
) -> Path:
    """Gera HTML interativo com equity curves, preço com markers de entrada/saída,
    MA200, sombreamento de regime bear e tabela de métricas. Retorna o caminho."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bh_eq = wf.benchmark.equity
    p0, p1 = wf.oos_period
    price_oos = price.loc[p0:p1]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.62, 0.38], vertical_spacing=0.07,
        subplot_titles=(
            f"Equity Out-of-Sample (base 1.0) — {asset}: sistema vs Buy & Hold",
            f"Preço {asset} + entradas/saídas do sistema (long-only; vermelho=regime bear/veto)",
        ),
    )
    fig.add_trace(
        go.Scatter(x=wf.oos_equity.index, y=wf.oos_equity.values,
                   name="Sistema (núcleo+veto)", line=dict(color="#16a34a", width=2)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=bh_eq.index, y=bh_eq.values,
                   name="Buy & Hold", line=dict(color="#94a3b8", width=2, dash="dot")),
        row=1, col=1,
    )
    # --- Preço + MA200 (referência de regime) ---
    fig.add_trace(
        go.Scatter(x=price_oos.index, y=price_oos.values,
                   name=f"{asset} preço", line=dict(color="#f59e0b", width=1.2)),
        row=2, col=1,
    )
    ma200 = price.rolling(ma_window).mean().loc[p0:p1]
    fig.add_trace(
        go.Scatter(x=ma200.index, y=ma200.values, name=f"MA{ma_window}",
                   line=dict(color="#3b82f6", width=1, dash="dash")),
        row=2, col=1,
    )

    # --- Sombreamento dos períodos de regime BEAR (veto ativo: peso forçado a 0) ---
    bear = (price_oos < ma200).fillna(False)
    for x0, x1 in _contiguous_true_spans(bear):
        for r in (1, 2):
            fig.add_vrect(x0=x0, x1=x1, fillcolor="#ef4444", opacity=0.06,
                          line_width=0, layer="below", row=r, col=1)

    # --- Markers de entrada/saída sobre o preço (estilo TradingView) ---
    ev = position_events(wf.oos_weights, price_oos)
    _add_event_markers(fig, ev, go)

    m, bh = wf.oos_metrics, wf.benchmark
    caption = (
        f"OOS {p0.date()}→{p1.date()} | "
        f"Sistema: {_pct(m['total_return'])} (MaxDD {_pct(m['max_drawdown'])}, Sharpe {m['sharpe']:.2f}) | "
        f"B&H: {_pct(bh.total_return)} (MaxDD {_pct(bh.max_drawdown)}, Sharpe {bh.sharpe:.2f})"
    )
    fig.update_layout(
        title=dict(text=f"TrendFit — Walk-Forward {asset}<br><sub>{caption}</sub>"),
        template="plotly_white", hovermode="x unified", height=760,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Equity (×)", row=1, col=1)
    fig.update_yaxes(title_text="USD", row=2, col=1)
    fig.write_html(str(out_path), include_plotlyjs="cdn")
    return out_path
