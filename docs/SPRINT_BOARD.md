# Sprint Board — Cockpit Unificado

Board operacional. Detalhe e justificativa no `PRD_COCKPIT_UNIFICADO.md`.
Agendado para continuar **21/06/2026 13:00** pela Sprint B.

## DONE (sessao 21/06 manha)
- [x] Fix bug regime 1-cor: `serialize_signals` reconstroi regime por barra
      (trades entry/exit + MA200). BTC real: BULL 415 / BEAR 400 / OUT 302.
- [x] Zonas de regime no `MainChart.tsx` (histograma colorido por regime).
- [x] Inflection markers nos pontos de mudanca de regime.
- [x] `RiskGauge.tsx` (Strong Off->On + last inflection point).
- [x] `RegimeTimeline.tsx` (barra de cores historica).
- [x] `BuffettJr.list_sessions()` + `get_history()` + param `focus_asset` no chat.
- [x] 24/24 testes verdes (buffett/serial/api).

## DONE (sessao 21/06 — Sprint B: Buffett Jr no cockpit)
- [x] `app/api/buffett.py` — lazy singleton + 4 endpoints (chat/sessions/history/session),
      degrada gracioso 503 com msg acionavel (sugere GROQ/GEMINI key).
- [x] Router montado em `app/api/main.py`.
- [x] Frontend: types + client (sendChat/fetchSessions/fetchHistory/newSession).
- [x] `BuffettChat.tsx` — bolhas, input Enter, "pensando...", erro amigavel.
- [x] Sidebar de historico (titulo=1a msg, nova conversa, selecionar carrega).
- [x] Foco na tela: `selected` vai como `asset` -> Buffett "ve" o ativo.
- [x] Layout: chat como coluna direita (lg:block, w-360).
- [x] VALIDADO browser: sidebar lista 4 conversas reais; carregar "Vale segurar
      meu BTC" (32 msgs) renderiza resposta real com voz gaucha + linha vermelha.
- [x] 149/149 testes verdes, console limpo.

### BLOQUEIO Sprint B — RESOLVIDO (21/06 loop 13h, autonomo)
- Causa raiz dupla: (1) gemini CLI gratuito aposentado (IneligibleTierError);
  (2) chamadas HTTP caiam em 403 Cloudflare (erro 1010) por usarem o User-Agent
  padrao do urllib ("Python-urllib/*"), tratado como bot.
- FIX (commit d120441): User-Agent explicito nos provedores HTTP (Groq/Gemini/
  Moonshot) + cascade reordenado (Groq primeiro, gemini CLI por ultimo).
- GROQ_API_KEY criada no console.groq.com (free tier) e gravada no .env (local,
  nao versionado). Chat VALIDADO ponta a ponta: HTTP 200, resposta real com voz
  gaucha + dados reais (regime/MVRV/decisao do dia/mercado preditivo), linha
  vermelha intacta. Latencia: 1a chamada ~47s (monta WFA dos 6 ativos, cache 6h),
  seguintes ~18s (RAG+predictive por query). 149 testes verdes.

## DONE (sessao 21/06 — Sprint C: auditoria aplicada)
- [x] A1 legenda de cores fixa abaixo do grafico (RegimeLegend.tsx) — pedido do Bruno.
- [x] A2 dessaturar vermelho BEAR (tons Glassnode, menos alarme) no MainChart.
- [x] A4 linha de decisao no topo (DecisionBar.tsx): ativo->regime->acao->postura->
      ambiente. Linguagem de ESTADO ("sistema fora"), nao ordem. Commit 50eb939.
- [x] M1 markers de entrada/saida (seta verde compra / vermelha venda, por
      transicao de in_position; menos poluicao). Commit 2ee43de.
- [x] M2 subtitulo de acao no Risk Gauge ("sistema fora — preserva capital").
- [x] M3 esconder watermark TradingView (attributionLogo:false em MainChart+MacroPanel).

## DONE (sessao 21/06 — Prioridade 3: verificacao adversarial read-only)
- [x] Linha vermelha: NENHUMA violacao. engine/ diff vazio (intocado); serialize_signals
      sem look-ahead (classifica por barra, trailing so na ultima); DecisionBar/RiskGauge
      = estado, nao ordem; sem previsao de preco.
- [x] Seguranca/edge cases: history inexistente->[]/200; message vazia->400; sem
      campo->422; SQL com placeholders (sem injection); XSS protegido (texto puro
      do React, sem dangerouslySetInnerHTML); postJSON trata detail.error.

## NEXT (baixo valor / bloqueado)
- [ ] M4 ritmo do eixo X. N1 header no scroll. N3 valor atual nos MacroPanels (nits).
- [ ] Sprint D Glassnode: BLOQUEADA por dados (decidir fonte com Bruno; nao mockar).
- [ ] PENDENTE BRUNO: revisar e dar OK p/ PUSH (4 commits na branch, nada pushado).

## BLOCKED (Sprint D: Glassnode)
- [ ] Precisa fonte de dados (API key paga ou metricas publicas). Sem dado real
      o seletor fica disabled — nao mockar. Decidir fonte com o Bruno.

## NOTAS
- Motor k=3 INTOCAVEL. Front/API so leem.
- Commits: Bruno Liberato Girardi, sem footer IA. `db/`/`reports/` gitignored.
- Rodar local: `uvicorn app.api.main:app --port 8502 --reload` +
  `cd app/frontend && npm run dev` (porta 3000, proxy /api -> 8502).
