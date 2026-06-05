# Cockpit interativo (app multi-ativo)

**Data:** 2026-06-05 · **Stack:** Streamlit + Plotly · **Rodar:**
`./.venv/bin/streamlit run app/cockpit_app.py` → http://localhost:8501

Evolução do painel estático (`reports/dashboard.html`) para um **app interativo**: trocar de
ativo, ver o sistema no gráfico e os parâmetros OOS reais por ativo. Decisão de stack:
**Streamlit** (single-user, reusa 100% do engine Python, ~¼ do código vs FastAPI+JS; o
walkforward por ativo roda em ~1,7–5s, resolvido com `st.cache_data`).

## Arquitetura (2 camadas)

- **`trendfit/cockpit.py` — data layer PURO** (zero dependência de front-end). `asset_cockpit(name)`
  agrega, por ativo: série + MA200 + RSI + valuation, sinais (entrar/sair/HOJE via transições do
  peso), regime, postura (Buffett Jr), critérios e **walkforward OOS** (params reais, escolhidos só
  no treino). `environment_now()` e `polymarket_now()` dão o contexto global. Reusável por qualquer
  front-end (FastAPI amanhã) sem alteração.
- **`app/cockpit_app.py` — casca Streamlit.** Só apresentação: seletor de ativo, gráfico Plotly
  (preço + MA200 + trades + HOJE + RSI + MVRV), KPIs, postura/cenários, métricas do walkforward +
  curva de capital, ambiente macro e termômetro Polymarket no topo.

## Ativos (Fase 1)

`BTC`, `ETH` (OHLCV real via CCXT, MVRV no BTC), `Ouro`, `SP500` (close-only → OHLC sintético,
dias úteis, desde 2000 — aproximação rotulada). Cada um: gráfico + sinais + postura + walkforward.

## Faseamento (acordado com o dono)

1. **Fase 1 (feita):** cockpit multi-ativo — trocar ativo, sistema no gráfico, indicador por ativo,
   postura, walkforward OOS por ativo.
2. **Fase 2:** botão de re-rodar walkforward ao vivo / ajustar parâmetros e ver o efeito.
3. **Fase 3:** carteira + caixa + gráfico de patrimônio + postura do Buffett Jr sobre a carteira
   (dados financeiros reais). **Linha vermelha:** o Buffett lê/classifica/dá postura — a decisão de
   comprar/vender é sempre do dono; nunca vira ordem nem previsão.

## Linha vermelha (inalterada)

Timing (regime) é validado OOS e MANDA no comprado/fora. Postura, macro e Polymarket INFORMAM —
nunca acionam ordem. O cockpit não prevê preço nem dá recomendação de investimento.
