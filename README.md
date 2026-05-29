# TrendFit

Sistema de trading multi-ativo por confluência, com backtesting local e
**walk-forward multi-ciclo**. O núcleo é uma regra robusta de tendência
(ensemble Donchian/HiLo multi-lookback); a IA entra como **filtro de contexto e
veto** — nunca como gerador de sinal.

> **Custo de stack: $0.** Só libs e APIs gratuitas (ccxt, yfinance, pandas, numpy, plotly, sqlite).
>
> **Status:** Sprint 1 concluída — núcleo BTC validado com dados reais. Ver [`docs/VERDICT.md`](docs/VERDICT.md).

---

## Princípio central (anti-overfitting)

O backtest reconstruído provou que **otimizar parâmetros ingenuamente causa
overfitting** (params "perfeitos" no passado deram +3.775% in-sample → só +5%
out-of-sample). A arquitetura inteira é desenhada para resistir a isso:

```
NÚCLEO: ensemble trend-following
  → Donchian/HiLo multi-lookback (ex: 10/20/30)
  → posição fracionária = fração dos lookbacks que concordam (0..1)
        +
VETO DE REGIME (filtro de contexto)
  → v1: preço vs MA200 (bull/bear macro)      [implementado]
  → v2: + MVRV, fluxo de ETF, drawdown de ciclo
  → v3: + NLP de notícias/sentimento
        ↓
SELEÇÃO walk-forward por RETORNO/RISCO (não por lucro máximo)
  → treino 4 anos → teste 1 ano cego → roda pra frente
```

Cada peça reduz graus de liberdade: ensemble em vez de parâmetro único, poucos
lookbacks fixos (sem grid-search fino), veto que tira o sistema do mercado em
regime bear, e seleção por retorno/risco que evita pegar pico de ruído.

---

## Instalação

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Uso (Sprint 1 — BTC)

```bash
python scripts/run_btc_sprint1.py
```

Esse comando:
1. Coleta OHLCV diário **real** de BTC via CCXT (Binance, com fallback) → cache SQLite (`db/`).
2. Roda o walk-forward multi-ciclo (treino 4a → teste 1a cego).
3. Imprime as métricas OOS vs Buy & Hold e o sinal atual.
4. Gera o relatório HTML interativo em `reports/btc_walkforward.html`.

Re-rodar é barato: o coletor é idempotente e só baixa candles novos.

## Testes

```bash
pytest --cov=trendfit
```

---

## Estrutura

```
trendfit/
├── data/        coleta (CCXT/yfinance) + cache SQLite idempotente
├── engine/      indicadores, ensemble, backtest vetorizado, walk-forward, sinal
├── layers/      camadas de confluência (Sprint 1: veto de regime v1 / MA200)
├── report/      relatório HTML (Plotly) + resumo de console
├── profiles/    1 perfil JSON por ativo (params oscilam por ativo)
└── radar/       screener multi-ativo (Fases 4-5, ver docs/PRD_FUTURE_RADAR.md)

scripts/         runners (run_btc_sprint1.py)
tests/           suíte pytest (engine ~99% coberto)
docs/            PRD, plano de sprint, veredito, PRD futuro do Radar
reference/       provas de conceito (lógica validada — não é código de produção)
db/ reports/     cache e saídas (regeneráveis; fora do git)
```

---

## Roadmap

- [x] **Sprint 1** — núcleo ensemble + veto v1 + walk-forward BTC com dados reais
- [ ] **Fase 2** — camadas externas: FRED (macro) + on-chain + sentimento → cache
- [ ] **Fase 3** — veto IA v2/v3: regime classifier (MVRV+ETF+macro) → NLP de notícias
- [ ] **Fase 4** — multi-ativo: perfis stocks/commodities/metais + validação cruzada
- [ ] **Fase 5** — Radar de oportunidades (quadrantes macro) — ver [`docs/PRD_FUTURE_RADAR.md`](docs/PRD_FUTURE_RADAR.md)
- [ ] **Fase 6** — dashboard (estilo TradingView) + paper trading

---

## Aviso

Ferramenta de pesquisa e backtesting. As saídas são resultados mecânicos do
sistema, **não recomendação de investimento**. Resultados passados (mesmo
out-of-sample) não garantem retornos futuros.
