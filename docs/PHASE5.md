# Fase 5 — Alocação por valuation (MVRV): tese REFUTADA com dados

**Data:** 2026-06-04
**Pergunta (do dono):** "comprar quando barato (MVRV baixo) e reduzir quando caro (alto)
acerta muito" — funciona como estratégia de alocação de ciclo?
**Veredito:** **Não.** Sem look-ahead, a regra rende muito menos que Buy & Hold e que o
trend-following, e **degrada** o trend quando combinada. Não adotada.

Reproduzir: `.venv/bin/python scripts/validate_valuation.py` (lido de arquivo).

## Método (anti-look-ahead)

"Barato/caro" = **percentil EXPANDING causal** do MVRV (só com a história até cada dia)
+ `shift(1)`. Exposição: barato (pct ≤ 30%) → 100%; caro (pct ≥ 70%) → 0%; linear no meio.
Threshold 30/70 escolhido **a priori** (não fitado no OOS). v3 = config live do walk-forward.

## Resultado (2018-08 → 2026-06, ~7,8 anos / ~2,5 ciclos)

| Estratégia | retorno | maxDD | Sharpe | Calmar | exposição |
|---|---:|---:|---:|---:|---:|
| Buy & Hold | +903% | −77% | 0,79 | 0,45 | 100% |
| **v3 (trend puro)** | +1180%* | −38% | 1,08 | **1,03** | 38% |
| **Valuation-only (MVRV)** | **+51%** | −62% | 0,33 | **0,09** | 44% |
| Trend × Valuation | +65% | −16% | 0,69 | 0,41 | 7% |

\* O +1180% do v3 usa a **config mais recente aplicada retroativamente** (otimista, não é
o OOS rigoroso). O número honesto do v3 OOS continua **+136,8%** (2021-2025, walk-forward).
A comparação **relativa** abaixo é robusta (todas as linhas usam o mesmo tratamento).

## Por que a tese falha (apesar de parecer óbvia no retrovisor)

- **Vende cedo demais:** o MVRV fica "caro" no *meio* do bull, então a regra sai antes da
  parte explosiva — perde justamente as pernas grandes. Daí +51% vs +903%.
- **Os topos de MVRV encolhem a cada ciclo** (2017 ~4,7 → 2021 ~3,x → agora < 2). Um
  threshold de "caro" fica dessincronizado — exatamente o que travou o dono em 2025/2026
  (esperou o MVRV-topo de antes, que não veio). **Não foi azar de timing: a regra perde
  sistematicamente.**
- **Combinar destrói o trend:** dosar o v3 pelo valuation derruba a exposição para 7% e o
  retorno de +1180% para +65% — mesma over-restrição da Fase 3.
- **Amostra pequena:** ~2,5 ciclos não calibram uma regra de ciclo. Qualquer "acerto"
  histórico é anedota, não edge.

## Decisão (04-jun-2026)

Valuation (MVRV) **não** vira regra de alocação nem de dosagem. Fica **só como contexto
informativo** no painel (rotulado: testado e refutado como sinal). O que decide entrar/
sair continua sendo o **trade system (preço): regime MA200 + Donchian + trailing ATR.**

Isto fecha o ciclo das hipóteses do dono (short, macro, funding, RSI, vol-target, anti-chop,
valuation) — **todas refutadas OOS.** O alfa real e robusto está em seguir a tendência com
proteção de drawdown, não em prever ciclo/topo/fundo por valuation.
