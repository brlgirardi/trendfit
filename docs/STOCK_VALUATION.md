# Valuation de ações como contexto (CAPE/Shiller)

**Data:** 2026-06-05 · **Arquivos:** `trendfit/data/external.py` (`fetch_cape_multpl`),
`trendfit/cockpit.py` (SP500 usa CAPE), `trendfit/allocation.py` (postura), `app/cockpit_app.py`
(subplot de valuation generalizado).

Resolve um furo honesto do Buffett Jr: o SP500 usava um **proxy de percentil de preço** como
"valuation" (marcava 100% só porque o preço está perto da máxima). Agora usa o **CAPE real**
(Shiller P/E, P/L ciclicamente ajustado) — a métrica-âncora de valuation de ações.

Motivado pelo gráfico da Bloomberg ("US Stock Valuations Have Never Been Higher" — composto de
8 métricas em percentil histórico, perto de 100, acima de 1929 e 2000). O CAPE é a mais icônica
e a única com fonte pública/validável daqui (FRED estava inalcançável; multpl.com responde).

## Fonte (validada de arquivo)

- **CAPE/Shiller** via `multpl.com/shiller-pe/table/by-month` (tabela mensal, sem auth, desde
  **1871**). Coletor `fetch_cape_multpl` no padrão dos demais (urllib, `_upsert` idempotente,
  `try/except → 0`, nunca inventa). Série `cape` no SQLite.
- Leitura de 2026-06-05: **CAPE 41,57**, **percentil 99,1%** sobre 1865 meses (mediana ~16,1;
  pico histórico ~44 em 2000). Confirma o post: extremo histórico, só 2000 foi maior.

## Como entra (CONTEXTO, nunca sinal)

- `cockpit.py`: o SP500 calcula o **percentil do CAPE atual** no histórico + label `CAPE 42` e
  passa para `asset_view` (exatamente como o BTC faz com o MVRV). O gráfico ganha um subplot de
  CAPE (com a mediana ~16 como referência).
- `allocation.py` (Buffett Jr): valuation em **extremo histórico (percentil ≥ 90)** passa a
  contribuir para a postura **CAUTELOSO** no BULL — antes exigia euforia/funding junto. Racional:
  carestia histórica = a margem de segurança pesa, independente do sentimento.
- Resultado: o SP500 sai de "NEUTRO por proxy" para **CAUTELOSO — CAPE 42 em extremo histórico**.

## Linha vermelha (mantida)

> **Postura INFORMA, regime DECIDE.** A postura é **display-only** — nunca alimenta
> `target_weights`/sinal, nunca aciona, zera ou dimensiona posição. O CAPE alto **não é venda**:
> a Fase 5 (docs/PHASE5.md) refutou vender por valuation (vende cedo, destrói retorno). É margem
> de segurança; o timing segue o regime (preço vs MA200 + trailing). O sistema continua surfando
> a tendência do SP500 (hoje COMPRADO/BULL) — só pinta o quão esticado o valuation está.

## Escopo e pendências

- CAPE aplica-se a **ações dos EUA** → só o **SP500**. BTC segue com MVRV; ETH/Ouro seguem proxy
  de preço (sem fundamental).
- **Refresh:** `fetch_cape_multpl` é standalone (rodado uma vez para popular o DB). Para
  auto-atualizar, deve entrar na rotina de refresh de externos (junto com o conserto de SSL já
  pendente dos coletores yfinance — ver memória).
- Percentil é full-history (não-causal): aceitável porque é **só display** (não entra em
  walk-forward); é exatamente a leitura "onde estamos vs toda a história" que o gráfico mostra.
- Próximo possível: completar o composto da Bloomberg (Mkt Cap/PIB via FRED quando alcançável,
  P/S etc.) — o CAPE já captura o essencial.
