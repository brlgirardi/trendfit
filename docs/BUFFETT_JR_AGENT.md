# Buffett Jr — Agente conversacional (assessor com second brain)

**Código:** `trendfit/agents/` (`buffett_jr.py`, `llm_provider.py`, `brain/`, `rag.py`).
**Não confundir** com `docs/BUFFETT_JR.md` (a *postura por critérios* em `allocation.py`,
que segue sendo a fonte do eixo POSTURA). Este documento é o **agente que conversa**.

## O que é

Um assessor de investimentos conversacional, de voz gaúcha, que **informa e opina com
convicção** — mas **nunca decide por ti**. Ele junta os dados reais do TrendFit, a
sabedoria dos grandes investidores e pesquisa ao vivo pra te dar uma leitura franca
("bah, eu venderia, tá arriscado"), e devolve a decisão pra ti.

### Linha vermelha (inegociável)

- **Engine ≠ assessor.** O engine (regime/walk-forward) é mecânico, validado OOS, decide
  *timing* — e **não muda**. O Buffett Jr é a camada de **julgamento**: opina, projeta
  cenários, pesa risco. Nunca aciona ordem, nunca alimenta o engine.
- **Opina, não ordena.** "Eu faria X" é o papel dele; "faça X agora" não é. A decisão é
  sempre do Bruno.
- **Projeção é opinião falível**, marcada como tal — não o sinal do sistema, não certeza.
- Cone de apostas = espelho da multidão; valuation = histórico. Contexto, nunca previsão.

## Arquitetura (camadas)

```
BuffettJr.chat(msg)                      # orquestra: memória + contexto + brain + LLM
├── memória SQLite (db/buffett_jr.db)    # histórico por sessão
├── contexto AO VIVO (data layer do cockpit, leitura do presente):
│   ├── portfolio Binance (get_portfolio_summary)
│   ├── panorama por ativo (asset_cockpit): regime + decisão + valuation CAPE/MVRV + postura
│   ├── ambiente macro (environment_now): FAVORÁVEL / MISTO / ADVERSO
│   └── mercado preditivo (market_cone): cone Kalshi + Polymarket
├── BuffettBrain.recall(query)           # second brain (ver abaixo)
└── LLMProvider (cascade)                # GeminiCLI → Gemini/Moonshot/Groq (HTTP)
    └── busca web ao vivo (Fed, CPI, juros, M2, geopolítica) via gemini CLI
```

### LLM cascade (`llm_provider.py`)

`CascadeProvider` tenta na ordem, com failover automático e skip de quem não tem credencial:

1. **GeminiCliProvider** — usa o `gemini` CLI local (login OAuth Google): **custo zero,
   sem API key**. Stateless por invocação (serializa system+histórico no stdin).
   - **Segurança:** o CLI traz tools de filesystem ligadas; rodamos em diretório
     temporário **vazio** + `--approval-mode plan` (read-only). Vazamento de filesystem
     fechado e comprovado em teste.
   - **Busca web:** o modo `plan` permite a tool de busca sem prompt interativo — o
     agente pesquisa dados/notícias atualizados **sem** reabrir escrita ao filesystem.
2. **GeminiProvider / MoonShotProvider / GroqProvider** — via HTTP, por API key no `.env`
   (`GEMINI_API_KEY`, `MOONSHOT_API_KEY`, `GROQ_API_KEY`). Fallback.

### Second brain (`brain/`) — microsserviço-ready

Contrato estável `recall(query) -> BrainResult` (`.to_dict()` JSON-serializável; pronto
pra virar serviço HTTP). Quatro pilares:

1. **Princípios destilados** (`principles.py`) — filosofia de 7 mestres (Buffett, Munger,
   Graham, Dalio, Marks, Burry, Wood): core, princípios acionáveis, sinais de alerta,
   tags. Seleção por relevância à pergunta. É a sabedoria de fundo.
2. **Literatura** (`rag.py` sobre `docs/books/`) — TF-IDF seguro sobre cartas/livros/memos.
   Degrada gracioso se vazio. *(Hoje vazio — ver roadmap.)*
3. **Macro** — hoje via **busca web** do agente (Fed, CPI, M2, etc.). *(Coletor estruturado
   FRED = roadmap.)*
4. **Memória de teses** (`theses.py`) — julgamento **adaptável**: registra a leitura
   (tese + alerta 1-10 + evidências), e quando o cenário muda, **reavalia** (confirma/
   refuta). `recall` traz as teses em aberto pra retestar.

## Validação

- **Suite:** `tests/test_buffett_jr.py` + `tests/test_brain.py` (provider/web mockados,
  sem rede). Toda a suite verde.
- **Backtest de sabedoria** (`scripts/wisdom_backtest.py`): testa se o framework levanta
  a bandeira de risco antes de crises, com os sinais conhecidos na época. Resultado:
  dotcom/1999 → alerta 10/10 (Marks+Buffett); subprime/2007 → 9/10 (Marks+Burry).
  **Ressalva honesta:** um LLM conhece a história — isso prova que o *framework* aponta
  os sinais certos, não previsão cega. O teste honesto de previsão é o cenário de hoje
  (registrar agora via memória de teses, conferir no futuro).

## Como usar

```python
from trendfit.agents import BuffettJr
jr = BuffettJr()                       # cascade default → gemini CLI (custo zero)
print(jr.chat("E aí, vale segurar meu BTC hoje?"))
```

Pré-requisitos: `gemini` CLI logado (OU uma API key no `.env`); para o portfolio real,
`BINANCE_API_KEY`/`SECRET` no `.env`. Sem nada disso, degrada gracioso e avisa.

## Limitações conhecidas e roadmap

- **Literatura (RAG) vazia:** baixar fontes legítimas (cartas Berkshire, Dalio
  Principles/Big Debt Crises oficiais grátis, memos Howard Marks, ARK research, Graham
  domínio público) para `docs/books/` — o RAG indexa automático. Bloqueio atual: a rede
  do ambiente de build não baixa; rodar no VPS (tem rede) ou dropar os PDFs no Mac.
- **Macro estruturado:** coletor FRED (M2, CPI, desemprego, PIB) para complementar a
  busca web com séries auditáveis. (FRED teve histórico de inalcançável — resolver.)
- **Busca web** pode trazer notícia de anos anteriores: mitigado com âncora de data no
  prompt (manda conferir o ano), mas vale validar as fontes citadas.
- **Microsserviço HTTP:** o Brain já tem contrato estável; falta expor como serviço.
- **UI:** chat ainda é via Python; integrar no cockpit (Streamlit) é a Task 3.
