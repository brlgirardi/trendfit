# Frontend — Arquitetura React + FastAPI

Documentação da camada de apresentação do cockpit TrendFit. Cobre a stack
React + FastAPI que substitui o dashboard Streamlit, como rodar tudo
localmente e como estender o sistema sem tocar no motor de sinais.

## 1. Visão geral — por que saímos do Streamlit

O cockpit nasceu em Streamlit (`app/cockpit_app.py`) e ele continua funcional
e mantido como legado. A migração para React + FastAPI aconteceu por três
motivos concretos:

- **Interatividade.** Streamlit re-renderiza a página inteira a cada clique no
  seletor de ativo. Com React, trocar de BTC para ETH só re-renderiza o gráfico
  e os badges — o resto do layout fica intacto.
- **Performance do gráfico.** O candlestick agora usa `lightweight-charts`
  (TradingView), que desenha milhares de candles em canvas. O Plotly do
  Streamlit engasgava com o histórico completo dos 6 ativos.
- **Separação de responsabilidades.** O Python vira API pura (`/api/...`),
  o React vira cliente puro. O motor de sinais (`trendfit.cockpit`) é importado
  só pela API; o frontend nunca fala com SQLite nem com `ccxt` direto.

Regra: **Python calcula, React desenha.** Toda lógica de sinal mora em
`trendfit.cockpit`; o React só consome JSON.

## 2. Arquitetura

```
  ┌──────────────────────────┐
  │  trendfit.cockpit        │   motor de sinais (k=3, walk-forward, MVRV)
  │  app/cockpit_app.py      │   ── importado pela API, não exposto à web
  └────────────┬─────────────┘
               │ import (list_assets, asset_cockpit, environment_now)
               ▼
  ┌──────────────────────────┐
  │  FastAPI  app/api/main   │   porta 8502
  │  /api/health             │   serializa cockpit → JSON
  │  /api/assets             │
  │  /api/data/{asset}       │
  │  /api/macro              │
  └────────────┬─────────────┘
               │ HTTP JSON  (Vite proxy: /api → localhost:8502)
               ▼
  ┌──────────────────────────┐
  │  React + Vite            │   porta 3000
  │  app/frontend/src        │   lightweight-charts + Tailwind
  │  AssetSelector           │
  │  SystemSelector          │
  │  MainChart / MacroPanel  │
  │  PostureBadge / Leverage │
  └──────────────────────────┘
```

O Streamlit legado (`app/cockpit_app.py`, porta 8501) roda em paralelo,
consumindo o mesmo `trendfit.cockpit`. As duas frentes compartilham o motor,
nunca duplicam a lógica de sinal.

## 3. Como rodar localmente

São três processos independentes. Backend e frontend juntos cobrem o cockpit
novo; o Streamlit é opcional, só se você precisar do legado.

**Backend (FastAPI, porta 8502):**
```
uvicorn app.api.main:app --port 8502 --reload
```

**Frontend (React + Vite, porta 3000):**
```
cd app/frontend && npm install && npm run dev
```

**Streamlit legado (porta 8501):**
```
streamlit run app/cockpit_app.py --server.port 8501
```

Abra `http://localhost:3000`. O Vite faz proxy de `/api` para
`http://localhost:8502` (`app/frontend/vite.config.ts`), então o frontend
chama caminhos relativos (`/api/data/BTC`) sem precisar de CORS em dev.

## 4. Endpoints da API

Base: `http://localhost:8502`. Todos retornam JSON.
Definidos em `app/api/main.py`, serialização em `app/api/serializers.py`.

| Path                  | Método | Descrição                                              |
|-----------------------|--------|--------------------------------------------------------|
| `/api/health`         | GET    | Health check. `{ "status": "ok" }`                     |
| `/api/assets`         | GET    | Lista de ativos válidos (array de strings)             |
| `/api/data/{asset}`   | GET    | Dados completos: OHLCV, sinais, postura, walk-forward  |
| `/api/macro`          | GET    | Séries macro: FNG, VIX, DXY, US10Y, MVRV BTC/ETH, funding |

`{asset}` é validado contra `list_assets()`; valor inválido retorna `404` com a
lista de ativos aceitos.

