import numpy as np, pandas as pd
daily = pd.read_pickle('btc_daily.pkl')

wk = daily.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
didx = daily.index
dH,dL,dC = daily['High'].values, daily['Low'].values, daily['Close'].values
wH,wL,wC = wk['High'].values, wk['Low'].values, wk['Close'].values
wk_idx = wk.index

def hilo_fast(H,L,C,period):
    ma_h=pd.Series(H).rolling(period).mean().shift(1).values
    ma_l=pd.Series(L).rolling(period).mean().shift(1).values
    hld=np.where(C>ma_h,1,np.where(C<=ma_l,-1,0)).astype(float)
    hld[hld==0]=np.nan
    return pd.Series(hld).ffill().fillna(1).values

def expand(arr_w, idx_ref):
    return pd.Series(arr_w, index=wk_idx).reindex(idx_ref, method='ffill').values

def signals_for(mask_d, mask_w, hp,f,s,sg):
    """gera buy/sell para subconjunto (usa índices completos, filtra depois)"""
    hlvd=hilo_fast(dH,dL,dC,hp)
    hlv_w=hilo_fast(wH,wL,wC,hp)
    hiloUp_w=np.where(hlv_w>0, pd.Series(wL).shift(1).rolling(hp).mean().values, np.nan)
    hiloUp=expand(hiloUp_w, didx)
    ser=pd.Series(wC)
    macd=ser.ewm(span=f,adjust=False).mean()-ser.ewm(span=s,adjust=False).mean()
    hist=(macd-macd.ewm(span=sg,adjust=False).mean()).values
    fpos=expand((hist>0).astype(float), didx)>0.5
    hlvd_prev=np.roll(hlvd,1)
    buy=(hlvd_prev<=0)&(hlvd>0)&fpos
    dC_prev=np.roll(dC,1); hiloUp_prev=np.roll(hiloUp,1)
    sell=(dC_prev>=hiloUp_prev)&(dC<hiloUp)
    return buy, sell

def trade(buy,sell,i0,i1):
    """backtest entre índices i0:i1"""
    eq=10000.0;pos=None;rets=[];curve=[eq]
    for i in range(i0,i1):
        if buy[i] and pos is None: pos=dC[i]
        elif sell[i] and pos is not None:
            r=(dC[i]-pos)/pos;eq*=(1+r);rets.append(r);pos=None;curve.append(eq)
    if pos is not None:
        r=(dC[i1-1]-pos)/pos;eq*=(1+r);rets.append(r);curve.append(eq)
    return rets,np.array(curve),eq

def metrics(rets,curve):
    if len(rets)<2: return None
    rets=np.array(rets)
    net=(curve[-1]/10000-1)*100
    peak=np.maximum.accumulate(curve);dd=((curve-peak)/peak*100).min()
    w=(rets>0).sum();l=(rets<=0).sum();mc=0;c=0
    for r in rets:
        if r<=0:c+=1;mc=max(mc,c)
        else:c=0
    return dict(net=net,dd=dd,winners=w,losers=l,allq=len(rets),maxcons=mc)

def fitness(m):
    if m is None: return -1
    if not(m['winners']>0.5*m['allq'] and abs(m['net'])>abs(m['dd']) and m['maxcons']<=2):
        return -1
    return ((abs(m['net'])+1)/(abs(m['dd'])+1))/(abs(m['losers'])+1)

def optimize(i0,i1):
    """acha melhor param NA JANELA i0:i1 (in-sample)"""
    best=(-1,None)
    for hp in range(4,56,6):
        for f in range(2,50,8):
            for s in range(2,50,8):
                for sg in range(2,40,8):
                    buy,sell=signals_for(None,None,hp,f,s,sg)
                    r,c,_=trade(buy,sell,i0,i1)
                    fit=fitness(metrics(r,c))
                    if fit>best[0]: best=(fit,(hp,f,s,sg))
    return best

# ============================================================
# WALK-FORWARD: janela treino 4 anos -> testa 1 ano à frente
# ============================================================
print("="*78)
print(" WALK-FORWARD BTC | treino=4 anos, teste=1 ano à frente (out-of-sample)")
print("="*78)
start=daily.index[0]
train_days=int(365*4); test_days=365
oos_rets=[]; oos_curve=[10000.0]; eq=10000.0
i=train_days
while i+test_days <= len(didx):
    # otimiza no passado [i-train:i]
    fit,params=optimize(i-train_days, i)
    if params is None:
        i+=test_days; continue
    hp,f,s,sg=params
    # aplica OUT-OF-SAMPLE no futuro [i:i+test]
    buy,sell=signals_for(None,None,hp,f,s,sg)
    r,c,_=trade(buy,sell,i,i+test_days)
    for rr in r:
        eq*=(1+rr); oos_rets.append(rr); oos_curve.append(eq)
    d0,d1=didx[i].date(), didx[min(i+test_days,len(didx)-1)].date()
    rsum=(np.prod([1+x for x in r])-1)*100 if r else 0
    print(f"  Treino->{didx[i].date()} | params(hilo={hp},f={f},s={s},sg={sg}) | teste {d0}..{d1}: {rsum:+.0f}% ({len(r)} trades)")
    i+=test_days

oos_curve=np.array(oos_curve)
print("\n"+"="*78)
print(" RESULTADO OUT-OF-SAMPLE (dinheiro real simulado)")
print("="*78)
if len(oos_rets)>=1:
    net=(eq/10000-1)*100
    peak=np.maximum.accumulate(oos_curve);dd=((oos_curve-peak)/peak*100).min()
    w=sum(1 for x in oos_rets if x>0);l=sum(1 for x in oos_rets if x<=0)
    print(f"  Sistema (walk-forward): ${eq:,.0f}  ({net:+.0f}%)")
    print(f"  Trades OOS: {len(oos_rets)} | Acertos {w} ({w/len(oos_rets)*100:.0f}%) | Drawdown {dd:.0f}%")
else:
    print("  Sem trades suficientes out-of-sample")

# Buy & Hold no MESMO período out-of-sample
bh_start=dC[train_days]; bh_end=dC[-1]
bh_eq=10000*bh_end/bh_start
print(f"\n  Buy & Hold (segurar): ${bh_eq:,.0f}  ({(bh_eq/10000-1)*100:+.0f}%)")
print(f"  Período OOS: {didx[train_days].date()} -> {didx[-1].date()}")
print("\n"+"="*78)
if len(oos_rets)>=1:
    if eq>bh_eq: print(f"  >>> SISTEMA GANHOU do buy & hold por {(eq/bh_eq-1)*100:+.0f}%")
    else: print(f"  >>> BUY & HOLD GANHOU do sistema por {(bh_eq/eq-1)*100:+.0f}%")
