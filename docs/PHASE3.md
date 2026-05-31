# Fase 3 — Moduladores contínuos (funding / MVRV / macro): resultado NEGATIVO honesto

**Data:** 2026-05-31
**Gatilho:** intuição de que correlação macro, saídas em mercado super-alavancado e
sinais de sobrecompra/sobrevenda poderiam melhorar o núcleo v3.
**Veredito:** nenhuma das três famílias melhora o OOS do v3 de forma robusta. Funding
chega a PIORAR. **Default inalterado = v3 puro** (`profiles/btc.json`).

Todos os números lidos de **arquivo** (não de stdout). Reproduzir:

```bash
.venv/bin/python scripts/validate_phase3.py    # auto-popula funding/MVRV se faltarem
```

---

## 1. A correção sobre a Fase 2: modular, não vetar

A Fase 2 matou o veto macro **binário (AND)** — ele zerava a posição e desabava o
retorno (exposição 44%→14%). A hipótese da Fase 3 é que o erro era o **mecanismo**, não
o dado. Então aqui cada sinal vira um **fator contínuo de exposição em [floor, 1]**
(`trendfit/layers/external_regime.py::exposure_factor` / `macro_factor`): só REDUZ o
tamanho em extremos, nunca zera.

Disciplina anti-overfit (a mesma que validou o trailing ATR):
- z-score **rolling causal** (a série entra com `ffill+shift(1)`) — sem look-ahead.
- o threshold/floor de cada modulador é uma **dimensão do grid**, escolhido **só no
  treino** junto com asym/banda/ATR. **"off" (sem modulador) é sempre candidato** — o
  sistema pode declinar o sinal em cada janela.

## 2. Dados novos coletados (custo zero, cobrem o OOS)

| Série | Fonte | Cobertura | Tese |
|---|---|---|---|
| `funding` | Binance USDT-M (8h→diário) | 2019-09 → hoje | funding alto = longs super-alavancados = fragilidade/topo |
| `mvrv` | CoinMetrics community (CapMVRVCur) | 2014 → hoje | MVRV alto = preço muito acima do custo base = euforia |
| `dxy/us10y/vix` | (já no cache, Fase 2) | — | aperto de liquidez |

*(Open Interest foi descartado: a Binance só dá ~30 dias de histórico de graça.)*

## 3. Ablação OOS (2021-08-16 → 2025-08-14)

| família | retorno | maxDD | Sharpe | Calmar | expos. | vs B&H |
|---|---:|---:|---:|---:|---:|---:|
| **baseline (só v3)** | **+137%** | −30% | **0,85** | **0,80** | 44% | −21% |
| + funding | +119% | −30% | 0,79 | 0,72 | 43% | −39% |
| + MVRV | +137% | −30% | 0,85 | 0,80 | 44% | −21% |
| + macro (modulado) | +137% | −30% | 0,85 | 0,80 | 44% | −21% |
| + funding+MVRV | +123% | −30% | 0,80 | 0,74 | 44% | −35% |
| Buy & Hold | +158% | −77% | 0,71 | 0,35 | 100% | 0% |

O que o grid **escolheu** por janela (revela o porquê):

| família | ΔRet | ΔCalmar | escolhas do grid (4 janelas) | leitura |
|---|---:|---:|---|---|
| + funding | −17,6pp | −0,08 | funding 2× / off 2× | **overfit**: bom no treino, pior no cego |
| + MVRV | 0,0pp | 0,00 | off 4× | grid rejeita o sinal já no treino |
| + macro (modulado) | 0,0pp | 0,00 | off 4× | idem — nem modulando ele entra |
| + funding+MVRV | −13,8pp | −0,06 | funding 1× / off 3× | overfit residual do funding |

## 4. Por que falhou (apesar de a tese ser boa)

- **MVRV e macro são rejeitados pelo próprio treino** ("off" nas 4 janelas). Reduzir
  exposição em MVRV/macro alto não melhorava nem o passado — então o grid nunca os usa.
  Resultado idêntico ao baseline (neutros, não destrutivos). Que o "off" sempre vença é
  o sinal de que a infra está honesta.
- **Funding é o caso mais instrutivo:** o grid o *seleciona* em 2 de 4 janelas (parece
  bom no treino) mas **piora o OOS** (−17,6pp). Miragem de treino que não generaliza.
  Causa provável: o núcleo v3 já sai via **trailing ATR** quando a tendência vira;
  cortar exposição antes, por funding esticado, só sacrifica pernas que ainda subiam
  (em bull, funding fica alto por meses sem reverter). O sinal de alavancagem e o
  trailing competem pelo mesmo trabalho — e o trailing faz melhor.
- Nenhuma família melhorou sequer o **drawdown** (todas −30%). Não há trade-off favorável.

## 5. Decisão (31-mai-2026)

**Default inalterado = v3 puro** (+136,8% OOS). Fase 3 fecha como **resultado negativo
honesto** — testar a hipótese com dados e descartá-la vale mais que adotar um número que
não generaliza. A infra fica pronta e reutilizável (coletores funding/MVRV, modulador
contínuo, `external_by` por candidato no grid).

### O que continua aberto (não testado)
A refutação é do uso desses sinais como **modulador de exposição que reduz topo**. Ainda
não testado, e conceitualmente diferente:
1. **Funding/MVRV como sinal de ENTRADA contracíclica** (comprar capitulação: funding
   muito negativo / MVRV < 1), em vez de cortar topo. É mean-reversion de entrada — exige
   cuidado (mean-reversion já foi traiçoeira no BTC), mas o lado da compra é menos punido
   que o short.
2. **Outro ativo**: macro e MVRV podem ter mais sinal em ativos sem a tendência
   estrutural tão forte do BTC (Fase 4 multi-ativo).
