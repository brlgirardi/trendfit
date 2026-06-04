# Qual estratégia vence em cada regime? (boom vs maduro vs lateral)

**Data:** 2026-06-04
**Pergunta (do dono):** o boom inicial (BTC 10-20x em 2020-21) pode nunca mais acontecer.
Num BTC **maduro/lateral**, quem vence — ainda é o trend-following?

Reproduzir: `.venv/bin/python scripts/validate_regime_split.py` (long-only, causal, sem
otimizar parâmetros no período). Lido de arquivo.

## Resultado (Calmar entre parênteses)

| Regime | Buy & Hold | Trend (v3) | Mean-reversion (range) |
|---|---:|---:|---:|
| Boom 2019-2021 | +1148% (2,08) | +531% (2,26) | +45% (0,23) |
| **Maduro 2022→hoje** | +37% (0,11) | **+103% (0,58)** | +0% (0,00) |
| Lateral puro (chop mar-out/2024) | −1% (−0,03) | −16% (−0,86) | **+10% (0,72)** |
| Tudo 2019→hoje | +1613% (0,61) | +1180% (1,09) | +45% (0,09) |

## Leitura honesta

1. **No maduro pós-boom (2022→hoje) — o cenário que o dono pediu — o Trend v3 VENCE claro:**
   +103% vs B&H +37%, com **metade do drawdown** (−30% vs −67%). Ou seja, **mesmo sem o boom,
   o trend é o vencedor.** A preocupação "o vencedor só ganhou por causa do boom" não se
   sustenta: o trend bate o B&H também no período maduro.

2. **A intuição do dono está CERTA para o lateral PURO:** no chop de 2024 o trend sofre
   whipsaw (−16%, Calmar −0,86) e o **mean-reversion ganha** (+10%, Calmar 0,72). Em mercado
   sem tendência, range-trading é superior — confirmado pelos dados.

3. **MAS o "maduro 2022-2026" NÃO foi lateral** — teve um bear de −77% (2022) e um bull
   (2023-25). Nesses movimentos direcionais o trend capturou e o mean-reversion fracassou
   (+0%). O lateral puro foi um trecho curto (~7 meses).

## O dilema do futuro (e por que não dá pra "escolher o vencedor")

- Se o futuro tiver **tendências** (o padrão histórico do BTC, mesmo maduro) → **trend vence**.
- Se for **puramente lateral/range** → **mean-reversion vence**.
- Ninguém sabe qual regime virá. **Apostar em "vai lateralizar" é uma aposta de regime.**

A tentação óbvia — *trocar de estratégia conforme o regime* (trend na tendência, mean-rev
no lateral) — exige **detectar o regime em tempo real sem look-ahead**, que é justamente o
que o **filtro anti-chop refutou (Fase 3d)**: o detector ou chega tarde ou é miragem.

## Conclusão

O **Trend v3 é o vencedor robusto e "all-weather"** para o BTC: ganha no boom e no maduro,
e só perde no lateral puro — que é minoria do tempo e impossível de prever de antemão. O
mean-reversion é um **especialista de lateral** que não se sabe quando vai precisar; usá-lo
como default troca um problema conhecido e pequeno (whipsaw ocasional) por uma aposta de
regime. O preço do trend (sofrer no chop) é o custo de **não precisar prever o regime** —
e, no agregado, ele paga (Calmar 1,09 no período todo, 0,58 no maduro).
