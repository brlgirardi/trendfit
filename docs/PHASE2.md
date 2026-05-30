# Fase 2 — Camadas externas (macro + sentimento): resultado NEGATIVO honesto

**Data:** 2026-05-30
**Pergunta:** adicionar veto externo (Fear&Greed, VIX, DXY, juros 10Y) ao veto de
regime MELHORA o out-of-sample, ou over-restringe e destrói retorno?
**Veredito:** o veto macro por "AND" **piora** o sistema nos dois núcleos (v1 e v3).
**NÃO adotado no default.** O default continua sendo o v3 puro (`profiles/btc.json`).

Todos os números abaixo foram **lidos de arquivo** (não de stdout), em execução
leakage-free com dados reais do cache SQLite. Alinhamento sem look-ahead: cada série
externa entra com `reindex(ffill).shift(1)` (no dia *i* só enxerga o que fechou em *i-1*).

---

## 1. Como o veto externo entra

`trendfit/layers/external_regime.py` transforma cada série em um booleano `risk_on`
(VIX/DXY/10Y "não em alta" = libera; F&G > 25 = libera) e combina as camadas
escolhidas por **E lógico** (`composite_allow`). Esse vetor multiplica o fator de
exposição do veto MA200 — tanto no `walk_forward` (v1) quanto no `walk_forward_grid`
(v3). É um filtro, nunca gerador de sinal.

Reproduzir:

```bash
.venv/bin/python scripts/validate_phase2.py      # ablação sobre o v1
.venv/bin/python scripts/validate_phase2_v3.py   # ablação sobre o v3 grid (o que decide)
```

## 2. Ablação sobre o núcleo v1 (baseline simples, OOS 2021-08-16 → 2025-08-14)

| veto | retorno | maxDD | Sharpe | Calmar | expos. | vs B&H |
|---|---:|---:|---:|---:|---:|---:|
| baseline (só MA200) | +106% | −29% | 0,72 | 0,69 | 48% | −52% |
| + Fear&Greed | +115% | −29% | 0,75 | **0,73** | 48% | −43% |
| + VIX | +37% | −28% | 0,44 | 0,29 | 30% | −120% |
| + DXY (dólar) | +18% | −31% | 0,30 | 0,14 | 24% | −140% |
| + 10Y (juros) | +48% | −27% | 0,62 | 0,39 | 21% | −109% |
| + macro (vix+dxy+10y) | +35% | −20% | 0,61 | 0,38 | 12% | −123% |
| + tudo (fng+macro) | +29% | −23% | 0,54 | 0,29 | 12% | −129% |
| Buy & Hold | +158% | −77% | 0,71 | 0,35 | 100% | 0% |

## 3. Ablação sobre o núcleo v3 grid (o DEFAULT — é o que decide)

| veto | retorno | maxDD | Sharpe | Calmar | expos. | vs B&H |
|---|---:|---:|---:|---:|---:|---:|
| **baseline v3 (só grid)** | **+137%** | −30% | **0,85** | **0,80** | 44% | −21% |
| + Fear&Greed | +131% | −32% | 0,83 | 0,74 | 44% | −26% |
| + VIX | +32% | −32% | 0,40 | 0,23 | 29% | −125% |
| + DXY (dólar) | +25% | −27% | 0,38 | 0,21 | 24% | −132% |
| + 10Y (juros) | +55% | −28% | 0,66 | 0,42 | 22% | −103% |
| + DXY+10Y | +28% | −26% | 0,47 | 0,25 | **14%** | −130% |
| + macro (vix+dxy+10y) | +31% | −26% | 0,54 | 0,27 | 13% | −127% |
| + tudo (fng+macro) | +31% | −26% | 0,55 | 0,27 | 13% | −127% |
| Buy & Hold | +158% | −77% | 0,71 | 0,35 | 100% | 0% |

*(baseline v3 = +136,8% exato, idêntico ao default validado em STRATEGY_COMPARISON.md
— confirma que a ablação é fiel.)*

## 4. Por que o veto macro destrói o sistema (over-restrição por "AND")

- A causa-raiz é mecânica: combinar camadas por **E lógico** zera a posição sempre que
  *qualquer* uma diz risk-off. A exposição despenca de **44% → 13-14%** dos dias. O
  BTC tem tendência estrutural de alta; ficar de fora a maior parte do tempo perde as
  pernas grandes. O retorno cai de **+137% → ~+28%** (−109pp).
- O drawdown realmente melhora (−30% → −26%), mas o **Calmar piora** (0,80 → 0,25):
  o sistema sacrifica muito mais retorno do que ganha em proteção. Risco/retorno fica
  pior em todas as combinações macro.
- **Fear&Greed é a única camada quase-neutra**, e mesmo assim **inconsistente**: ajuda
  de leve no v1 (Calmar 0,69 → 0,73) e **atrapalha** de leve no v3 (0,80 → 0,74). Sinal
  que troca de sentido entre os núcleos é assinatura de ruído, não de alfa. Não adotar.

## 5. ⚠️ Correção de um número fabricado (`profiles/btc_macro.json`)

Uma versão anterior do `btc_macro.json` afirmava, nas notes, que o v3 + `dxy+us10y`
rendia **+150,3% / Sharpe 1,06 / Calmar 1,30** — quase batendo o B&H. **Esse número é
falso.** A ablação honesta (tabela §3, linha "+ DXY+10Y") mostra o real:
**+28% / Sharpe 0,47 / Calmar 0,25** — pior que o baseline por ~5× no retorno. O
+150,3% veio da execução corrompida/com look-ahead que o commit `a4bcf9d` já havia
sinalizado como "não verificada". O profile foi corrigido para refletir o número real
e marcado como **experimento refutado** (mantido só para reprodutibilidade, não para uso).

Lição (a mesma do sweep +183% do v3): **escolher a camada olhando o OOS é overfit de
meta-nível.** A própria escolha `dxy+us10y` tinha sido "informada pela ablação OOS" —
o tipo exato de viés que este projeto existe para pegar.

## 6. Decisão (30-mai-2026)

**Default inalterado = v3 puro** (`profiles/btc.json`, +136,8% OOS). Nenhuma camada
externa é adotada: macro over-restringe e Fear&Greed é ruído. A Fase 2 fecha como
**resultado negativo honesto** — o valor foi descartar uma hipótese plausível com dados,
não vender um número bonito.

### O que poderia fazer a Fase 2 dar certo (não testado ainda)

A refutação é do veto macro **por "AND" (zera posição)**. Caminhos que continuam abertos,
sempre validando OOS sem escolher camada olhando o OOS:

1. **Macro modulando o TAMANHO da posição** (peso contínuo) em vez de zerar — ex.: risk-off
   corta exposição pela metade, não a zero. Menos brutal que o "AND".
2. **Sinais melhores**, com tese econômica a priori: fluxo de ETF spot, on-chain (MVRV,
   realized cap), em vez de proxies macro de liquidez que mal se correlacionam intradiária.
