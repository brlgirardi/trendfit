"""Runner da Sprint 1 — BTC, dados reais, walk-forward vs Buy & Hold.

Fluxo:
  1. Carrega o perfil do ativo (profiles/btc.json).
  2. Coleta OHLCV diário real via CCXT (cache SQLite).
  3. Roda o walk-forward multi-ciclo (treino 4a -> teste 1a cego).
  4. Imprime resumo OOS vs Buy & Hold + sinal atual.
  5. Gera relatório HTML (equity curve interativa).

Uso:
    python -m scripts.run_btc_sprint1            # usa profiles/btc.json
    python scripts/run_btc_sprint1.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendfit.data import OHLCVCache, fetch_ohlcv_daily, CollectorError  # noqa: E402
from trendfit.engine.signal import current_signal  # noqa: E402
from trendfit.engine.strategy import StrategyConfig  # noqa: E402
from trendfit.engine.walkforward import walk_forward, walk_forward_strategy  # noqa: E402
from trendfit.report import build_report, format_console_summary  # noqa: E402

DB_PATH = ROOT / "db" / "trendfit.sqlite"
REPORT_PATH = ROOT / "reports" / "btc_walkforward.html"


def main() -> int:
    # Perfil default = btc.json (v1). Passar outro perfil: python scripts/run_btc_sprint1.py profiles/btc_v2.json
    profile_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "profiles" / "btc.json"
    profile = json.loads(profile_path.read_text())
    asset = profile["asset"]
    dcfg, ecfg, wcfg = profile["data"], profile["engine"], profile["walkforward"]
    scfg = profile.get("strategy")  # bloco opcional: se presente, usa o núcleo v2
    exchanges = [tuple(x) for x in dcfg["exchanges"]]

    print(f"[1/5] Coletando OHLCV real de {asset}...")
    try:
        with OHLCVCache(DB_PATH) as cache:
            df = fetch_ohlcv_daily(
                cache,
                cache_symbol=dcfg["cache_symbol"],
                timeframe=dcfg["timeframe"],
                exchanges=exchanges,
            )
    except CollectorError as exc:
        print("\n[ERRO] Coleta de dados reais falhou — NÃO vou inventar dados.")
        print(exc)
        print("\nAbortando. (Sem dados reais, sem veredito.)")
        return 3

    df = df[~df.index.duplicated(keep="last")].sort_index()
    print(f"      {len(df)} candles | {df.index[0].date()} -> {df.index[-1].date()}")

    if scfg:
        print(f"[2/5] Walk-forward núcleo v2 ({scfg['mode']}, banda={scfg['band']:.0%}, "
              f"cooldown={scfg['min_hold']}d)...")
        cfg = StrategyConfig(
            ma_window=ecfg["ma_window"], band=scfg["band"],
            mode=scfg["mode"], min_hold=scfg["min_hold"],
        )
        wf = walk_forward_strategy(df, cfg, ensembles=ecfg["ensembles"],
                                   train_days=wcfg["train_days"], test_days=wcfg["test_days"],
                                   cost_bps=ecfg["cost_bps"])
    else:
        print("[2/5] Walk-forward núcleo v1 (long-only breakout, treino 4a -> teste 1a cego)...")
        wf = walk_forward(
            df,
            ensembles=ecfg["ensembles"],
            kind=ecfg["kind"],
            train_days=wcfg["train_days"],
            test_days=wcfg["test_days"],
            ma_window=ecfg["ma_window"],
            cost_bps=ecfg["cost_bps"],
        )

    print("[3/5] Resultado out-of-sample:\n")
    print(format_console_summary(wf, asset=asset))

    print("\n[4/5] Sinal atual do sistema (última barra real):")
    # usa a config escolhida na última janela de treino (a mais recente)
    last_cfg = wf.steps[-1].lookbacks
    sig = current_signal(df, last_cfg, kind=ecfg["kind"], ma_window=ecfg["ma_window"])
    print(f"      {sig.date.date()} | preço ${sig.price:,.0f}")
    print(f"      ensemble {last_cfg}: voto {sig.ensemble_vote*100:.0f}% comprado")
    print(f"      regime: {'BULL (libera)' if sig.regime_bull else 'BEAR (veta)'} "
          f"(MA200 ${sig.ma_value:,.0f})")
    print(f"      >>> posição recomendada: {sig.recommended_weight*100:.0f}% | {sig.reading}")

    print("\n[5/5] Gerando relatório HTML...")
    out = build_report(wf, df["Close"], REPORT_PATH, asset=asset, ma_window=ecfg["ma_window"])
    print(f"      relatório: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
