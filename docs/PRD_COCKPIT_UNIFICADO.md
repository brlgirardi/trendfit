# PRD — Cockpit Unificado TrendFit + Buffett Jr

> Documento de produto do cockpit React unificado. Junta o **motor TrendFit**
> (regime k=3, walk-forward honesto) com o **Buffett Jr** (assessor conversacional
> com second brain) numa única tela operacional. Visão Glassnode Vector: zonas de
> regime, risk gauge, inflection points, chat do assessor com histórico.
>
> **Regra-mãe (linha vermelha):** o sistema INFORMA e ACONSELHA. Regime decide
> timing (motor mecânico validado OOS), Bruno decide a ação. O agente nunca aciona
> sinal nem prevê preço/probabilidade. WFA sempre sem look-ahead.

---

## 1. Visão — uma coisa só

Hoje existem duas frentes que o Bruno olha separado:
- **TrendFit** (motor): regime, postura, walk-forward, zonas — o "o que" e o "quando".
- **Buffett Jr** (assessor): le o mesmo data layer, da opiniao com sabedoria dos
  mestres, ve portfolio e mercado preditivo — o "por que" e o "como pensar".

**Objetivo:** fundir as duas numa tela so. O Bruno abre o cockpit, ve o sistema no
grafico (zonas + inflexoes + risk gauge), e conversa com o Buffett Jr ali do lado —
o assessor enxerga exatamente o que esta na tela (ativo em foco) e aconselha. WFA
roda para todos os ativos sob demanda. Uma experiencia, nao duas.

### Jobs To Be Done
- **JTBD-1:** "Quando abro o cockpit, quero ver de imediato em que regime cada
  ativo esta e qual a minha postura — para decidir se ajo hoje."
- **JTBD-2:** "Quando estou em duvida sobre um ativo, quero perguntar ao Buffett Jr
  e ele ja saber o que estou olhando — para ter um conselho fundamentado sem repetir
  contexto."
- **JTBD-3:** "Quando volto depois de dias, quero retomar conversas anteriores com o
  assessor — para acompanhar a evolucao das teses."

---

## 2. Estado atual (o que ja esta no ar)

Servidores locais: **FastAPI** `localhost:8502` + **React/Vite** `localhost:3000`.
Streamlit legado (`localhost:8501`) segue como referencia.

| Camada | Componente | Status |
|---|---|---|
| Backend | `app/api/main.py` — `/api/health,/assets,/data/{asset},/macro` | OK no ar |
| Backend | `app/api/serializers.py` — OHLCV, signals, postura, walkforward | OK regime historico por barra (corrigido) |
| Frontend | `MainChart.tsx` — candles + zonas de regime + inflection markers | OK no ar |
| Frontend | `RiskGauge.tsx` — Strong Off -> Strong On + last inflection | OK no ar |
| Frontend | `RegimeTimeline.tsx` — barra de cores historica | OK no ar |
| Frontend | `PostureBadge` / `LeverageBadge` — postura + alavancagem | OK no ar |
| Frontend | `MacroPanel` — FNG, MVRV, VIX, US10Y | OK no ar |
| Backend | `BuffettJr` — chat + memoria SQLite + `list_sessions`/`get_history`/`focus_asset` | OK pronto (falta endpoint) |
| Backend | `app/api/buffett.py` — endpoints REST de chat | PENDENTE proximo |
| Frontend | `BuffettChat.tsx` — painel de chat + historico de sessoes | PENDENTE proximo |
| Frontend | Seletor Glassnode | BLOQUEADO disabled ("coming soon") — sem mock |

### Correcao entregue nesta sessao (bug de regime)
O serializer aplicava o regime **atual** a todas as ~1117 barras (grafico
inteiro de uma cor so). Agora `serialize_signals` reconstroi o regime historico
por barra a partir dos `trades` (entry/exit) + MA200 (distingue BEAR de OUT).
Resultado real BTC: **BULL 415 - BEAR 400 - OUT 302**. Zonas e timeline agora
refletem a historia verdadeira do sistema.

---

## 3. Auditoria UX — Nielsen + psicologia cognitiva + objetivos

Audit visual com browser real (Pixel) sobre o estado atual. Cada achado tem
heuristica violada, o porque psicologico e a acao. Priorizado por impacto na
**decisao do Bruno**.

### Criticos (atacam a decisao)

