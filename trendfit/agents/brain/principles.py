"""Princípios destilados dos grandes investidores — knowledge base curada.

Conhecimento factual sobre as FILOSOFIAS de cada investidor (não cópia de obra).
É a sabedoria de fundo que o Buffett Jr usa pra raciocinar como um analista de
verdade: o que cada mestre olharia, o que o deixaria com medo, como ele pensa risco.

LINHA VERMELHA: isto INFORMA o julgamento do assessor — nunca vira sinal do engine.
O regime mecânico decide timing; estes princípios dão contexto e profundidade.
"""

from __future__ import annotations

# Cada investidor: filosofia central, princípios acionáveis, sinais de alerta que
# ele observaria, e tags pra recuperação por tema. Curado a partir de cartas,
# entrevistas e obras públicas — é descrição de filosofia, não reprodução de texto.
INVESTORS: dict[str, dict] = {
    "buffett": {
        "name": "Warren Buffett",
        "style": "value / qualidade",
        "core": (
            "Comprar negócios maravilhosos a preços justos e segurar por muito tempo. "
            "Preço é o que pagas, valor é o que recebes. O mercado é servo, não guia."
        ),
        "principles": [
            "Margem de segurança: só compre com folga grande entre preço e valor intrínseco.",
            "Círculo de competência: invista só no que entende; o resto é especulação.",
            "Seja medroso quando os outros são gananciosos e ganancioso quando há medo.",
            "Volatilidade não é risco; risco é perda permanente de capital.",
            "O melhor tempo de posse é 'para sempre' — deixe os juros compostos trabalharem.",
            "Não perca dinheiro (regra 1); não esqueça a regra 1 (regra 2).",
        ],
        "warnings": [
            "Euforia e narrativas de 'dessa vez é diferente'.",
            "Alavancagem — quebra quem estava certo no longo prazo.",
            "Pagar caro por crescimento futuro incerto.",
        ],
        "tags": ["value", "margem de seguranca", "longo prazo", "qualidade", "psicologia",
                 "risco", "buy and hold", "intrinseco"],
        "on_context": (
            "Buffett historicamente cético com cripto ('veneno de rato ao quadrado') por "
            "não gerar fluxo de caixa. No TrendFit, a leitura dele puxa pra disciplina, "
            "margem de segurança e ceticismo com euforia — não pra prever preço."
        ),
    },
    "munger": {
        "name": "Charlie Munger",
        "style": "value / modelos mentais",
        "core": (
            "Inverta sempre: pense no que pode dar errado e evite a estupidez. "
            "Latticework de modelos mentais de várias disciplinas."
        ),
        "principles": [
            "Inverta, sempre inverta: evitar o erro grosseiro vale mais que ser brilhante.",
            "Incentivos governam comportamento — siga o incentivo pra entender o agente.",
            "Espere com paciência; aja com convicção e tamanho quando a chance aparece.",
            "Conheça os limites do seu conhecimento; humildade epistêmica.",
        ],
        "warnings": [
            "Vieses: ancoragem, prova social, aversão à perda, excesso de confiança.",
            "Complexidade vendida como sofisticação.",
        ],
        "tags": ["modelos mentais", "inversao", "vieses", "psicologia", "incentivos",
                 "risco", "paciencia"],
        "on_context": (
            "Munger pede para inverter: 'o que destruiria esse capital?'. No contexto, "
            "ajuda o Buffett Jr a listar riscos de cauda antes de qualquer otimismo."
        ),
    },
    "graham": {
        "name": "Benjamin Graham",
        "style": "value / pai do value investing",
        "core": (
            "O investidor inteligente é realista que compra de pessimistas e vende a "
            "otimistas. Sr. Mercado é bipolar — use o humor dele, não o obedeça."
        ),
        "principles": [
            "Margem de segurança é o conceito central de todo investimento sólido.",
            "Distinga investimento (proteção do principal + retorno adequado) de especulação.",
            "Sr. Mercado oferece preços todo dia; você decide se usa — não é obrigado.",
            "Foque no valor do ativo, não na cotação de curto prazo.",
        ],
        "warnings": [
            "Confundir preço subindo com valor; comprar caro só porque sobe.",
            "Deixar a emoção do Sr. Mercado ditar a decisão.",
        ],
        "tags": ["value", "margem de seguranca", "sr mercado", "especulacao",
                 "psicologia", "valuation"],
        "on_context": (
            "Graham é a base do 'postura informa, regime decide': o preço de mercado "
            "(e o cone de apostas) é o Sr. Mercado — contexto, nunca ordem."
        ),
    },
    "dalio": {
        "name": "Ray Dalio",
        "style": "macro / ciclos de dívida",
        "core": (
            "Entenda a máquina econômica: ciclos de dívida de curto e longo prazo, "
            "produtividade e crédito. Diversifique de forma descorrelacionada."
        ),
        "principles": [
            "A economia é uma máquina: crédito + juros + produtividade movem os ciclos.",
            "Grandes ciclos de dívida terminam em desalavancagem — saiba em que fase está.",
            "Liquidez (M2, balanço dos bancos centrais) move ativos de risco no agregado.",
            "Diversificação descorrelacionada é o 'santo graal' de reduzir risco sem cortar retorno.",
            "Não lute contra os bancos centrais; entenda o que eles serão forçados a fazer.",
            "Tenha princípios escritos e teste-os contra a realidade — radical open-mindedness.",
        ],
        "warnings": [
            "Topo de ciclo de dívida com crédito esticado e juros subindo.",
            "Liquidez secando (aperto monetário) com ativos de risco caros.",
            "Concentração — apostar tudo numa só tese macro.",
        ],
        "tags": ["macro", "ciclos", "divida", "liquidez", "m2", "juros", "diversificacao",
                 "bancos centrais", "inflacao", "deflacao", "desalavancagem"],
        "on_context": (
            "Dalio é o pilar macro do Buffett Jr: M2/liquidez, fase do ciclo de dívida, "
            "postura dos bancos centrais. Ajuda a ler o pano de fundo do BTC/SP500 — "
            "sempre como leitura de ambiente, jamais previsão de preço."
        ),
    },
    "marks": {
        "name": "Howard Marks",
        "style": "ciclos / risco / segundo nível",
        "core": (
            "Você não pode prever, mas pode se preparar. Onde estamos no ciclo importa "
            "mais que prever o próximo passo. Pense em segundo nível."
        ),
        "principles": [
            "Pensamento de segundo nível: o que o consenso já precifica? Onde ele erra?",
            "Não dá pra prever, dá pra saber em que ponto do ciclo (pêndulo) estamos.",
            "Risco é a probabilidade de perda, não a volatilidade — e mora no preço pago.",
            "Os maiores riscos vêm quando todos acham que não há risco (complacência).",
            "Comprar bem é metade do jogo: o preço de entrada define o risco.",
        ],
        "warnings": [
            "Complacência generalizada, prêmio de risco comprimido, crédito fácil.",
            "Narrativa unânime — quando ninguém vê risco, o risco está no topo.",
        ],
        "tags": ["ciclos", "risco", "segundo nivel", "psicologia", "pendulo",
                 "sentimento", "complacencia", "valuation"],
        "on_context": (
            "Marks dá ao Buffett Jr o 'onde estamos no ciclo' e o pensamento de segundo "
            "nível para ler o cone de apostas (o que a multidão já precifica)."
        ),
    },
    "burry": {
        "name": "Michael Burry",
        "style": "contrarian / deep value / cauda",
        "core": (
            "Faça o trabalho que ninguém faz, encontre o desajuste que ninguém vê, e "
            "aguente a dor de estar certo cedo demais. Foco em risco de cauda."
        ),
        "principles": [
            "Pesquisa independente e profunda — desconfie do consenso preguiçoso.",
            "O mercado pode ficar irracional mais tempo do que parece; dimensione pra aguentar.",
            "Procure assimetrias: pouco a perder, muito a ganhar (ou o inverso a evitar).",
            "Bolhas se formam em excesso de crédito e alavancagem escondida.",
        ],
        "warnings": [
            "Alavancagem sistêmica escondida; passivos que ninguém está olhando.",
            "Manias especulativas com entrada de varejo no topo.",
            "Iliquidez disfarçada — sair é fácil até não ser.",
        ],
        "tags": ["contrarian", "cauda", "bolha", "alavancagem", "liquidez", "risco",
                 "assimetria", "pesquisa"],
        "on_context": (
            "Burry é o radar de risco de cauda do Buffett Jr: a pergunta 'e se quebrarem "
            "o BTC?' é puro Burry — procurar a fragilidade que o modelo mecânico não vê."
        ),
    },
    "wood": {
        "name": "Cathie Wood",
        "style": "growth / inovação disruptiva",
        "core": (
            "Inovação disruptiva (IA, genômica, blockchain, energia) cresce de forma "
            "exponencial e é subprecificada por modelos lineares. Horizonte de 5+ anos."
        ),
        "principles": [
            "Curvas de custo em queda destravam adoção exponencial (lei de Wright).",
            "O mercado subestima tecnologias de plataforma no início da curva-S.",
            "Convicção de longo prazo: tese vale mais que a volatilidade do caminho.",
            "Realoca para as maiores convicções quando o mercado pune indiscriminadamente.",
        ],
        "warnings": [
            "Pagar qualquer preço por crescimento; ignorar caminho de fluxo de caixa.",
            "Concentração e correlação alta entre teses 'diferentes'.",
            "Sensibilidade a juros — growth de duration longa sofre com aperto.",
        ],
        "tags": ["growth", "inovacao", "ia", "tecnologia", "longo prazo", "disrupcao",
                 "curva de custo", "juros"],
        "on_context": (
            "Wood traz o lado growth/inovação — útil pra ler rotação cripto→IA (QQQ/SOXX) "
            "como tese de longo prazo, sempre separando convicção de timing (do regime)."
        ),
    },
}

