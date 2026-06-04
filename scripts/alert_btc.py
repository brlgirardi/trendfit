"""Alerta de AÇÃO do sistema TrendFit (BTC) — detecta mudança de estado e avisa.

Emite um dos estados, comparando com a última execução (state file):
  COMPRA / ENTRA      — regime virou bull + ensemble vota comprado (0% -> X%)
  AUMENTA             — peso sobe (tendência fortalece)
  REDUZ               — peso cai mas ainda comprado
  VENDE / SAI 100%    — vai a 0%: regime virou bear (perde MA200) OU trailing ATR
  MANTÉM              — sem mudança de banda

IMPORTANTE: o gatilho de SAÍDA é REGIME (preço < MA200) / fim de tendência — NÃO é
"sobrevendido". Trend-following não vende por sobrevenda (isso é mean-reversion, refutada
no BTC, ver docs/STRATEGY_COMPARISON.md). MVRV/funding entram só como CONTEXTO informativo.

Uso (rodar quando quiser, ou via cron/loop):
    .venv/bin/python scripts/alert_btc.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from trendfit.data import OHLCVCache, fetch_ohlcv_daily  # noqa: E402
from trendfit.engine.signal import current_signal  # noqa: E402


def _rsi(close: pd.Series, period: int = 14) -> float:
    d = close.diff()
    up = d.clip(lower=0.0); dn = -d.clip(upper=0.0)
    rs = (up.ewm(alpha=1 / period, adjust=False).mean()
          / dn.ewm(alpha=1 / period, adjust=False).mean())
    return float((100 - 100 / (1 + rs)).iloc[-1])
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward_grid  # noqa: E402

DB = ROOT / "db" / "trendfit.sqlite"
STATE = ROOT / "db" / "alert_state.json"


def band(w: float) -> str:
    if w <= 0.0:
        return "FORA"
    if w < 0.33:
        return "LEVE"
    if w < 0.66:
        return "PARCIAL"
    return "FORTE"


def _context() -> str:
    """MVRV e funding como contexto informativo (não dispara ação). Best-effort."""
    try:
        from trendfit.data.external import load_series
        mv = load_series(DB, "mvrv"); fu = load_series(DB, "funding")
        if mv.empty:
            return "  contexto on-chain: (sem dado)"
        mv_now = mv.iloc[-1]; pct = (mv < mv_now).mean() * 100
        f30 = fu.iloc[-30:].mean() if not fu.empty else float("nan")
        return (f"  contexto (informativo, NÃO dispara ação): "
                f"MVRV {mv_now:.2f} (percentil {pct:.0f}% — {'<1 capitulação' if mv_now < 1 else 'neutro' if mv_now < 3.5 else 'euforia'}) | "
                f"funding 30d {f30:+.4f}")
    except Exception as exc:  # noqa: BLE001
        return f"  contexto on-chain indisponível ({type(exc).__name__})"


def main() -> int:
    profile = json.loads((ROOT / "profiles" / "btc.json").read_text())
    e, w, g = profile["engine"], profile["walkforward"], profile["grid"]
    dcfg = profile["data"]
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
    last_cfg = wf.steps[-1].lookbacks
    sig = current_signal(df, last_cfg, kind=e["kind"], ma_window=e["ma_window"])

    w_now = round(sig.recommended_weight, 2)
    b_now = band(w_now)

    prev = {}
    if STATE.exists():
        prev = json.loads(STATE.read_text())
    w_prev = prev.get("weight", None)
    b_prev = prev.get("band", None)

    # classifica a ação vs estado anterior
    if w_prev is None:
        action = "ESTADO INICIAL"
    elif b_prev == "FORA" and b_now != "FORA":
        action = "🟢 COMPRA / ENTRA"
    elif b_prev != "FORA" and b_now == "FORA":
        action = "🔴 VENDE / SAI 100%"
    elif w_now > (w_prev or 0) + 0.01:
        action = "🟢 AUMENTA posição"
    elif w_now < (w_prev or 0) - 0.01:
        action = "🟡 REDUZ posição"
    else:
        action = "⚪ MANTÉM posição"

    why = (f"regime {'BULL (libera)' if sig.regime_bull else 'BEAR (veta)'} "
           f"(preço ${sig.price:,.0f} vs MA200 ${sig.ma_value:,.0f}) | "
           f"ensemble {last_cfg}: {sig.ensemble_vote*100:.0f}% comprado")

    print("=" * 76)
    print(f" ALERTA TrendFit BTC — {sig.date.date()}  | preço ${sig.price:,.0f}")
    print("=" * 76)
    print(f"  AÇÃO: {action}")
    print(f"  posição recomendada: {w_now*100:.0f}%  ({b_now})  | antes: "
          f"{'—' if w_prev is None else f'{w_prev*100:.0f}% ({b_prev})'}")
    print(f"  motivo: {why}")
    print(f"  leitura: {sig.reading}")
    rsi_now = _rsi(df["Close"])
    rsi_tag = ("SOBREVENDIDO" if rsi_now < 30 else "SOBRECOMPRADO" if rsi_now > 70 else "neutro")
    print(f"  termômetro curto prazo (INFORMATIVO — testado, NÃO melhora o sistema): "
          f"RSI(14)={rsi_now:.0f} ({rsi_tag})")
    print(_context())
    if b_now == "FORA":
        gap = (sig.ma_value / sig.price - 1) * 100 if sig.price else float("nan")
        print(f"  >>> reentrada exige preço retomar a MA200 (~+{gap:.0f}% daqui) + ensemble comprar")
    print("=" * 76)

    STATE.write_text(json.dumps({
        "date": str(sig.date.date()), "price": sig.price,
        "weight": w_now, "band": b_now, "action": action,
        "regime_bull": sig.regime_bull, "ma200": sig.ma_value,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
