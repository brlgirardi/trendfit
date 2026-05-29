# TrendFit — Starter / Provas de Conceito

Scripts da fase de validação (dados reconstruídos). Servem como REFERÊNCIA
da lógica, não como código de produção.

## Arquivos
- trendfit_btc.py     — réplica fiel do Trade System AFL (HiLo+MACD multi-TF)
- build_data.py       — reconstrução de série BTC (âncoras mensais + ruído)
- optimize2.py        — Optimizer + Fitness (réplica do Fitness_Final.afl)
- walkforward.py      — walk-forward HiLo+MACD (provou o overfitting)
- confluence_wf.py    — arquitetura vencedora: ensemble trend + veto de regime
- current_signal.py   — leitura do sinal atual

## Resultado-chave
- HiLo+MACD otimizado: +3.775% in-sample → +5% OOS (overfitting)
- Ensemble + veto: +92% OOS vs +28% Buy&Hold (+51% de vantagem)

## IMPORTANTE
Dados aqui são RECONSTRUÍDOS. Produção exige dados reais via CCXT.
