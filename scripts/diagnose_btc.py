"""Diagnóstico trade-a-trade do núcleo atual (long-only Donchian + veto MA200).

Cruza os dados para quantificar o que o usuário observou: "vendeu na baixa,
comprou na alta" (whipsaw). Não altera nada — só mede e reporta a verdade.
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
from trendfit.engine.walkforward import walk_forward  # noqa: E402
from trendfit.layers.regime import regime_allow  # noqa: E402


def round_trips(weights: pd.Series, price: pd.Series) -> pd.DataFrame:
    """Segmenta em 'trades': cada período contíguo com peso>0 é um round-trip.

    Retorna entrada/saída/dias/retorno do segmento (peso médio aplicado).
    """
    w = weights.reindex(price.index).fillna(0.0).to_numpy()
    p = price.to_numpy()
    idx = price.index
    trades = []
    in_pos = False
    start_i = 0
    for i in range(len(w)):
        if w[i] > 0 and not in_pos:
            in_pos, start_i = True, i
        elif w[i] == 0 and in_pos:
            in_pos = False
            seg_ret = p[i] / p[start_i] - 1.0
            trades.append((idx[start_i], idx[i], i - start_i, p[start_i], p[i], seg_ret))
    if in_pos:
        seg_ret = p[-1] / p[start_i] - 1.0
        trades.append((idx[start_i], idx[-1], len(w) - 1 - start_i, p[start_i], p[-1], seg_ret))
    return pd.DataFrame(
        trades, columns=["entrada", "saida", "dias", "preco_in", "preco_out", "ret_preco"]
    )


def main() -> int:
    prof = json.load(open(ROOT / "profiles" / "btc.json"))
    e, w = prof["engine"], prof["walkforward"]
    with OHLCVCache(ROOT / "db" / "trendfit.sqlite") as cache:
        df = fetch_ohlcv_daily(cache, "BTC", "1d")
    df = df[~df.index.duplicated()].sort_index()

    wf = walk_forward(df, e["ensembles"], e["kind"], w["train_days"], w["test_days"],
                      e["ma_window"], e["cost_bps"])
    p0, p1 = wf.oos_period
    price = df["Close"].loc[p0:p1]
    weights = wf.oos_weights

    print("=" * 70)
    print(" DIAGNÓSTICO — núcleo long-only Donchian + veto MA200 (OOS real)")
    print(f" Período: {p0.date()} -> {p1.date()}")
    print("=" * 70)

    rt = round_trips(weights, price)
    losers = rt[rt["ret_preco"] < 0]
    winners = rt[rt["ret_preco"] > 0]
    print(f"\n  Round-trips (entra->sai do mercado): {len(rt)}")
    print(f"  Vencedores: {len(winners)} | Perdedores: {len(losers)} "
          f"| Win rate: {len(winners)/max(len(rt),1)*100:.0f}%")
    print(f"  Duração mediana de um trade: {rt['dias'].median():.0f} dias "
          f"(min {rt['dias'].min():.0f}, max {rt['dias'].max():.0f})")
    whip = rt[rt["dias"] <= 5]
    print(f"  Trades 'pipoca' (<=5 dias): {len(whip)} "
          f"({len(whip)/max(len(rt),1)*100:.0f}% dos trades)")
    print(f"  Retorno médio (preço) dos trades curtos <=5d: {whip['ret_preco'].mean()*100:+.1f}%")

    # quantos 'sell low / buy back higher': saiu e a próxima entrada foi a preço MAIOR
    rebuys_higher = 0
    for k in range(len(rt) - 1):
        if rt.iloc[k + 1]["preco_in"] > rt.iloc[k]["preco_out"]:
            rebuys_higher += 1
    print(f"  Recompras a preço MAIOR que a saída anterior: {rebuys_higher}/{len(rt)-1} "
          f"(o clássico 'vendeu na baixa, recomprou na alta')")

    # quanto da decisão é o veto MA200 oscilando perto da linha
    allow = pd.Series(regime_allow(df, e["ma_window"]), index=df.index).loc[p0:p1]
    flips = int((allow != allow.shift(1)).sum())
    ma = df["Close"].rolling(e["ma_window"]).mean().loc[p0:p1]
    near = (abs(price - ma) / ma < 0.05)  # dentro de 5% da MA200
    print(f"\n  Veto MA200: {flips} viradas bull<->bear no período")
    print(f"  Dias com preço a <5% da MA200 (zona de chicote): {int(near.sum())} "
          f"({near.mean()*100:.0f}% do tempo)")

    print("\n  Piores 5 trades (preço):")
    for _, r in rt.nsmallest(5, "ret_preco").iterrows():
        print(f"    {r['entrada'].date()} ${r['preco_in']:,.0f} -> "
              f"{r['saida'].date()} ${r['preco_out']:,.0f}  "
              f"({r['dias']:.0f}d, {r['ret_preco']*100:+.1f}%)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
