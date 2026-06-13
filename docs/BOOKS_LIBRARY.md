# Biblioteca do Buffett Brain — curadoria

A literatura do brain vive em `docs/books/*.md` como **conhecimento destilado** (ideias-chave
acionáveis das obras, escritas para o projeto — não cópia/redistribuição dos livros). O
RagIndex indexa esses `.md` automaticamente; o Buffett Jr recupera por relevância à pergunta.

## Por que destilado, e não os PDFs

Vários repositórios de "listas de livros" hospedam PDFs de obras sob copyright (pirataria).
Não redistribuímos esses arquivos. Em vez disso, destilamos as **ideias** (que são fato, não
texto protegido) — o que é melhor para o RAG: denso, limpo, sem ruído de formatação. Material
genuinamente livre (cartas da Berkshire, "Big Debt Crises"/"Principles" e "How the Economic
Machine Works" do Dalio, memos do Howard Marks, ARK research, e domínio público como
*Reminiscences of a Stock Operator* e *Madness of Crowds*) pode ser adicionado como `.txt`/`.pdf`
quando a rede permitir.

## Varredura das fontes (7 repos)

| Fonte | Tipo | Decisão |
|---|---|---|
| si74/financial-reading-list | lista iniciante | extraídos os clássicos; descartado ruído (Dummies, FIRE, YouTube) |
| greyblake/humble-investing | lista value | curadoria boa — aproveitada |
| mr-karan/awesome-investing | awesome-list | melhor curadoria — base do consenso |
| bharaniabhishek123/some-investment-books | PDFs | só títulos lidos; maioria é trading/forex (ruído) — destilados os clássicos |
| manjunath5496/Best-Investing-Books | PDFs genéricos | curadoria não confiável — ignorado |
| blicenses/ae | **spam** ("baixe ebook grátis" → site pirata) | **descartado** |
| aalhour/brains (Zen-Of-Capital) | PDFs Dalio (oficiais grátis) + zen.md | ideias do Dalio destiladas |

## Temas destilados (`docs/books/`)

- `value-investing.md` — Graham, Fisher, Klarman, Greenblatt, Pabrai, Greenwald
- `quality-moats-capital-allocation.md` — Buffett, Thorndike (The Outsiders)
- `mental-models-munger.md` — Munger, Bevelin, Cialdini
- `cycles-and-risk-marks.md` — Howard Marks
- `macro-debt-cycles-dalio.md` — Ray Dalio
- `behavioral-finance-uncertainty.md` — Kahneman, Montier, Taleb, Surowiecki
- `bubbles-manias-crises.md` — Mackay, Lefèvre, Shiller, Lowenstein, Lewis
- `trend-following-momentum.md` — Covel, Turtles, Antonacci, Schwager (núcleo do engine)
- `valuation-indexing-growth.md` — Damodaran, Bogle, Siegel, Lynch, Wood/ARK

## Removido por design (ruído)

Day-trading/forex/candlestick "for Dummies", binárias, astrologia financeira, "fique rico
em 15 min/semana", FIRE genérico, canais de YouTube e tudo que prega previsão de preço ou
atalho — incompatível com a filosofia do projeto (validar OOS, nunca prever).
