"""Agente de Alocação — Painel multi-ativo (regime + valuation). NÃO prevê: classifica.

Para cada ativo (BTC, Ouro, SP500, Caixa) mostra, com dados reais do cache:
  - regime de tendência (preço vs MA200 + inclinação) — FATO
  - posição no range histórico (percentil do preço) — FATO
  - valuation: BTC = MVRV (on-chain real); Ouro/SP500 = percentil de preço (PROXY técnica,
    NÃO é valuation fundamental — sem P/E no cache) — rotulado
  - viés de alocação = HEURÍSTICA transparente, AINDA NÃO validada OOS — rotulado

Filosofia (escola Dalio/Graham, não timing): compara onde está o melhor risco/retorno e
sinaliza ambiente caro/barato. Não diz "compra agora" nem "crash em X". O que virar regra
de dinheiro tem que passar pelo walk-forward antes — este painel é a camada de AGREGAÇÃO.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.data.external import load_series  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"


def view(name: str, close: pd.Series, valuation_pct: float | None = None,
         valuation_label: str = "") -> dict:
    close = close.dropna()
    p = float(close.iloc[-1])
    ma200 = close.rolling(200).mean()
    regime = "BULL" if p > ma200.iloc[-1] else "BEAR"
    slope = ma200.iloc[-1] / ma200.iloc[-21] - 1 if len(ma200.dropna()) > 21 else 0.0
    dist_ma = p / ma200.iloc[-1] - 1
    price_pct = float((close < p).mean() * 100)
    val_pct = price_pct if valuation_pct is None else valuation_pct
    # viés heurístico transparente (NÃO validado)
    cheap = val_pct < 35
    expensive = val_pct > 70
    if regime == "BULL" and cheap:
        bias = "ACUMULAR (barato + tendência)"
    elif regime == "BULL" and expensive:
        bias = "MANTER c/ cautela (caro, mas em alta)"
    elif regime == "BEAR" and cheap:
        bias = "ZONA DE INTERESSE (barato; aguardar virada)"
    elif regime == "BEAR" and expensive:
        bias = "EVITAR (caro + tendência de baixa)"
    else:
        bias = "NEUTRO"
    return {"name": name, "price": p, "regime": regime, "slope": slope, "dist_ma": dist_ma,
            "price_pct": price_pct, "val_pct": val_pct, "val_label": valuation_label or "percentil preço (proxy)",
            "bias": bias, "asof": close.index[-1].date()}


def main() -> int:
    with OHLCVCache(DB) as cache:
        btc = fetch_ohlcv_daily(cache, "BTC", "1d")["Close"]
    gold = load_series(DB, "gold")
    spx = load_series(DB, "spx")
    mv = load_series(DB, "mvrv")
    mvrv_pct = float((mv < mv.iloc[-1]).mean() * 100) if not mv.empty else None

    rows = [
        view("BTC", btc, valuation_pct=mvrv_pct,
             valuation_label=f"MVRV {mv.iloc[-1]:.2f} (on-chain, percentil)" if not mv.empty else ""),
        view("Ouro", gold),
        view("SP500", spx),
    ]

    print("=" * 94)
    print(" AGENTE DE ALOCAÇÃO — Painel multi-ativo (regime + valuation) · classifica, NÃO prevê")
    print("=" * 94)
    print(f"  {'ativo':7}{'preço':>12}{'regime':>8}{'vs MA200':>10}{'tend.':>7}{'valuation':>11}{'viés (heurística, NÃO validada)':>34}")
    print("  " + "-" * 90)
    for r in rows:
        tend = "↑" if r["slope"] > 0.005 else "↓" if r["slope"] < -0.005 else "→"
        print(f"  {r['name']:7}{r['price']:>12,.0f}{r['regime']:>8}{r['dist_ma']*100:>+9.0f}%{tend:>7}"
              f"{r['val_pct']:>9.0f}%  {r['bias']:>32}")
    print(f"  {'Caixa':7}{'—':>12}{'estável':>8}{'—':>10}{'→':>7}{'—':>11}{'reserva / dry powder':>34}")
    print("  " + "-" * 90)
    # ambiente / fragilidade (heurística rotulada)
    spx_hot = rows[2]["price_pct"] > 90
    btc_bear = rows[0]["regime"] == "BEAR"
    frag = "ELEVADA" if (spx_hot and btc_bear) else "MODERADA" if spx_hot or btc_bear else "BAIXA"
    print(f"  Fragilidade do ambiente (heurística): {frag}  "
          f"[SP500 percentil {rows[2]['price_pct']:.0f}% · BTC {rows[0]['regime']}]")
    print(f"  datas: BTC {rows[0]['asof']} · Ouro {rows[1]['asof']} · SP500 {rows[2]['asof']}")
    print("=" * 94)
    print("  ⚠️ Viés e fragilidade são HEURÍSTICAS transparentes, NÃO validadas OOS — contexto, não ordem.")
    print("     Valuation real só p/ BTC (MVRV). Ouro/SP500 usam percentil de preço (proxy, falta P/E).")
    print("     Não é recomendação de investimento.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
