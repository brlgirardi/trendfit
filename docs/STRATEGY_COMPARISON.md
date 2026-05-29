# Comparação de estratégias — diagnóstico de whipsaw e o que muda

**Data:** 2026-05-29
**Gatilho:** observação de que o sistema "vendeu na baixa e comprou na alta"
(whipsaw). Investigação trade-a-trade + teste de alternativas no walk-forward.

## 1. Diagnóstico do núcleo v1 (long-only breakout + veto MA200)

Rodando `scripts/diagnose_btc.py` sobre o OOS real (2021-08 → 2025-08):

- **18 round-trips, win rate 44%** (mais perdedores que vencedores).
- **39% dos trades duram ≤5 dias** ("pipoca"), com retorno médio **−2,4%**.
- **15 de 17 recompras foram a preço MAIOR que a saída anterior** → o clássico
  "vendeu na baixa, recomprou na alta", em 88% das vezes.
- Veto MA200 **virou 39 vezes** bull↔bear; preço passou **14% do tempo a <5% da MA200**
  (zona de chicote).

**Causa-raiz:** (1) breakout puro compra topo / vende fundo — ruim em mercado
lateral; (2) veto MA200 sem banda liga/desliga perto da linha.

## 2. Alternativas testadas (mesmo walk-forward, dados reais)

`scripts/compare_strategies.py`:

| Estratégia | Retorno | MaxDD | Sharpe | Calmar | Trades | vs B&H |
|---|---:|---:|---:|---:|---:|---:|
| v1 long-only (atual) | +106% | −29% | 0,72 | 0,69 | 18 | −52% |
| v2 long-only banda=3% | +85% | −25% | 0,65 | 0,66 | 11 | −73% |
| v2 long-only banda=5% | +91% | −25% | 0,68 | 0,70 | 10 | −67% |
| **v2 long-only banda=5% +cooldown 5d** | +93% | **−23%** | 0,69 | **0,79** | **10** | −64% |
| v3 long/short banda=3% | **−4%** | −48% | 0,19 | −0,02 | 19 | −162% |
| v3 long/short banda=5% | +8% | −45% | 0,26 | 0,04 | 17 | −150% |
| Buy & Hold | +158% | −77% | 0,71 | 0,35 | 0 | 0% |

*(Calmar = CAGR / |MaxDD|; retorno por unidade de drawdown — maior é melhor.)*

### Whipsaw: v1 vs v2

| Métrica | v1 | v2 (banda 5% + cooldown 5d) |
|---|---:|---:|
| Trades | 18 | 10 |
| Win rate | 44% | 50% |
| Trades-pipoca ≤5d | 7 | **0** |
| Recompra a preço maior que a saída | 15/17 | 7/9 |

## 3. Conclusões

**a) A banda anti-whipsaw funciona.** Elimina 100% dos trades-pipoca, reduz o
drawdown (−29% → −23%) e tem o melhor retorno/risco (Calmar 0,79 vs 0,35 do B&H).
Custo: ~13pp a menos de retorno bruto que o v1. Trade-off clássico risco×retorno.

**b) Short é uma armadilha no BTC — refutado pelos dados.** Adicionar venda a
descoberto derrubou o retorno (+106% → −4%/+8%) e **dobrou o drawdown** (−45%/−48%).
O BTC tem tendência estrutural de alta; shortar rema contra a maré e perde nas
explosões. Era uma intuição razoável que os dados desmentiram — exatamente o tipo
de erro que o projeto existe para pegar. **Não usar short no BTC.** Em ativos
mean-reverting (não-cripto) pode ser reavaliado.

## 4. Decisão (29-mai-2026)

**Padrão = v1** (escolha do dono do projeto: prioriza retorno bruto e Sharpe,
aceita o whipsaw). O v2 fica **selecionável** e validado:

```bash
python scripts/run_btc_sprint1.py                      # v1 (default)
python scripts/run_btc_sprint1.py profiles/btc_v2.json # v2 suave (anti-whipsaw)
```

Long/short permanece implementado (`StrategyConfig(mode="long_short")`) apenas
para experimentação — desaconselhado no BTC pelos números acima.
