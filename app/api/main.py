"""API REST (FastAPI) que expõe trendfit.cockpit — camada fina sobre a data layer pura.

Endpoints:
  GET /api/health        -> {"status": "ok"}
  GET /api/assets        -> ["BTC","ETH","Ouro","SP500","QQQ","SOXX"]
  GET /api/data/{asset}  -> {ohlcv, signals, posture, walkforward}  (calculado sob demanda)
  GET /api/macro         -> séries macro {fng, vix, dxy, us10y, mvrv_btc, mvrv_eth, funding}

A API NÃO cacheia na inicialização: asset_cockpit() roda o walk-forward honesto (~2s/ativo)
só quando o endpoint é chamado. Nenhuma decisão nova aqui — só orquestra cockpit + serializers.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from trendfit.cockpit import asset_cockpit, environment_now, list_assets, market_cone
from trendfit.data.external import load_series

from app.api import serializers
from app.api.buffett import router as buffett_router

logger = logging.getLogger(__name__)

# DB sobreescrevível por env (TRENDFIT_DB). Default = mesmo arquivo que o cockpit usa.
DB_PATH = Path(os.getenv("TRENDFIT_DB", "db/trendfit.sqlite"))

app = FastAPI(title="TrendFit API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chat do Buffett Jr (POST /api/buffett/chat, sessoes, historico). Agente lazy.
app.include_router(buffett_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/assets")
def assets() -> list[str]:
    return list_assets()


@app.get("/api/data/{asset}")
def data(asset: str) -> dict:
    """Pacote completo de UM ativo (sob demanda). Valida o nome, roda o cockpit com
    walk-forward honesto e serializa para o contrato da API."""
    valid = list_assets()
    if asset not in valid:
        raise HTTPException(
            status_code=404,
            detail={"error": f"ativo desconhecido: {asset!r}", "valid_assets": valid},
        )

    try:
        env_now = environment_now()
    except Exception:  # noqa: BLE001 — ambiente é contexto; sem ele a postura cai p/ ""
        logger.warning("environment_now() falhou; postura sem ambiente macro", exc_info=True)
        env_now = {"ctx": {}, "env": {}}

    ctx = env_now.get("ctx") or {}
    env = env_now.get("env") or {}

    cockpit_data = asset_cockpit(asset, ctx=ctx, env=env, with_walkforward=True)

    return {
        "asset": asset,
        "name": cockpit_data.get("name", asset),
        "asof": cockpit_data.get("asof"),
        "price": cockpit_data.get("price"),
        "regime": cockpit_data.get("regime"),
        "ohlcv": serializers.serialize_ohlcv(cockpit_data),
        "signals": serializers.serialize_signals(cockpit_data),
        "posture": serializers.serialize_posture(cockpit_data, env=env),
        "valuation": serializers.serialize_valuation(cockpit_data),
        "walkforward": serializers.serialize_walkforward(cockpit_data),
    }


@app.get("/api/cone/{asset}")
def cone(asset: str) -> dict:
    """Cone do MERCADO DE APOSTAS (Kalshi + Polymarket) p/ UM ativo.

    LINHA VERMELHA: é ESPELHO DA MULTIDÃO, não sinal do sistema. Estes números
    NUNCA entram no motor (strategy/signal/walkforward), não acionam trade, não
    modulam exposição — só mostram o que dois mercados de aposta independentes
    precificam para o mesmo horizonte. A UI deve deixar isso explícito.

    Degrada gracioso: rede pode cair (Kalshi/Polymarket externos). Nesse caso
    devolve {points:[], sources:[], end:null, available:false} — nunca 500.
    """
    valid = list_assets()
    if asset not in valid:
        raise HTTPException(
            status_code=404,
            detail={"error": f"ativo desconhecido: {asset!r}", "valid_assets": valid},
        )

    try:
        result = market_cone(asset)
    except Exception:  # noqa: BLE001 — cone é display-only; rede externa pode falhar
        logger.warning("market_cone(%s) falhou; cone indisponível", asset, exc_info=True)
        result = None

    if not result or not result.get("points"):
        return {"asset": asset, "points": [], "sources": [], "end": None, "available": False}

    points = [
        {
            "dir": p.get("dir"),
            "target": p.get("target"),
            "prob": p.get("prob"),
            "source": p.get("source"),
            "oi": p.get("oi"),
        }
        for p in result.get("points", [])
    ]
    return {
        "asset": asset,
        "points": points,
        "sources": result.get("sources", []),
        "end": result.get("end"),
        "available": True,
    }


@app.get("/api/macro")
def macro() -> dict:
    """Séries macro temporais para os subplots de contexto. Cada série degrada para []
    se vazia/ausente (load_series devolve Series vazia). 'mvrv_btc' lê a série 'mvrv'."""
    macro_series = {
        field: load_series(DB_PATH, series_name)
        for field, series_name in serializers.MACRO_SERIES.items()
    }
    return serializers.serialize_macro(macro_series)
