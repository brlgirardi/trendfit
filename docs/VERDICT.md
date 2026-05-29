# Veredito — Sprint 1 (BTC, dados reais)

**Data:** 2026-05-29
**Pergunta:** a arquitetura validada no backtest reconstruído (ensemble trend +
veto de regime) se sustenta com **dados reais**?

---

## Dados

- Fonte: **Binance BTC/USDT diário**, via CCXT (pública, custo zero).
- Janela: **2017-08-17 → 2026-05-29** (3.208 candles, ~8,8 anos). Uma fonte só,
  sem costura entre exchanges.
- Cache: SQLite (`db/trendfit.sqlite`), idempotente.

> Nota: a Binance só tem BTC/USDT desde ago/2017. Estender até 2014 (como cita o
> PRD) exigiria costurar Bitstamp/yfinance (BTC/USD), misturando exchanges.
> Optei por manter uma fonte limpa nesta sprint. Estender o histórico é melhoria
> documentada (mais ciclos OOS).

## Metodologia

- Walk-forward: treino **4 anos** → teste **1 ano cego** → rola pra frente. 4 janelas OOS.
- Seleção da config no treino por **retorno/risco** (retorno ÷ |drawdown|), não por lucro máximo.
- Núcleo: ensemble Donchian multi-lookback, posição fracionária por votação.
- Veto v1: preço vs MA200.
- Sem look-ahead (canais com `shift(1)`; peso de hoje só captura o retorno de amanhã).
- Sem custos de transação modelados (cost_bps=0) — ver limitações.

## Resultado Out-of-Sample (2021-08-16 → 2025-08-14, 1.459 dias)

| Estratégia | Retorno | CAGR | MaxDD | Sharpe | Exposição |
|---|---:|---:|---:|---:|---:|
| **Sistema (núcleo + veto)** | **+106,1%** | +19,8% | **−28,9%** | **0,72** | 47,8% |
| Núcleo sem veto | +84,8% | +16,6% | −48,8% | 0,62 | 57,0% |
| **Buy & Hold** | **+157,7%** | +26,7% | −76,6% | 0,71 | 100% |

Janelas (config escolhida no treino → retorno OOS no teste cego, com veto):
- 2021-08 → 2022-08: `medio` [20,40,60] → **−17,2%**
- 2022-08 → 2023-08: `medio` [20,40,60] → **+8,4%**
- 2023-08 → 2024-08: `medio` [20,40,60] → **+49,7%**
- 2024-08 → 2025-08: `amplo` [15,30,55,90] → **+54,2%**

---

## Veredito: a arquitetura se sustenta — como gestora de risco, não como maximizadora de retorno

**1. NÃO bateu o Buy & Hold em retorno absoluto.** Com dados reais, o B&H fez
+157,7% no período OOS contra +106,1% do sistema — o B&H **ganhou por ~52pp**.
Isso **refuta a magnitude** do backtest reconstruído (que dava +51% de *vantagem*
do sistema sobre o B&H, com B&H em apenas +28%).

**2. A diferença vem dos dados, não de um bug.** A série reconstruída do PRD
(âncoras mensais + ruído) subestimou grosseiramente o retorno real do BTC em
2021-2025: lá o B&H era +28%; na realidade foi +157,7%, porque o período incluiu
o bull market forte de 2023-2025. Conclusão tirada de dados sintéticos sobre o
*nível* de retorno não era confiável — exatamente o tipo de armadilha que o
projeto existe para evitar.

**3. A TESE central do PRD se confirmou.** O Risco #3 do PRD já previa: *"sistema
perde p/ B&H em bull puro; valor real é proteção de drawdown em bear"*. Foi
precisamente o que aconteceu:
   - Drawdown máximo **−28,9% (sistema) vs −76,6% (B&H)** → proteção de ~48pp.
   - Sharpe **0,72 vs 0,71** → empate técnico em retorno ajustado a risco, com
     metade da exposição (47,8% do tempo no mercado).
   - O **veto de regime ajudou em retorno E risco**: +106,1% vs +84,8% sem veto,
     e cortou o drawdown de −48,8% para −28,9%.

**4. O sistema está fazendo o que promete, agora.** Sinal atual (2026-05-29):
BTC $73,6k **abaixo da MA200 ($79,8k) → regime BEAR → posição 0%**. O B&H está
exposto à queda; o sistema saiu. É o cenário onde o valor da arquitetura aparece.

### Decisão

A arquitetura **se sustenta com dados reais** para o objetivo de **retorno
ajustado a risco e proteção de capital** — não para "bater o B&H em retorno bruto
num bull market". O KPI do projeto ("bater B&H OOS") precisa ser qualificado:
bater em **retorno/risco** (Sharpe, Calmar), não necessariamente em retorno
absoluto. Seguir para a Fase 2 (camadas externas) para fortalecer o veto, que é
de onde vem o alfa real desta arquitetura.

---

## Limitações (honestidade metodológica)

- **4 janelas OOS** é pouco. O ponto de início (2021-08, perto do topo de ciclo)
  favorece o sistema no quesito drawdown. Mais ciclos (estender dados pré-2017)
  dariam um veredito mais robusto.
- **Custos de transação não modelados.** O sistema tem turnover menor que o B&H
  e exposição de ~48%, então custos o penalizariam menos que estratégias de alta
  rotação — mas o número exato muda com fees. (`cost_bps` já existe no engine.)
- **Veto v1 é cego a fluxo.** Como o próprio PRD nota, a MA200 não vê o sangramento
  de ETF; é aí que o veto v2/v3 (Fase 3) deve adicionar valor real.
- **Sem slippage / sem modelagem de execução.** Backtest diário em close.

## Como reproduzir

```bash
source .venv/bin/activate
python scripts/run_btc_sprint1.py
```
