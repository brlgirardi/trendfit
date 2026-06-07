"""Data layer do COCKPIT multi-ativo (Fase 1) — 100% Python puro, ZERO dependência de
front-end (sem `streamlit`/`flask`). Agrega, por ativo, tudo que a casca precisa para
desenhar: série + regime + sinais (entrar/sair/hoje) + indicador + postura + walkforward.

Reusa o engine validado (walk_forward_grid, target_weights, current_signal) e as camadas
de leitura (allocation: asset_view/asset_posture/environment_read; polymarket). NÃO decide
nada novo — só consome e organiza. Qualquer front-end (Streamlit hoje, FastAPI amanhã)
pode usar estas funções sem alteração.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from trendfit.allocation import (
    asset_posture,
    asset_view,
    environment_read,
)
from trendfit.data import OHLCVCache, fetch_ohlcv_daily
from trendfit.data.external import load_series
from trendfit.data.kalshi import fetch_price_cone
from trendfit.data.polymarket import fetch_btc_price_distribution, fifty_fifty_level, nearest_prob
from trendfit.engine.signal import current_signal
from trendfit.engine.strategy import StrategyConfig, target_weights
from trendfit.engine.walkforward import walk_forward_grid, walk_forward_strategy

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "trendfit.sqlite"
PROFILE = ROOT / "profiles" / "btc.json"

# Registro de ativos do cockpit. kind=ohlcv (cripto, OHLCV real) | series (close-only ->
# OHLC sintético, dias úteis — aproximação rotulada, ver docs/PHASE4.md). valuation = série
# de valuation real (só BTC tem MVRV); os demais caem no percentil de preço (proxy).
ASSETS: dict[str, dict] = {
    "BTC": {"kind": "ohlcv", "symbol": "BTC", "valuation": "mvrv", "class": "crypto",
            "exchanges": [("binance", "BTC/USDT"), ("kraken", "BTC/USD"),
                          ("coinbase", "BTC/USD"), ("bitstamp", "BTC/USD")]},
    "ETH": {"kind": "ohlcv", "symbol": "ETH", "valuation": None, "class": "crypto",
            "exchanges": [("binance", "ETH/USDT"), ("kraken", "ETH/USD"), ("coinbase", "ETH/USD")]},
    "Ouro": {"kind": "series", "series": "gold", "valuation": None, "class": "commodity"},
    "SP500": {"kind": "series", "series": "spx", "valuation": "cape", "class": "equity"},
}

START = "2023-06-01"  # janela visível no gráfico (o walkforward usa todo o histórico)


def list_assets() -> list[str]:
    return list(ASSETS.keys())


def load_profile() -> dict:
    return json.loads(PROFILE.read_text())


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def load_asset_df(name: str) -> pd.DataFrame:
    """OHLCV diário do ativo. Cripto = real (CCXT). series = close-only -> OHLC sintético."""
    a = ASSETS[name]
    if a["kind"] == "ohlcv":
        with OHLCVCache(DB) as c:
            df = fetch_ohlcv_daily(c, cache_symbol=a["symbol"], timeframe="1d", exchanges=a["exchanges"])
        return df[~df.index.duplicated(keep="last")].sort_index()
    s = load_series(DB, a["series"]).dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s[s.index >= "2000-01-01"]  # histórico relevante (1933 não informa hoje; acelera o walkforward)
    return pd.DataFrame({"Open": s, "High": s, "Low": s, "Close": s, "Volume": 0.0})


def _candidates(e: dict, g: dict) -> list[tuple]:
    out = []
    for ln, lbs in e["ensembles"].items():
        for asym in g["asym"]:
            for band, atrk in g["variants"]:
                out.append((f"{ln}|a{asym}|b{band}|k{atrk}", lbs,
                            StrategyConfig(ma_window=e["ma_window"], band=band,
                                           mode="long_asym", asym=asym, atr_k=atrk)))
    return out


def _cfg_from_name(nm: str, ma: int) -> StrategyConfig:
    return StrategyConfig(ma_window=ma, band=float(nm.split("|b")[1].split("|")[0]),
                          mode="long_asym", asym=float(nm.split("|a")[1].split("|")[0]),
                          atr_k=float(nm.split("|k")[1]))


def _trades_from_weights(w: pd.Series, price: pd.Series) -> list[dict]:
    """Pares entrada->saída a partir das transições do peso (0 -> >0 abre; >0 -> 0 fecha)."""
    wv = w.to_numpy()
    idx = w.index
    trades, entry_i = [], None
    for i in range(1, len(wv)):
        if wv[i] > 0 and wv[i - 1] <= 0:
            entry_i = i
        elif wv[i] <= 0 and wv[i - 1] > 0 and entry_i is not None:
            e_px, x_px = float(price.iloc[entry_i]), float(price.iloc[i])
            trades.append({"entry_date": idx[entry_i], "exit_date": idx[i],
                           "entry_px": e_px, "exit_px": x_px, "ret": x_px / e_px - 1})
            entry_i = None
    if entry_i is not None:  # trade ainda aberto
        e_px = float(price.iloc[entry_i])
        trades.append({"entry_date": idx[entry_i], "exit_date": None,
                       "entry_px": e_px, "exit_px": float(price.iloc[-1]),
                       "ret": float(price.iloc[-1]) / e_px - 1, "open": True})
    return trades


def environment_now() -> dict:
    """Leitura macro global (ambiente FAVORÁVEL/MISTO/ADVERSO) — não previsão."""
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
    return {"ctx": ctx, "env": environment_read(ctx)}


def polymarket_now() -> dict | None:
    """Termômetro do mercado de apostas (Polymarket) — contexto, NÃO sinal."""
    dist = fetch_btc_price_distribution()
    if not dist:
        return None
    floor = fifty_fifty_level(dist.get("down", []))
    return {"dist": dist, "floor_5050": floor}


def asset_cockpit(name: str, ctx: dict | None = None, env: dict | None = None,
                  with_walkforward: bool = True) -> dict:
    """Pacote completo de UM ativo para o cockpit. with_walkforward roda o walk-forward
    honesto (params OOS reais, ~1,7s) — é o que dá a config viva dos sinais e as métricas."""
    prof = load_profile()
    e, w, g = prof["engine"], prof["walkforward"], prof["grid"]
    a = ASSETS[name]
    df = load_asset_df(name)
    price = df["Close"]
    ma = e["ma_window"]

    # valuation real por ativo (BTC=MVRV on-chain, SP500=CAPE/Shiller); os demais caem no
    # percentil de preço (proxy) dentro do asset_view. val_overlay = (nome, referência, série)
    # para o subplot de contexto no gráfico. Tudo CONTEXTO — nunca aciona (PHASE5).
    val_pct, val_label, val_overlay = None, "", None
    val_kind = a.get("valuation")
    if val_kind == "mvrv":
        mv = load_series(DB, "mvrv")
        if not mv.empty:
            val_pct = float((mv < mv.iloc[-1]).mean() * 100)
            val_label = f"MVRV {mv.iloc[-1]:.2f}"
            val_overlay = ("MVRV", 1.0, mv.reindex(price.index).ffill())
    elif val_kind == "cape":
        cp = load_series(DB, "cape")
        if not cp.empty:
            val_pct = float((cp < cp.iloc[-1]).mean() * 100)
            val_label = f"CAPE {cp.iloc[-1]:.0f}"
            val_overlay = ("CAPE", float(cp.median()), cp.reindex(price.index).ffill())

    view = asset_view(name, price, valuation_pct=val_pct, valuation_label=val_label)
    cax = {"fng": (ctx or {}).get("fng"),
           "funding": (ctx or {}).get("funding") if a["class"] == "crypto" else None}
    posture = asset_posture(view, cax, env)

    out: dict = {
        "name": name, "class": a["class"], "kind": a["kind"],
        "price": float(price.iloc[-1]), "asof": price.index[-1].date().isoformat(),
        "regime": view["regime"], "dist_ma": view["dist_ma"], "val_pct": view["val_pct"],
        "val_label": view.get("val_label", ""), "view": view, "posture": posture,
        "has_history": len(df) >= (w["train_days"] + w["test_days"] + 30),
    }

    # série recente para o gráfico (preço + MA200 + RSI + valuation)
    pr = price.loc[START:]
    ma200 = price.rolling(ma).mean().loc[START:]
    rsi = _rsi(price).loc[START:]
    has_ohlc = a["kind"] == "ohlcv"
    out["series"] = {
        "date": [d.date().isoformat() for d in pr.index],
        "price": [float(x) for x in pr.to_numpy()],
        "ma200": [None if np.isnan(x) else float(x) for x in ma200.to_numpy()],
        "rsi": [None if np.isnan(x) else float(x) for x in rsi.to_numpy()],
        "val_overlay": ({"name": val_overlay[0], "ref": val_overlay[1],
                         "values": [None if pd.isna(x) else float(x)
                                    for x in val_overlay[2].loc[START:].to_numpy()]}
                        if val_overlay is not None else None),
        "high_low": has_ohlc,
    }
    # OHLC para candles (só ativos com OHLC real; sintéticos seguem como linha). Reindexa
    # ao MESMO índice da série de preço para o candlestick não quebrar por desalinho.
    if has_ohlc:
        out["series"]["open"] = [float(x) for x in df["Open"].reindex(pr.index).to_numpy()]
        out["series"]["high"] = [float(x) for x in df["High"].reindex(pr.index).to_numpy()]
        out["series"]["low"] = [float(x) for x in df["Low"].reindex(pr.index).to_numpy()]

    if with_walkforward and out["has_history"]:
        cands = _candidates(e, g)
        wf = walk_forward_grid(df, cands, train_days=w["train_days"], test_days=w["test_days"],
                               cost_bps=e["cost_bps"])
        m, bh = wf.oos_metrics, wf.benchmark
        p0, p1 = wf.oos_period
        last = wf.steps[-1]
        cfg = _cfg_from_name(last.chosen, ma)
        w_live = pd.Series(target_weights(df, last.lookbacks, cfg), index=df.index)
        sig = current_signal(df, last.lookbacks, kind=e["kind"], ma_window=ma)
        eq = wf.oos_equity
        out["signal"] = {"fora": bool(sig.recommended_weight <= 0),
                         "weight": float(sig.recommended_weight),
                         "regime_bull": bool(sig.regime_bull),
                         "ma_value": float(sig.ma_value), "price": float(sig.price)}
        out["trades"] = [
            {**t, "entry_date": t["entry_date"].date().isoformat(),
             "exit_date": t["exit_date"].date().isoformat() if t.get("exit_date") is not None else None}
            for t in _trades_from_weights(w_live.loc[START:], price.loc[START:])
        ]
        out["wf"] = {
            "ret": m["total_return"], "dd": m["max_drawdown"], "sharpe": m["sharpe"],
            "cagr": m["cagr"], "calmar": (m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0),
            "bh_ret": bh.total_return, "bh_dd": bh.summary()["max_drawdown"],
            "params": last.chosen, "lookbacks": last.lookbacks,
            "period": f"{p0.date()} → {p1.date()}",
            "equity": {"date": [d.date().isoformat() for d in eq.index],
                       "val": [float(x) for x in eq.to_numpy()]},
        }
    else:
        out["signal"], out["trades"], out["wf"] = None, [], None
    return out


def lab_walkforward(name: str, asym: float = 1.0, band: float = 0.05, atr_k: float = 3.0,
                    ratchet_gain: float = 0.0, ratchet_k: float = 0.0) -> dict:
    """LABORATÓRIO (exploratório, NÃO honesto): roda walk_forward_strategy com os params
    FIXOS escolhidos pelo usuário (os lookbacks ainda são escolhidos no treino). Serve para
    VER o efeito dos parâmetros — mas escolher params olhando ESTE OOS é overfit. O número
    honesto é o grid (asset_cockpit['wf']), que escolhe TODOS os params só no treino."""
    prof = load_profile()
    e, w = prof["engine"], prof["walkforward"]
    df = load_asset_df(name)
    cfg = StrategyConfig(ma_window=e["ma_window"], band=band, mode="long_asym", asym=asym,
                         atr_k=atr_k, ratchet_gain=ratchet_gain, ratchet_k=ratchet_k)
    wf = walk_forward_strategy(df, cfg, e["ensembles"], train_days=w["train_days"],
                               test_days=w["test_days"], cost_bps=e["cost_bps"])
    m, bh = wf.oos_metrics, wf.benchmark
    p0, p1 = wf.oos_period
    eq = wf.oos_equity
    ratchet = f"|R{ratchet_gain:.0%}/{ratchet_k:.0f}" if ratchet_gain and ratchet_k else ""
    return {
        "ret": m["total_return"], "dd": m["max_drawdown"], "sharpe": m["sharpe"],
        "calmar": (m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else 0.0),
        "bh_ret": bh.total_return, "period": f"{p0.date()} → {p1.date()}",
        "params": f"asym{asym}|b{band}|k{atr_k}{ratchet}",
        "equity": {"date": [d.date().isoformat() for d in eq.index],
                   "val": [float(x) for x in eq.to_numpy()]},
    }


def market_cone(asset: str) -> dict | None:
    """Cone do MERCADO DE APOSTAS p/ plotar À FRENTE de hoje (Kalshi + Polymarket).

    ──────────────────────────────────────────────────────────────────────────────
    NEVER USED BY ENGINE — é ESPELHO da multidão, não sinal. Estes números não entram
    em strategy/signal/walkforward, não acionam, não modulam exposição. O TrendFit não
    prevê; aqui só mostramos o que DOIS mercados de aposta independentes precificam para
    o mesmo horizonte (até a resolução, fim de 2026). One-touch: "tocar X", não "fechar
    em X". As fontes ficam LADO A LADO (sem média/blend) — a divergência é informação.
    ──────────────────────────────────────────────────────────────────────────────

    Retorna {points:[{target,prob,dir,source,oi}], end, sources} ou None se nada
    disponível. Degrada gracioso: cada fonte some sozinha se cair (try/except interno)."""
    points: list[dict] = []
    sources: list[str] = []
    ends: list[str] = []

    k = fetch_price_cone(asset)  # Kalshi: BTC/ETH; demais → None
    if k:
        for tgt, prob, oi in k.get("up", []):
            points.append({"target": float(tgt), "prob": float(prob), "dir": "up",
                           "source": "kalshi", "oi": float(oi)})
        for tgt, prob, oi in k.get("down", []):
            points.append({"target": float(tgt), "prob": float(prob), "dir": "down",
                           "source": "kalshi", "oi": float(oi)})
        if k.get("end"):
            ends.append(k["end"])
        if k.get("up") or k.get("down"):
            sources.append("kalshi")

    if asset == "BTC":  # Polymarket: só o mercado anual de BTC (o mais líquido)
        pm = fetch_btc_price_distribution()
        if pm:
            for tgt, prob in pm.get("up", []):
                points.append({"target": float(tgt), "prob": float(prob), "dir": "up",
                               "source": "polymarket", "oi": None})
            for tgt, prob in pm.get("down", []):
                points.append({"target": float(tgt), "prob": float(prob), "dir": "down",
                               "source": "polymarket", "oi": None})
            if pm.get("end"):
                ends.append(pm["end"])
            if pm.get("up") or pm.get("down"):
                sources.append("polymarket")

    if not points:
        return None
    return {"points": points, "end": max(ends) if ends else None, "sources": sources}


def nearest_market_prob(dist: dict, level: float) -> tuple[int, float] | None:
    """Atalho p/ a casca: prob. implícita do nível mais próximo (Polymarket)."""
    pts = (dist.get("up", []) + dist.get("down", [])) if dist else []
    return nearest_prob(pts, level)
