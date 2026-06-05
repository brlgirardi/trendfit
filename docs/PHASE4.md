# Fase 4 — Sistema v3.1 multi-ativo (BTC, ETH, SP500)

**Data:** 2026-06-05
**Pergunta (do dono):** o sistema deveria seguir na mesma linha em ETH e SP500?
**Veredito:** **funciona em cripto (BTC, ETH); em ações (SP500) a proposta é mais fraca.**

Mesmo motor (ensemble Donchian + regime MA200 + trailing ATR k=3), mesmo walk-forward
honesto (params só no treino). `scripts/validate_multiasset.py`. Lido de arquivo.

## Resultado

| Ativo | período OOS | Sistema | B&H | sysDD | bhDD | Sharpe (sis/B&H) | vs B&H |
|---|---|---:|---:|---:|---:|---:|---:|
| **BTC** | 2021-25 | +157% | +158% | −27% | −77% | 0,95 / 0,71 | −1pp |
| **ETH** | 2021-25 | +82% | +45% | −37% | −79% | 0,60 / — | **+37pp** |
| SP500 (2015-25) | recente | +116% | +233% | −18% | −34% | 0,92 / 0,90 | −117pp |
| SP500 (1933-25) | 92 anos | +5.659% | +57.245% | −24% | −60% | 0,68 / — | enorme |

Sinal hoje: BTC **FORA (bear)**, ETH **FORA (bear)**, SP500 **COMPRADO (bull)**.

## Leitura

1. **ETH segue na linha — e melhor:** o sistema **bate o B&H** (+82% vs +45%, +37pp) com
   **metade do drawdown**. Em cripto (volátil, com bear markets de −77%/−79%), sair na
   reversão e voltar na tendência protege muito e ainda captura. Sinal hoje = FORA (bear),
   igual ao BTC, mais esticado pra baixo (ETH caiu mais).

2. **SP500 NÃO segue na mesma linha.** Em ações, o **B&H vence em retorno** (compounding de
   longo prazo, sem os bear markets brutais da cripto). O sistema **reduz o drawdown pela
   metade** (−18% vs −34%) mas com **Sharpe equivalente** (0,92 vs 0,90) — ou seja, não há
   o ganho de risco/retorno que existe na cripto. Em 92 anos a diferença explode (sair e
   voltar perde décadas de compounding). **Trend-following é desenhado pra ativos com
   quedas brutais (cripto), não pra ações que sobem estruturalmente.**

3. **Responde a tese macro do dono:** o sistema do SP500 diz **BULL/comprado hoje** — ele
   **não prevê** a queda que o dono teme; segue a tendência (que é de alta). O sistema não
   antecipa topo; reage à reversão.

## Caveats (gotchas levantados pelo Harry)

- **SP500 = OHLC sintético** (só close no cache; sem intraday real → trailing ATR vira
  range de close; MA200/Donchian em dias úteis, não 24/7). Aproximação, não produção.
- **Correlação cripto↔ações muda em stress** — o walk-forward não captura regime de crise.
- ETH/BTC = OHLCV real via CCXT.

## Decisão

Sistema **adotável em cripto** (BTC default v3.1; ETH segue a mesma config e bate o B&H).
Em **ações**, usar com ressalva: serve pra **proteção de drawdown**, não pra superar o B&H
de longo prazo. Próximo: coletar OHLCV real do SP500 (não só close) e validar em produção.
