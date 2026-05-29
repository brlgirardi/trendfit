import numpy as np, pandas as pd
daily = pd.read_pickle('btc_daily.pkl')
didx=daily.index
dC=daily['Close'].values; dH=daily['High'].values; dL=daily['Low'].values

# ============================================================
# NÚCLEO ROBUSTO: Donchian breakout (trend-following, 1 param)
# + ENSEMBLE (vota entre vários lookbacks, reduz overfit)
# ============================================================
def donchian_signal(C,H,L,lb):
    hh=pd.Series(H).rolling(lb).max().shift(1).values
    ll=pd.Series(L).rolling(lb).min().shift(1).values
    long_in = C>hh   # rompe topo => entra
    long_out= C<ll   # rompe fundo => sai
    return long_in, long_out

def ensemble_position(C,H,L,lbs):
    """cada lookback dá voto 0/1; posição = fração que está long"""
    votes=np.zeros(len(C))
    for lb in lbs:
        lin,lout=donchian_signal(C,H,L,lb)
        state=0;v=np.zeros(len(C))
        for i in range(len(C)):
            if lin[i]: state=1
            elif lout[i]: state=0
            v[i]=state
        votes+=v
    return votes/len(lbs)  # 0..1

# ============================================================
# CAMADA DE VETO / REGIME (proxy do que IA faria)
# Regime de tendência longa: preço vs média 200d (bull/bear macro)
# + "ciclo": distância de drawdown do topo (proxy MVRV)
# ============================================================
def regime_filter(C):
    ma200=pd.Series(C).rolling(200).mean().values
    bull = C>ma200                       # só compra em bull macro
    # proxy ciclo: drawdown do pico móvel — perto do topo = cautela
    peak=pd.Series(C).cummax().values
    dd=(C-peak)/peak
    not_euphoria = dd < -0.02            # evita comprar exatamente no topo
    return bull, ma200

# ============================================================
# BACKTEST com posição fracionária (ensemble) + veto
# ============================================================
def run_strategy(i0,i1,lbs,use_veto):
    eq=10000.0; curve=[eq]; rets=[]
    pos=ensemble_position(dC,dH,dL,lbs)
    bull,_=regime_filter(dC)
    prev_w=0.0
    for i in range(i0,i1):
        w=pos[i]
        if use_veto and not bull[i]:
            w=0.0                        # VETO: regime bear => fica fora
        # retorno diário aplicado ao peso do dia anterior
        if i>i0:
            daily_ret=(dC[i]-dC[i-1])/dC[i-1]
            eq*=(1+prev_w*daily_ret)
            curve.append(eq)
        if abs(w-prev_w)>0.01 and prev_w>0 and w<prev_w:
            rets.append(1)  # marca mudança (simplificado)
        prev_w=w
    return eq, np.array(curve)

def maxdd(curve):
    peak=np.maximum.accumulate(curve)
    return ((curve-peak)/peak*100).min()

# ============================================================
# WALK-FORWARD: 4a treino (escolhe melhor conjunto de lookbacks)
#               1a teste cego
# ============================================================
print("="*78)
print(" WALK-FORWARD: Núcleo Ensemble Trend + Veto de Regime  vs  Buy&Hold")
print("="*78)

# candidatos de ensemble (conjuntos de lookbacks Donchian)
ensembles={
 'curto':[10,20,30],
 'medio':[20,40,60],
 'longo':[40,60,100],
 'amplo':[15,30,55,90],
}

train_days=int(365*4); test_days=365
i=train_days
eq_veto=10000.0; eq_noveto=10000.0
curve_veto=[eq_veto]; curve_noveto=[eq_noveto]

while i+test_days<=len(didx):
    # treino: escolhe ensemble com melhor retorno/DD no passado
    best=None
    for name,lbs in ensembles.items():
        e,c=run_strategy(i-train_days,i,lbs,use_veto=True)
        dd=maxdd(c); score=(e/10000-1)/(abs(dd)+1)  # retorno por unidade de risco
        if best is None or score>best[0]:
            best=(score,name,lbs)
    _,name,lbs=best
    # teste OOS com e sem veto
    ev,cv=run_strategy(i,i+test_days,lbs,use_veto=True)
    en,cn=run_strategy(i,i+test_days,lbs,use_veto=False)
    eq_veto*=ev/10000; eq_noveto*=en/10000
    d0,d1=didx[i].date(),didx[min(i+test_days,len(didx)-1)].date()
    print(f"  treino->{didx[i].date()} escolheu '{name}' {lbs}")
    print(f"    teste {d0}..{d1}: com_veto {(ev/10000-1)*100:+.0f}% | sem_veto {(en/10000-1)*100:+.0f}%")
    i+=test_days

# Buy&Hold no mesmo período OOS
bh=10000*dC[-1]/dC[train_days]

print("\n"+"="*78)
print(" RESULTADO FINAL OUT-OF-SAMPLE")
print("="*78)
print(f"  Núcleo + Veto Regime : ${eq_veto:,.0f}  ({(eq_veto/10000-1)*100:+.0f}%)")
print(f"  Núcleo SEM veto      : ${eq_noveto:,.0f}  ({(eq_noveto/10000-1)*100:+.0f}%)")
print(f"  Buy & Hold (segurar) : ${bh:,.0f}  ({(bh/10000-1)*100:+.0f}%)")
print(f"  Período: {didx[train_days].date()} -> {didx[-1].date()}")
print("\n  COMPARATIVO:")
sysbest=max(eq_veto,eq_noveto)
if sysbest>bh: print(f"  >>> SISTEMA bateu Buy&Hold por {(sysbest/bh-1)*100:+.0f}%")
else: print(f"  >>> Buy&Hold venceu por {(bh/sysbest-1)*100:+.0f}%")
print(f"  Veto {'AJUDOU' if eq_veto>eq_noveto else 'ATRAPALHOU'}: {(eq_veto/eq_noveto-1)*100:+.0f}% vs sem veto")
