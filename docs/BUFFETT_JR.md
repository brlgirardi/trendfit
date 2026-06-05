# Agente "Buffett Jr" — postura por critérios (NÃO previsão)

**Data:** 2026-06-05 · **Código:** `trendfit/allocation.py` (`environment_read`,
`asset_posture`) + render em `scripts/dashboard.py`.

## O que é (e o que NÃO é)

O que o Buffett faz: **critérios explícitos → leitura do PRESENTE → postura → age**.
NÃO é previsão de preço, crash ou probabilidade ("vai até $X" = recusado, refutado 5×).
É um painel de decisão **auditável** que separa dois eixos — como Buffett separa "o que
comprar" de "margem de segurança":

- **Eixo 1 — TIMING (validado OOS = regime):** preço vs MA200 + inclinação. **MANDA** no
  comprado/fora. É o núcleo v3.1, já validado. Não muda aqui.
- **Eixo 2 — POSTURA (contexto, transparente, NÃO validado):** dado o timing, *quão*
  agressivo/defensivo estar. Sintetiza valuation + sentimento + alavancagem + macro.

> **REGRA DE OURO:** a postura **INFORMA**, o regime **DECIDE**. A postura é leitura/texto
> e **nunca** altera o sinal nem o tamanho. Linha vermelha: leitura do presente, jamais
> aposta no futuro.

## Critérios e fontes (já no DB, via `external.py`)

| Critério | Série | Eixo | Papel |
|---|---|---|---|
| Regime / tendência | preço vs MA200 + slope | TIMING | **validado — move dinheiro** |
| Valuation | `mvrv` (BTC) / percentil de preço (proxy) | POSTURA | desconto / zona |
| Sentimento | `fng` (Fear & Greed) | POSTURA/ambiente | contrarian |
| Alavancagem | `funding` (BTC) | POSTURA | euforia esticada |
| Juros | `us10y` | ambiente | aperto/alívio |
| Risco de mercado | `vix` | ambiente | calmo/estresse |
| Dólar | `dxy` | ambiente | headwind/tailwind |

## Camada de ambiente (global) — `environment_read(ctx)`

Classifica o pano de fundo macro em **FAVORÁVEL / MISTO / ADVERSO** a risco, somando
estados (ok=+1, bad=−1) de juros (caindo=alívio), VIX (<20 calmo), dólar (forte=headwind)
e Fear&Greed (medo=contrarian ok, euforia=risco). Limiares explícitos e editáveis. É
**descrição do regime macro atual**, não aposta de direção.

## Camada de postura por ativo — `asset_posture(view, ctx, env)`

| Regime | Contexto | Postura | Leitura |
|---|---|---|---|
| BULL | barato, sem euforia, ambiente não-adverso | **ACUMULAR** | construir posição |
| BULL | caro + euforia/funding esticado | **CAUTELOSO** | manter, não aumentar no topo |
| BULL | adverso / sem extremo | **NEUTRO** | manter o que o sistema indica |
| BEAR | barato | **CAUTELOSO** | zona de interesse; agir só na virada da MA200 |
| BEAR | sem desconto | **DEFENSIVO** | aguardar virada de regime |

Cada postura vem com **racional escrito** + **cenários CONDICIONAIS** (gatilhos objetivos
do presente, ex.: *"SE recuperar a MA200 (~$X, +Y% daqui) com valuation não-caro →
ACUMULAR"*). Nunca probabilidade.

## Leitura atual (05/06/2026, de arquivo)

- **Ambiente: FAVORÁVEL** — VIX 15 (calmo), Fear&Greed 23 (medo extremo), juros/dólar
  estáveis. Sem euforia perigosa.
- **BTC** BEAR ($61k, −22% da MA200), MVRV pct 32% → **CAUTELOSO** (zona de interesse).
  Gatilho: recuperar a MA200 (~$78,8k, +29%) → ACUMULAR.
- **ETH** BEAR ($1,6k, −35%) → **DEFENSIVO** (ver limitação abaixo).
- **Ouro / SP500** BULL, em máxima → **NEUTRO**.

## Camada extra — Termômetro do mercado de apostas (Polymarket)

`trendfit/data/polymarket.py` (`fetch_btc_price_distribution`) lê a distribuição de
probabilidade **IMPLÍCITA** que o Polymarket precifica para o BTC (Gamma API pública, sem
auth, mercado anual mais líquido — ex. "What price will Bitcoin hit in 2026?", vol ~$41M).
Mostra no painel, em faixa roxa separada: piso 50/50, prob. de tocar níveis de alta e a
cauda de medo.

**Fronteira rígida (linha vermelha):** é leitura do PRESENTE — o que a multidão aposta
AGORA, igual Fear&Greed. **O sistema NÃO usa estes números** (não acionam, não modulam, não
viram sinal). É espelho da multidão, exibido lado a lado com a postura — o leitor tira a
conclusão; o painel não sintetiza recomendação a partir da divergência. Cai graciosamente
(faixa some) se a API estiver indisponível. Prob. implícita ≠ prob. real.

Leitura 05/06: piso 50/50 ~$46k · tocar $90k 28% · tocar $100k 18% · cair a $30k 14%.

## Limitações conhecidas (honestas)

1. **ETH sem valuation real:** não há MVRV de ETH coletado; cai no **percentil de preço**
   (47% = "neutro"), que não captura "barato" num bear porque o preço nominal já foi menor
   na história. Por isso ETH=DEFENSIVO e BTC=CAUTELOSO. Não é bug — é proxy declarado.
   *Próximo:* coletar MVRV/valuation de ETH, ou usar distância da MA200 como desconto técnico.
2. **Dois "ambientes":** `environment_read` (macro: juros/VIX/dólar/sentimento) pode dar
   FAVORÁVEL enquanto `environment_fragility` (concentração: SP500 no topo + BTC bear) dá
   ELEVADA. São eixos diferentes (atrito macro vs euforia/topo de ativos), mas convém
   **unificar** numa leitura só na próxima iteração.
3. **Sem FRED ainda:** macro usa `us10y/vix/dxy/fng`. Juros reais, inflação (CPI),
   emprego e liquidez (FRED) ficam como incremento — exigem coletor novo.
4. **Defasagem:** séries de contexto atualizam até ~1 semana atrás (coletor externo); é
   contexto/postura, não timing, então é aceitável.
