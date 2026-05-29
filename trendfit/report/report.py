"""Relatório do walk-forward: HTML interativo (Plotly) + resumo de console.

Mostra a equity curve do sistema (com veto) contra Buy & Hold no MESMO período
out-of-sample, a tabela de métricas e o detalhamento por janela do walk-forward.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trendfit.engine.walkforward import WalkForwardResult


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


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
) -> Path:
    """Gera HTML interativo com equity curves e tabela de métricas. Retorna o caminho."""
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
            f"Preço {asset} (USD) no período OOS",
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
    fig.add_trace(
        go.Scatter(x=price_oos.index, y=price_oos.values,
                   name=f"{asset} preço", line=dict(color="#f59e0b", width=1)),
        row=2, col=1,
    )

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