**A1 — Falta legenda de cores das zonas.** *(Nielsen #2 "match com o mundo real",
#6 "reconhecer > lembrar")*
O Bruno pediu explicitamente "abaixo a legenda das cores". A timeline bar mostra
azul/vermelho/rosa mas sem dizer o que cada um significa. Sem legenda, o usuario
precisa **lembrar** o codigo de cores — carga cognitiva desnecessaria.
-> **Acao:** legenda fixa abaixo do grafico: Risk-On forte (azul escuro) - Risk-On
(azul claro) - Risk-Off/BEAR (vermelho) - Neutro/OUT (rosa).

**A2 — Vermelho saturado demais gera alarme constante.** *(Psicologia: vies de
negatividade / ansiedade de cor)*
A zona BEAR usa vermelho forte cobrindo grande area — vermelho = perigo, dispara
resposta de estresse mesmo quando a leitura e so "fora da posicao". Glassnode usa
tons dessaturados. -> **Acao:** baixar saturacao/opacidade do BEAR; reservar
vermelho vivo so para o marker de saida, nao para a area inteira.

**A3 — Buffett Jr ausente da tela.** *(Objetivo do produto / JTBD-2)*
O assessor e metade do sistema e nao esta no cockpit. -> **Acao:** painel de chat
(sprint atual).

**A4 — Decisao do dia nao esta em destaque no topo.** *(Nielsen #1 "visibilidade
do status"; Streamlit ja fazia isso)*
O badge "MUITO RUIM 0%" aparece mas sem o "o que fazer agora" explicito ao lado.
-> **Acao:** linha de decisao no topo: ativo -> regime -> acao recomendada -> postura.

### Medios (atrito, nao bloqueio)

**M1 — Inflection markers poluidos e sem rotulo.** Muitas bolinhas sobrepostas;
nao da pra ler entrada vs saida. -> agrupar/filtrar e legendar (entrada = triangulo
verde p/ cima, saida = triangulo vermelho p/ baixo).
**M2 — Risk Gauge nao conecta com acao.** Diz "STRONG RISK-OFF" mas nao amarra ao
que isso significa pra carteira. -> subtitulo de 1 linha ("sistema fora — preserva
capital").
**M3 — Watermark "TV" do TradingView** nos cantos dos charts — ruido visual.
-> esconder via config do `lightweight-charts`.
**M4 — Eixo X com labels soltos** ("jun." "2024" "jul.") — ritmo irregular.

### Nits (polimento)
N1 — Header corta no scroll. N2 — Subplot CAPE ainda sem nota "OOS congelada".
N3 — MacroPanels poderiam ter valor atual no canto (ultimo ponto).

---

## 4. Sprints

### Sprint A — Zonas & Risk Gauge - FEITO (esta sessao)
- [x] `serialize_signals` regime historico por barra (fix do bug 1-cor)
- [x] Zonas de regime no MainChart (histograma colorido)
- [x] Inflection markers (mudanca de regime)
- [x] RiskGauge (Strong Off->On + last inflection point)
- [x] RegimeTimeline bar
- [x] 24/24 testes verdes (buffett/serial/api)

### Sprint B — Buffett Jr no cockpit - EM ANDAMENTO (continuar 13:00)
- [x] `BuffettJr.list_sessions()` + `get_history()` + `focus_asset`
- [ ] `app/api/buffett.py`: `POST /api/buffett/chat` (message, session, asset),
      `GET /api/buffett/sessions`, `GET /api/buffett/history/{session}`,
      `POST /api/buffett/session` (nova)
- [ ] Montar router no `main.py` com lazy singleton do BuffettJr
- [ ] `BuffettChat.tsx`: bolhas de mensagem, input, indicador "digitando"
- [ ] Sidebar de historico de sessoes (lista + nova conversa + selecionar)
- [ ] Passar `selected` (ativo em foco) no payload -> "ele ve a tela"
- [ ] Layout: chat como coluna/drawer a direita do grafico
- [ ] Smoke test: pergunta generica responde sobre o ativo em foco

### Sprint C — Auditoria UX aplicada - PROXIMA
- [ ] A1 legenda de cores fixa abaixo do grafico
- [ ] A2 dessaturar vermelho BEAR (tons Glassnode)
- [ ] A4 linha de decisao no topo (ativo->regime->acao->postura)
- [ ] M1 markers legendados (entrada / saida)
- [ ] M2 subtitulo de acao no Risk Gauge
- [ ] M3 esconder watermark TradingView
- [ ] Re-audit com browser real, comparar antes/depois

### Sprint D — Glassnode (de-para) - BLOQUEADA por dados
- [ ] Definir fonte: API key Glassnode (paga) ou metricas publicas equivalentes
- [ ] Ingerir no pipeline `trendfit.cockpit` (com key em `.env`, nunca commit)
- [ ] `/api/data/{asset}?system=glassnode` (mesmo shape JSON)
- [ ] Habilitar seletor; de-para lado a lado TrendFit x Glassnode
- **Nota:** mantem disabled enquanto nao ha dado real. Botao cinza > sinal falso.

### Sprint E — WFA multi-ativo visivel - PARCIAL
- [x] WFA ja roda por ativo em `/api/data/{asset}` (sob demanda, ~2s/ativo)
- [ ] Indicador de "recalculando WFA" ao trocar de ativo (status visivel)
- [ ] (opcional) pre-aquecer cache dos 6 ativos em background

---

## 5. Metricas de sucesso
- **Decisao mais rapida:** tempo ate "sei minha postura hoje" < 5s ao abrir.
- **Conselho contextual:** Buffett Jr responde pergunta generica ja focado no ativo
  da tela em >=90% dos casos (smoke test).
- **Continuidade:** retomar conversa anterior em 1 clique na sidebar.
- **Zero look-ahead:** WFA OOS congelado; nenhuma cor/sinal usa dado futuro.

---

## 6. Riscos & guarda-corpos
- **Motor k=3 INTOCAVEL** (`trendfit/engine/`). Front e API so leem a saida.
- **`.env` nunca commitado.** Keys (LLM, Glassnode) ficam locais.
- **`db/` e `reports/` gitignored.** Nunca `git add -A`.
- **Chat depende de LLM:** cascade usa gemini CLI (OAuth, custo zero) como 1a
  opcao; degrada com mensagem clara se nenhum provider disponivel.
- **Commits:** Bruno Liberato Girardi, sem footer de IA.

---

## 7. Plano da continuacao (agendado 13:00)
Retomar pela **Sprint B** (Buffett Jr no cockpit) — backend ja 1/3 pronto:
1. `app/api/buffett.py` + router no main + lazy singleton.
2. `BuffettChat.tsx` + sidebar de historico + foco no ativo da tela.
3. Smoke test com browser real (pergunta generica -> responde sobre o ativo).
4. Em seguida **Sprint C** (auditoria aplicada) e re-audit comparativo.
Estado salvo neste PRD; backlog detalhado em `docs/SPRINT_BOARD.md`.
