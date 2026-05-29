# PRD Futuro — Radar de Oportunidades Macro (Fases 4–5)

> **Status: RASCUNHO / pré-pesquisa.** Não construir antes de uma rodada de
> pesquisa dedicada (validar quadrantes, fontes e mapeamento ativo↔regime com
> dados históricos). Este doc fixa a visão e as perguntas em aberto.

---

## 1. Problema

O núcleo TrendFit decide *quando* entrar/sair de **um** ativo (timing de
tendência). O Radar responde a uma pergunta diferente e anterior: **em quais
ativos vale a pena rodar o sistema agora, dado o cenário macro?**

Exemplo concreto (cenário atual, mai/2026): com inflação resiliente e juros
ainda altos, **metais (ouro/prata/cobre)** tendem a se sair bem. O Radar precisa
"ligar" esse raciocínio macro à seleção de watchlists — não escanear tudo às
cegas, mas priorizar as classes de ativo favorecidas pelo regime econômico
vigente.

## 2. Framework: quadrantes macro (estilo Investment Clock)

A literatura clássica (Merrill Lynch Investment Clock) cruza dois eixos —
**crescimento** (acelerando/desacelerando) e **inflação** (subindo/caindo) — em
4 regimes, cada um favorecendo classes de ativo distintas:

| Regime | Crescimento | Inflação | Tende a favorecer |
|---|---|---|---|
| **Recuperação (Reflation)** | ↑ | ↓ | Ações (growth), crypto, small caps |
| **Sobreaquecimento (Overheat)** | ↑ | ↑ | **Commodities, metais, energia**, value |
| **Estagflação (Stagflation)** | ↓ | ↑ | **Ouro/metais**, cash, defensivos |
| **Desaceleração (Reflation→Deflation)** | ↓ | ↓ | Bonds, dólar, defensivos |

A posição no relógio é estimada por um painel de indicadores macro. O Radar
classifica o regime atual e usa isso como **peso de prioridade** sobre as
watchlists, antes de rodar o backtest/walk-forward de cada ativo.

## 3. Painel de indicadores (FRED + mercado, custo zero)

Eixos e fontes candidatas (todas gratuitas via `fredapi` / `yfinance`):

**Inflação**
- CPI (`CPIAUCSL`), Core CPI (`CPILFESL`), PCE (`PCEPI`), breakeven 5y (`T5YIE`)

**Emprego / Crescimento**
- Desemprego (`UNRATE`), Payrolls (`PAYEMS`), pedidos de seguro-desemprego (`ICSA`)
- PMI / ISM (proxy), produção industrial (`INDPRO`), PIB (`GDPC1`)

**Juros / Política monetária**
- Fed Funds (`DFF`, `FEDFUNDS`), curva 10y-2y (`T10Y2Y`), 10y (`DGS10`)

**Liquidez / Risco**
- M2 (`M2SL`), DXY (dólar), VIX, spread de crédito (`BAMLH0A0HYM2`)

Cada indicador entra como **nível + tendência** (ex.: inflação alta E subindo vs
alta mas caindo mudam o quadrante).

## 4. Saída do Radar

1. **Classificação de regime** atual (1 dos 4 quadrantes + confiança).
2. **Ranking de classes de ativo** por aderência ao regime (ex.: estagflação →
   metais no topo).
3. **Por ativo da watchlist**: roda backtest+walk-forward default e rankeia por
   retorno/risco, ponderado pela prioridade macro da sua classe.
4. **Categorização**: `otimizar` (alto potencial + regime favorável) /
   `monitorar` / `ignorar`.
5. **Triggers de anomalia**: volume anormal, ATR breakout, quebra de correlação
   com BTC, setor inteiro se movendo.

## 5. Watchlists iniciais (a refinar)

- **Crypto:** BTC, ETH, majors selecionadas
- **Metais:** ouro (GLD/XAU), prata (SLV), cobre (HG), mineradoras
- **Energia:** WTI, gás natural, XLE
- **Tech US:** índices/ações líquidas
- **ETFs macro:** TLT (bonds), UUP (dólar), commodities amplas

## 6. Perguntas em aberto (a resolver na pesquisa ANTES de codar)

1. **Quais indicadores e quais thresholds** definem cada quadrante de forma
   robusta? (Evitar overfitting de regime — mesma disciplina do núcleo.)
2. Janela de cálculo de "tendência" de cada indicador (3m? 6m? 12m?).
3. Como tratar **divergências** (crescimento OK mas crédito apertando)?
4. O mapeamento quadrante→classe-de-ativo se sustenta **out-of-sample** em dados
   históricos (validação cruzada por décadas)?
5. **Look-ahead em dados macro**: CPI/PIB são revisados e publicados com atraso —
   usar só o que estava disponível na data (vintages do FRED / ALFRED).
6. Latência de regime: o relógio gira devagar; com que frequência reavaliar?

## 7. Dependências

- Fase 2 (camadas externas: FRED + on-chain + sentimento) precisa existir antes.
- Fase 3 (veto IA) compartilha indicadores macro com o Radar.
- O Radar é Fase 4–5; só faz sentido após o núcleo estar validado em multi-ativo.

## 8. Risco principal

Overfitting de regime: "explicar o passado" com quadrantes é fácil; prever o
futuro não. A validação macro precisa ser tão rígida quanto a do núcleo —
walk-forward sobre décadas, dados em vintage real, sem ajuste fino de thresholds.