**Exemplo — `GET /api/assets`:**
```json
["BTC", "ETH", "Ouro", "SP500", "QQQ", "SOXX"]
```

**Exemplo — `GET /api/data/BTC` (encurtado):**
```json
{
  "asset": "BTC",
  "ohlcv": [
    { "time": 1718841600, "open": 64500.0, "high": 65200.0,
      "low": 63900.0, "close": 64980.0, "volume": 0.0 }
  ],
  "signals": [
    { "time": 1718841600, "regime": "BULL", "trailing_stop": 61200.0,
      "in_position": true, "fraction": 1.0 }
  ],
  "posture": { "label": "ACUMULAR", "action": "...", "environment": "FAVORÁVEL", "color": "#16a34a" },
  "walkforward": { "oos_return": 1.57, "sharpe": 0.95, "max_dd": -0.22, "cagr": 0.38, "period": "2022-01-01 → 2026-06-01" }
}
```

`time` é epoch em segundos (UTC), pronto para `lightweight-charts`.

## 5. Design system

Tema dark, definido em `app/frontend/tailwind.config.ts` e
`app/frontend/src/styles/globals.css`. Use sempre os tokens do Tailwind, nunca
hex solto nos componentes.

| Token            | Hex       | Uso                                  |
|------------------|-----------|--------------------------------------|
| `bg-primary`     | `#0D0D0D` | Fundo da página                      |
| `bg-panel`       | `#1A1A1A` | Cards, seletores, painéis            |
| `border-line`    | `#2A2A2A` | Bordas e divisórias                  |
| `bull`           | `#00FF88` | Regime BULL, postura positiva        |
| `bear`           | `#FF3B3B` | Regime BEAR, alerta                  |
| `neutral`        | `#FFB800` | Estado neutro / cautela              |
| `very-bad`       | `#FF0000` | Pior nível de risco                  |
| `text-primary`   | `#E8E8E8` | Texto principal                      |
| `text-secondary` | `#888888` | Texto de apoio, labels inativos      |

Tipografia: **Inter** (UI) + **JetBrains Mono** (números, tickers).

Cores de postura (geradas pelo backend em `serializers.serialize_posture`):
`ACUMULAR #16a34a` · `NEUTRO #3b82f6` · `CAUTELOSO #f59e0b` · `DEFENSIVO #ef4444`

## 6. Como adicionar um novo ativo

Um ativo precisa atravessar as três camadas, nesta ordem:

**(a) Motor — `trendfit/cockpit.py`.** Registre em `ASSETS` e garanta que o
pipeline de dados sabe buscar o OHLCV. Depois de registrado, `list_assets()`
já o inclui — o motor k=3 roda automático, sem código novo de estratégia.

**(b) API — nada a fazer.** `/api/data/{asset}` é genérico: valida contra
`list_assets()` e serializa qualquer ativo registrado no passo (a).

**(c) Frontend — `app/frontend/src/components/Controls/AssetSelector.tsx`.**
Acrescente o ticker ao array `ASSETS`. Os hooks e o `MainChart` já consomem
`/api/data/{asset}` de forma genérica — não há componente específico por ativo.

## 7. Seletor de trade system (plugar Glassnode)

`SystemSelector.tsx` já prevê múltiplos sistemas. Hoje lista dois:

- **TrendFit** → ativo
- **Glassnode** → desabilitado ("coming soon")

Para habilitar Glassnode:
1. Ingerir métricas Glassnode no pipeline (`trendfit.cockpit`), com API key em `.env`.
2. Expor via `/api/data/{asset}?system=glassnode` (mesmo shape JSON do TrendFit).
3. Remover `disabled` em `SystemSelector.tsx` e propagar `activeSystem` nos hooks.

Não mock dados de sistema externo — botão cinza é melhor que sinal falso.

## 8. Regras inegociáveis

- **Motor k=3 é INTOCÁVEL.** `trendfit/engine/` e a lógica de `trendfit.cockpit`
  não se alteram para acomodar frontend ou API. Frontend e API só **leem** a saída.
- **`.env` nunca é commitado.** API keys ficam em `.env` local, fora do git.
- **Commits:** Bruno Liberato Girardi, zero footer de IA.
- **`db/` e `reports/` são gitignored.** Nunca `git add -A`.
