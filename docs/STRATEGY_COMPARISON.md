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

---

## 5. Melhoria validada: "permanecer mais tempo na tendência" (núcleo v3)

Gatilho: o sistema nunca acerta topo/fundo e sai cedo demais. Trend-following NÃO
acerta topo/fundo (isso é mean-reversion, refutada via short). O que dá para
melhorar de verdade é **segurar a tendência** e **capturar mais da perna grande**.

Alavancas implementadas (`strategy.py`, mode `long_asym`):
- **Canal assimétrico**: entra no rompimento de `lb` dias, só sai no canal de
  `lb*asym` dias (saída mais larga → aguenta repiques, cavalga a tendência).
- **Trailing stop ATR** (chandelier): sai só quando a tendência realmente vira.

### Sweep exploratório (`scripts/improve_strategies.py`)

Vários valores de `asym` melhoram retorno E Sharpe sobre o v1 — sinal robusto de
que a direção está certa. O melhor combo chegou a +183% (Sharpe 0,97, PF 5,68).
**Porém esse número é otimista**: o `asym` foi escolhido olhando o OOS = overfitting.

### Validação SEM vazamento (`scripts/validate_improved.py`)

O honesto é deixar o walk-forward escolher `asym`/banda/ATR **só com dados de
treino** (`walk_forward_grid`). Resultado leakage-free (conferido em 3 execuções):

| | Retorno | MaxDD | Sharpe | Calmar | Trades | d.méd |
|---|---:|---:|---:|---:|---:|---:|
| v1 (atual) | +106,1% | −28,9% | 0,72 | 0,69 | 18 | 46d |
| **GRID honesto (v3)** | **+136,8%** | −30,1% | **0,85** | **0,80** | 12 | 62d |
| Buy & Hold | +157,7% | −76,6% | 0,71 | 0,35 | 0 | — |

(B&H Sharpe conferido recalculando do zero: 0,709.)

> ⚠️ **Correção de honestidade:** uma versão anterior deste doc citou +147,5% — número
> errado, escrito antes da execução final. O valor real validado é **+136,8%**.

**Conclusões:**
- A melhoria é **real e sobrevive à validação rigorosa**: +106% → +136,8%.
- **Encurta bem a distância pro B&H em retorno** (−21pp, vs −52pp do v1) com **~1/3
  do drawdown** (−30% vs −77%).
- **Ganha do B&H em retorno/risco**: Sharpe 0,85 vs 0,71; Calmar 0,80 vs 0,35.
- Segura o trade ~62 dias (vs 46 do v1) com menos trades (12 vs 18).

**O que de fato generalizou (importante):** o grid escolheu `asym=1.0` + banda 5% +
trailing ATR (k=4) em **todas** as 4 janelas. Ou seja, o que segurou a tendência e
melhorou OOS foi o **trailing stop por ATR + a banda de regime** — **não** o canal
assimétrico (asym>1), que só brilhou no sweep COM vazamento. A intuição "segurar
mais" estava certa; o mecanismo vencedor foi o trailing, não o canal largo.

Rodar (v3 é o default): `python scripts/run_btc_sprint1.py`