# Síntese transversal: o que TODOS concordam (o consenso dos mestres) — âncora do agente.
SHARED_WISDOM: list[str] = [
    "Risco é perda permanente de capital, não oscilação de preço.",
    "Preço de entrada e margem de segurança definem o risco assumido.",
    "Psicologia de manada cria as melhores e as piores oportunidades.",
    "Ninguém prevê o futuro de forma confiável; prepare-se em vez de prever.",
    "Sobreviver vem antes de prosperar — proteja o capital pra continuar no jogo.",
    "Saiba em que fase do ciclo (mercado, crédito, liquidez) você está.",
]


def _tokens(text: str) -> set[str]:
    """Tokeniza simples (minúsculas, sem pontuação) pra casar tags."""
    out: set[str] = set()
    for raw in text.lower().split():
        tok = "".join(ch for ch in raw if ch.isalnum())
        if len(tok) >= 3:
            out.add(tok)
    return out


def relevant_investors(query: str, limit: int = 3) -> list[str]:
    """Seleciona os investidores mais relevantes à pergunta por casamento de tags.

    Sempre retorna ao menos `limit` (preenche com os pilares se a query não casar)."""
    q = _tokens(query)
    scored: list[tuple[int, str]] = []
    for key, data in INVESTORS.items():
        score = 0
        for tag in data["tags"]:
            if _tokens(tag) & q:
                score += 1
        # nome do investidor citado na pergunta puxa forte
        if _tokens(data["name"]) & q:
            score += 5
        scored.append((score, key))

    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = [k for s, k in scored if s > 0][:limit]
    if not chosen:
        # sem casamento: pilares default (value + macro + risco/ciclo)
        chosen = ["buffett", "dalio", "marks"][:limit]
    return chosen


def principles_context(query: str, limit: int = 3) -> str:
    """Monta o trecho de princípios relevantes pra injeção no system prompt."""
    keys = relevant_investors(query, limit=limit)
    blocks: list[str] = []
    for key in keys:
        d = INVESTORS[key]
        princ = "; ".join(d["principles"][:4])
        warn = "; ".join(d["warnings"][:2])
        blocks.append(
            f"  {d['name']} ({d['style']}): {d['core']} "
            f"Princípios: {princ}. Alerta: {warn}. Leitura no contexto: {d['on_context']}"
        )
    shared = " | ".join(SHARED_WISDOM)
    return "Consenso dos mestres: " + shared + "\n" + "\n".join(blocks)
