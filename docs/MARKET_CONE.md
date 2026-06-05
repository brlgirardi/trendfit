# Cone do mercado de apostas (Passo #3)

**Data:** 2026-06-05 · **Arquivos:** `trendfit/data/kalshi.py` (coletor novo),
`trendfit/cockpit.py` (`market_cone`), `app/cockpit_app.py` (`_add_cone` no gráfico).

Plota, **à frente de hoje** no gráfico do cockpit, a distribuição de preço que o
**mercado de apostas** precifica para o ativo até a resolução (fim de 2026). Combina
**duas multidões independentes** — Kalshi + Polymarket — lado a lado.

## Linha vermelha (inegociável)

> **O cone é do MERCADO DE APOSTAS, NÃO do sistema.** O TrendFit não prevê preço,
> crash nem probabilidade. "Análise preditiva" aqui = a previsão **de quem aposta**
> (espelho da multidão), igual o Fear&Greed ou o funding. Estes números **NUNCA**
> entram em `strategy.py` / `signal.py` / `walkforward.py`, não acionam, não modulam
> exposição, não viram sinal. Isso está marcado no código (`NEVER USED BY ENGINE`).

É a continuação natural da camada Polymarket (que já mostrava o **presente**): agora
projetamos a aposta **até o horizonte** dela. Não reabre as 5+ hipóteses de previsão
refutadas — o sistema continua só classificando regime/postura.

## Fontes (validadas de API real)

- **Kalshi** (`api.elections.kalshi.com/trade-api/v2`, pública, **sem auth**). Séries
  one-touch anuais: `KX{ASSET}MAXY` (alta) + `KX{ASSET}MINY` (baixa). Nível em
  `floor_strike`, probabilidade implícita em `last_price_dollars`, liquidez em
  `open_interest_fp`. Cobre **BTC** e **ETH** (líquidos, OI nas centenas de milhares).
- **Polymarket** (Gamma API, já existente). Mercado anual de **BTC** ("what price will
  bitcoin hit in 2026"), também one-touch.

Cada ponto vira `{target, prob, dir(up/down), source, oi}`. As fontes ficam **lado a
lado, sem média/blend** — a divergência entre elas é informação honesta.

## Semântica HONESTA (one-touch)

Os mercados resolvem **Yes se o preço TOCAR o strike em algum momento** até o fim do
ano — **não** "fechar nele". Por isso o rótulo diz **"tocar X"**, nunca "preço será X".
A curva é cumulativa (decresce conforme o alvo de alta sobe / o alvo de baixa cai).

## Leitura no gráfico

- Eixo X estendido até a resolução; linha pontilhada = **hoje** (separa sistema ↔ apostas).
- **Raios** de hoje → cada alvo, opacidade/espessura ∝ probabilidade (formato de leque).
- **Marcadores** por fonte e direção: tamanho/opacidade ∝ prob, rótulo de %, **OI no
  hover**. Alta em **verde**, baixa em **vermelho**. Fonte por símbolo: Kalshi = losango,
  Polymarket = círculo. Coluna do Polymarket ~18 dias antes da do Kalshi só para não
  sobrepor.
- Foco automático nos últimos ~13 meses + futuro (interativo: dá pra dar zoom out).

## Por que o cone some em 1º de janeiro (by design, não bug)

A data plotada é o **fim do horizonte da aposta** (resolução, ~31/12/2026), parseada do
`event_ticker` (ex `KXBTCMAXY-26DEC31`) — **não** o settlement da Kalshi (~31/01/2027).
Quando a aposta vence, não há mais mercado para aquele horizonte e o cone **desaparece**
até a próxima safra anual de mercados abrir. É esperado.

## Escopo e degradação

- **BTC, ETH** têm cone hoje. **Ouro, SP500** → sem mercado mapeado: o cone simplesmente
  **não aparece** (degrada gracioso, igual o Polymarket de hoje; o coletor nunca derruba
  o painel — `try/except → None`).
- Fed/juros e SP500 têm mercado na Kalshi (571 séries Economics) — ficam para incremento.
- **Default `btc.json` INTOCADO.** Nada aqui toca o engine de sinais.

## Trade-offs em aberto (a calibrar testando)

- Alvos extremos de baixa probabilidade (ex BTC $200k @ 4%) **esticam o eixo Y** e
  achatam o histórico. Mantido por **honestidade** (mostra quão longe a aposta extrema
  está). Alternativa, se o dono preferir: filtrar por prob mínima ou teto de alvo.
- Cache de 600 s no cone (dado vivo de mercado).
