# Trend following e momentum — o núcleo operacional

Síntese de Covel (Trend Following; The Complete TurtleTrader), Faith (Way of the Turtle),
Antonacci (Dual Momentum), Schwager (Market Wizards), Lefèvre (Reminiscences). Ideias
destiladas. É o pilar mais próximo do motor do TrendFit.

## Princípios do trend following
- **Não preveja, reaja.** Você não sabe quanto uma tendência vai durar; siga o preço, que
  é a única verdade. O sistema entra na direção da tendência e sai quando ela vira.
- **Corte as perdas, deixe os lucros correrem.** A assimetria é tudo: muitas perdas pequenas,
  poucos ganhos grandes. A esperança no perdedor e o medo no vencedor destroem o edge.
- **Gestão de risco e tamanho de posição** importam mais que o sinal de entrada. Arrisque uma
  fração pequena por trade; sobreviva às sequências de perda (que são inevitáveis).
- **Edge estatístico, não acerto individual.** O resultado vem da repetição disciplinada de
  uma regra com expectativa positiva — não de "estar certo" numa trade.
- **Drawdown é o custo do negócio.** Períodos de chop/perda fazem parte; abandonar o sistema
  no drawdown é o erro clássico.

## Turtles (Dennis & Eckhardt) — sistema pode ser ensinado
- Regras mecânicas e explícitas: entrada por rompimento (Donchian), stops por volatilidade
  (ATR), piramidação, saída por canal oposto. Disciplina > intuição.
- A lenda mostrou que **seguir as regras** separava os vencedores dos perdedores — não talento.

## Antonacci — Dual Momentum
- **Momentum relativo** (escolher o ativo mais forte) + **momentum absoluto** (só ficar
  comprado se o ativo bate o caixa/T-bills). O absoluto é o filtro que tira você do mercado
  em bear, reduzindo drawdown.

## Market Wizards (Schwager) — o que os melhores têm em comum
- Método próprio testado + disciplina férrea + gestão de risco + controle emocional.
- "Não há um jeito certo; há o jeito que combina com você e que você segue de fato."
- Eles cortam perdas sem ego e escalam ganhadores.

## Aplicação no contexto do TrendFit
- Esse é o DNA do engine do TrendFit (ensemble Donchian/HiLo + veto de regime + trailing
  ATR + walk-forward). A literatura aqui CONFIRMA a filosofia do motor: seguir tendência,
  cortar perda, proteger drawdown, não prever. **Reforço importante:** validar OOS sem
  look-ahead e não fazer overfit — adicionar parâmetro olhando o resultado é o erro que o
  projeto já refutou várias vezes. O assessor entende isso e nunca empurra o engine a
  "prever"; o regime decide o timing, o Bruno decide a ação.
