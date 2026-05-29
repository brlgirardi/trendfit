# Sprint 1 — Núcleo + dados reais BTC

**Objetivo (JTBD):** validar, com dados reais, se a arquitetura ensemble + veto
de regime se sustenta out-of-sample contra Buy & Hold no BTC.

## Entregáveis e status

| # | Entregável | Status | Onde |
|---|---|---|---|
| 1.1 | Repo + estrutura + README + requirements | ✅ | raiz, `trendfit/`, `README.md` |
| 1.2 | Coletor CCXT + cache SQLite idempotente | ✅ | `trendfit/data/` |
| 1.3 | Núcleo ensemble Donchian multi-lookback (posição fracionária) | ✅ | `trendfit/engine/ensemble.py` |
| 1.4 | Veto de regime v1 (preço vs MA200) | ✅ | `trendfit/layers/regime.py` |
| 1.5 | Engine walk-forward (treino 4a → teste 1a cego; seleção retorno/risco) | ✅ | `trendfit/engine/walkforward.py` |
| 1.6 | Relatório: equity curve + métricas OOS vs B&H | ✅ | `trendfit/report/`, `reports/btc_walkforward.html` |
| 1.7 | Veredito registrado | ✅ | [`VERDICT.md`](VERDICT.md) |

## Disciplina anti-overfitting aplicada

- Lookbacks **fixos** por design (1 "knob" diversificado por candidato); **sem grid-search fino**.
- Seleção por **retorno/risco** (retorno ÷ |drawdown|), não por lucro máximo.
- **Sem look-ahead**: canais com `shift(1)`; o peso decidido no dia *i* só captura
  o retorno de *i→i+1* (testado em `tests/test_backtest.py`).
- Walk-forward multi-ciclo como único teste de verdade.

## Qualidade

- Suíte pytest: **22 testes**, cobertura **90%** (engine ~99-100%).
- Build/run end-to-end com dados reais: OK.

## Resultado (resumo)

Sistema +106,1% vs Buy & Hold +157,7% OOS — **B&H venceu em retorno**, mas o
sistema entregou **metade do drawdown** (−28,9% vs −76,6%) e Sharpe equivalente
com ~48% de exposição. A tese de **proteção de risco** do PRD se confirmou; a
magnitude "+51% sobre B&H" do backtest reconstruído **não** se confirmou (era
artefato dos dados sintéticos). Detalhes e decisão em [`VERDICT.md`](VERDICT.md).

## Fora de escopo (fases futuras)

Camadas on-chain/macro/sentimento (Fase 2), veto IA v2/v3 com NLP (Fase 3),
multi-ativo + perfis (Fase 4), Radar macro (Fase 5, ver
[`PRD_FUTURE_RADAR.md`](PRD_FUTURE_RADAR.md)), dashboard (Fase 6).
