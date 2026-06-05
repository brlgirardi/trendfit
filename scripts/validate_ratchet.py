"""Validação SEM vazamento da SAÍDA ASSIMÉTRICA / let-winners-run (trailing RATCHET).

Hipótese (Passo #1): a entrada já é boa; na saída, proteger apertado no começo
(k=3) mas, quando o trade JÁ andou muito a favor (pico >= ratchet_gain, ex +30%),
ALARGAR o trailing para ratchet_k (5-6) e deixar a perna lucrada esticar perto do
topo. Mecanismo no chandelier (trendfit/engine/strategy.py): catraca que trava
(usa o pico, monotônico) — uma vez alargada, não re-aperta numa correção.

Disciplina honesta (igual às 9 hipóteses anteriores):
  - Os parâmetros do ratchet (gain, k largo) entram como NOVAS DIMENSÕES do grid.
  - "off" (k=3 puro) está SEMPRE no pool de candidatos.
  - O walk-forward escolhe o candidato em cada janela usando SÓ o treino.
  - Comparação contra o baseline v3.1 (grid do btc.json) e o B&H, no mesmo OOS.

Se o grid honesto NÃO bater o baseline (+156,8%), o ratchet fica REFUTADO. O número
de referência FIXO (melhor ratchet olhando o OOS) é diagnóstico do teto/overfit, NÃO
é o veredito.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid, walk_forward_strategy  # noqa: E402
from scripts.diagnose_btc import round_trips  # noqa: E402

# Candidatos do RATCHET: (lucro-gatilho, k largo). "off" não está aqui — é o
# próprio baseline k=3/k=4 sem ratchet, sempre presente no pool.
RATCHET_COMBOS = [(0.30, 5.0), (0.30, 6.0), (0.50, 5.0), (0.50, 6.0)]


def line(name, wf, bh, price):
    m = wf.oos_metrics
    rt = round_trips(wf.oos_weights, price)
    avg_d = rt["dias"].mean() if not rt.empty else 0
    calmar = m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0
    return (f"  {name:34}{m['total_return']*100:+7.0f}%{m['max_drawdown']*100:7.0f}%"
            f"{m['sharpe']:7.2f}{calmar:7.2f}{len(rt):6d}{avg_d:7.0f}"
            f"{(m['total_return']-bh.total_return)*100:+8.0f}%")


def build_base(ens, ma, grid):
    """Grid baseline = exatamente o do btc.json (asym x variants [band, atr_k])."""
    cands = []
    for lname, lbs in ens.items():
        for asym in grid["asym"]:
            for band, atrk in grid["variants"]:
                cfg = StrategyConfig(ma_window=ma, band=band, mode="long_asym",
                                     asym=asym, atr_k=atrk)
                cands.append((f"{lname}|a{asym}|b{band}|k{atrk}", lbs, cfg))
    return cands


def build_ratchet(ens, ma, grid):
    """Candidatos ratchet: aplica (gain, k largo) sobre as bases com trailing ativo
    (band=0.05, atr_k in {3,4}). Adicionados ao pool — o baseline 'off' continua lá."""
    cands = []
    base_ks = [atrk for band, atrk in grid["variants"] if atrk > 0]
    for lname, lbs in ens.items():
        for asym in grid["asym"]:
            for base_k in base_ks:
                for rg, rk in RATCHET_COMBOS:
                    cfg = StrategyConfig(ma_window=ma, band=0.05, mode="long_asym",
                                         asym=asym, atr_k=base_k,
                                         ratchet_gain=rg, ratchet_k=rk)
                    cands.append((f"{lname}|a{asym}|k{base_k}|R{rg:.0%}/{rk:.0f}", lbs, cfg))
    return cands


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w, grid = prof["engine"], prof["walkforward"], prof["grid"]
    with OHLCVCache(ROOT / "db" / "trendfit.sqlite") as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated()].sort_index()
    ens, td, ted, ma, cost = e["ensembles"], w["train_days"], w["test_days"], e["ma_window"], e["cost_bps"]

    base = build_base(ens, ma, grid)
    ratchet = build_ratchet(ens, ma, grid)
    pool = base + ratchet

    grid_base = walk_forward_grid(df, base, td, ted, cost)        # reproduz v3.1 (+156,8%)
    grid_pool = walk_forward_grid(df, pool, td, ted, cost)        # baseline + ratchet, honesto
    bh = grid_base.benchmark
    p0, p1 = grid_base.oos_period
    price = df["Close"].loc[p0:p1]

    # Referência FIXA (overfit, só diagnóstico): melhor ratchet escolhido olhando OOS.
    ref_best, ref_ret = None, -1e9
    for rg, rk in RATCHET_COMBOS:
        for base_k in (3.0, 4.0):
            cfg = StrategyConfig(ma_window=ma, band=0.05, mode="long_asym",
                                 asym=1.0, atr_k=base_k, ratchet_gain=rg, ratchet_k=rk)
            r = walk_forward_strategy(df, cfg, ens, td, ted, cost)
            if r.oos_metrics["total_return"] > ref_ret:
                ref_ret, ref_best = r.oos_metrics["total_return"], (r, f"R{rg:.0%}/{rk:.0f} k{base_k}")

    print("=" * 96)
    print(f" VALIDAÇÃO SEM VAZAMENTO — RATCHET / let-winners-run — BTC OOS {p0.date()} -> {p1.date()}")
    print("=" * 96)
    print(f"  {'':34}{'retorno':>7}{'maxDD':>7}{'Sharpe':>7}{'Calmar':>7}{'trades':>6}{'d.méd':>7}{'vs B&H':>8}")
    print("  " + "-" * 92)
    print(line("BASELINE v3.1 (grid k=3, btc.json)", grid_base, bh, price))
    print(line("GRID + ratchet (honesto, no treino)", grid_pool, bh, price))
    print(line(f"[ref overfit] melhor ratchet fixo", ref_best[0], bh, price))
    bhm = bh.summary()
    bcal = bhm["cagr"] / abs(bhm["max_drawdown"])
    print(f"  {'Buy & Hold':34}{bhm['total_return']*100:+7.0f}%{bhm['max_drawdown']*100:7.0f}%"
          f"{bhm['sharpe']:7.2f}{bcal:7.2f}{0:6d}{'-':>7}{0:+8.0f}%")
    print("=" * 96)

    chose_ratchet = sum(1 for s in grid_pool.steps if "|R" in s.chosen)
    print(f"\n  Referência overfit usou: {ref_best[1]} (ret OOS {ref_ret*100:+.0f}%)")
    print(f"  Janelas em que o GRID honesto escolheu um candidato RATCHET: {chose_ratchet}/{len(grid_pool.steps)}")
    print("  Config escolhida pelo GRID honesto (+ratchet) em cada janela (só com treino):")
    for s in grid_pool.steps:
        tag = "  <-- RATCHET" if "|R" in s.chosen else ""
        print(f"    {s.test_start.date()}..{s.test_end.date()}  ->  {s.chosen}  (OOS {s.oos_return_veto*100:+.0f}%){tag}")

    base_ret = grid_base.oos_metrics["total_return"]
    pool_ret = grid_pool.oos_metrics["total_return"]
    verdict = "ADOTAR" if pool_ret > base_ret + 0.005 else ("EMPATE" if abs(pool_ret - base_ret) <= 0.005 else "REFUTADO")
    print(f"\n  VEREDITO: ratchet honesto {pool_ret*100:+.1f}% vs baseline {base_ret*100:+.1f}% "
          f"(delta {(pool_ret-base_ret)*100:+.1f}pp) -> {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
