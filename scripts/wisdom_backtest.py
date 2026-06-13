"""Backtest de SABEDORIA do Buffett Jr — ele identificaria as grandes crises?

Ideia (pedido do Bruno): testar, estilo walk-forward, se o framework de princípios
do Buffett Jr levanta a bandeira de risco em momentos que ANTECEDERAM crises —
usando só os sinais conhecidos NA ÉPOCA, sem revelar o desfecho ao agente.

HONESTIDADE METODOLÓGICA (lê isto antes de tirar conclusão):
- Um LLM CONHECE a história — ele "sabe" que 2000 e 2008 foram crises. Então os
  cenários históricos NÃO provam previsão cega; provam que o FRAMEWORK (Graham,
  Marks, Burry, Dalio) aponta os sinais de risco que de fato estavam presentes.
- O teste honesto de previsão é o cenário ATUAL (hoje): a leitura é registrada
  agora, sem desfecho conhecido por ninguém, pra conferir no futuro. Isso sim é WFA.

Uso: python scripts/wisdom_backtest.py   (consome o LLM via cascade; precisa de
gemini CLI logado ou API key). Não é teste automatizado (depende de rede/LLM).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trendfit.agents.brain import BuffettBrain  # noqa: E402
from trendfit.agents.llm_provider import CascadeProvider  # noqa: E402

# Cada cenário: fatos PÚBLICOS conhecidos até a data (sem desfecho). O "aftermath"
# é só pra MINHA conferência depois — NUNCA entra no prompt do agente.
SCENARIOS = [
    {
        "name": "Bolha dotcom",
        "as_of": "dezembro de 1999",
        "facts": (
            "CAPE (Shiller P/E) do S&P 500 perto de 44 — máxima histórica, acima até "
            "do pico de 1929. Nasdaq subiu ~85% no ano. Enxame de IPOs de empresas sem "
            "lucro e sem receita relevante, avaliadas em múltiplos altíssimos de vendas. "
            "Narrativa dominante: 'a internet muda tudo, esta vez é diferente'. "
            "Day-trading de varejo viral. Prêmio de risco de ações historicamente baixo."
        ),
        "aftermath": "Nasdaq caiu ~78% (2000-2002), S&P ~49%. Bolha estourou.",
    },
    {
        "name": "Bolha imobiliária / subprime",
        "as_of": "julho de 2007",
        "facts": (
            "Preços de imóveis nos EUA quase dobraram em ~6 anos. Explosão de hipotecas "
            "subprime e 'NINJA loans'. Securitização em CDOs com alavancagem bancária "
            "altíssima. Spreads de crédito muito comprimidos (complacência), VIX baixo. "
            "Primeiros sinais de inadimplência subprime e dois fundos da Bear Stearns "
            "com problemas. Consenso: risco está 'diluído e distribuído'."
        ),
        "aftermath": "Crise global 2008: S&P caiu ~57% até mar/2009; Lehman quebrou.",
    },
]

_PERSONA = (
    "Você é o Buffett Jr, analista com a sabedoria destilada de Graham, Warren Buffett, "
    "Charlie Munger, Howard Marks, Ray Dalio e Michael Burry. Você é cético, pensa em "
    "ciclos, risco de cauda e margem de segurança."
)

_RULES = (
    "REGRA DO TESTE (inegociável): ESTAMOS EM {as_of}. Você só conhece o que era público "
    "ATÉ essa data. NÃO use conhecimento de eventos posteriores — isso seria trapaça e "
    "invalida o teste. Responda como se vivesse o momento.\n\n"
    "Entregue, curto e direto:\n"
    "1) NÍVEL DE ALERTA DE RISCO de 1 (tranquilo) a 10 (perigo extremo).\n"
    "2) Qual mestre/princípio embasa (ciclo, margem de segurança, risco de cauda...).\n"
    "3) O que você faria com capital exposto a esse mercado."
)


def run_scenario(llm: CascadeProvider, brain: BuffettBrain, sc: dict) -> str:
    wisdom = brain.recall(f"{sc['name']} valuation ciclo risco bolha crédito").as_prompt_block()
    system = (
        f"{_PERSONA}\n\n{wisdom}\n\n"
        + _RULES.format(as_of=sc["as_of"])
    )
    user = (
        f"FATOS PÚBLICOS CONHECIDOS ATÉ {sc['as_of']}:\n{sc['facts']}\n\n"
        f"Qual sua leitura de risco agora ({sc['as_of']})?"
    )
    return llm.complete(system, [{"role": "user", "content": user}])


def main() -> None:
    llm = CascadeProvider()
    brain = BuffettBrain()

    for sc in SCENARIOS:
        print("=" * 78)
        print(f"CENÁRIO: {sc['name']} — {sc['as_of']}")
        print("=" * 78)
        try:
            print(run_scenario(llm, brain, sc))
        except Exception as exc:
            print(f"[falha no LLM: {exc}]")
        print(f"\n>>> DESFECHO REAL (só pra conferência, não foi dado ao agente): {sc['aftermath']}\n")


if __name__ == "__main__":
    main()
