import numpy as np, pandas as pd
daily=pd.read_pickle('btc_daily.pkl')
dC=daily['Close'].values;dH=daily['High'].values;dL=daily['Low'].values;didx=daily.index

def donchian_state(C,H,L,lb):
    hh=pd.Series(H).rolling(lb).max().shift(1).values
    ll=pd.Series(L).rolling(lb).min().shift(1).values
    state=0;out=np.zeros(len(C))
    for i in range(len(C)):
        if C[i]>hh[i]: state=1
        elif C[i]<ll[i]: state=0
        out[i]=state
    return out,hh,ll

lbs=[10,20,30]  # ensemble vencedor
votes=np.zeros(len(dC))
detail=[]
for lb in lbs:
    st,hh,ll=donchian_state(dC,dH,dL,lb)
    votes+=st
    detail.append((lb,st[-1],hh[-1],ll[-1]))
votes/=len(lbs)

ma200=pd.Series(dC).rolling(200).mean().values
bull=dC[-1]>ma200[-1]
peak=pd.Series(dC).cummax().values
dd_now=(dC[-1]-peak[-1])/peak[-1]*100

print("="*68)
print(" SINAL ATUAL DO TRENDFIT — BTC | 29-mai-2026")
print("="*68)
print(f"  Preço: ${dC[-1]:,.0f}")
print(f"\n  NÚCLEO (ensemble Donchian):")
for lb,st,hh,ll in detail:
    print(f"    Donchian-{lb}: {'LONG' if st>0 else 'FORA'} (topo ${hh:,.0f} / fundo ${ll:,.0f})")
print(f"    >>> Voto do ensemble: {votes[-1]*100:.0f}% comprado")
print(f"\n  VETO DE REGIME:")
print(f"    Média 200d: ${ma200[-1]:,.0f} | Preço {'ACIMA' if bull else 'ABAIXO'}")
print(f"    Regime macro: {'BULL (libera)' if bull else 'BEAR (veta compra)'}")
print(f"    Drawdown do topo: {dd_now:.0f}%")

# decisão final
w=votes[-1] if bull else 0.0
print(f"\n  {'='*40}")
print(f"  POSIÇÃO RECOMENDADA PELO SISTEMA: {w*100:.0f}% comprado")
if w>=0.66: verdict="COMPRADO forte — tendência confirmada"
elif w>=0.33: verdict="PARCIAL — tendência mista"
elif w>0: verdict="LEVE — sinal fraco"
else: verdict="FORA — sem tendência de alta confirmada / regime bear"
print(f"  LEITURA: {verdict}")
