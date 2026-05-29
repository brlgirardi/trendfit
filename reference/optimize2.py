import numpy as np, pandas as pd
daily = pd.read_pickle('btc_daily.pkl')

# Pré-computa semanal UMA vez
wk = daily.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
didx = daily.index
wk_close = wk['Close'].values
wk_idx = wk.index

def hilo_fast(H,L,C,period):
    ma_h = pd.Series(H).rolling(period).mean().shift(1).values
    ma_l = pd.Series(L).rolling(period).mean().shift(1).values
    hld = np.where(C>ma_h,1,np.where(C<=ma_l,-1,0)).astype(float)
    hld[hld==0]=np.nan
    hlv = pd.Series(hld).ffill().fillna(1).values
    return hlv

# pré-arrays diário
dH,dL,dC = daily['High'].values, daily['Low'].values, daily['Close'].values
wH,wL,wC = wk['High'].values, wk['Low'].values, wk['Close'].values

def expand_w2d(arr_w):
    return pd.Series(arr_w, index=wk_idx).reindex(didx, method='ffill').values

def run(hp,f,s,sg):
    hlvd = hilo_fast(dH,dL,dC,hp)
    hlv_w = hilo_fast(wH,wL,wC,hp)
    hiloUp_w = np.where(hlv_w>0, pd.Series(wL).shift(1).rolling(hp).mean().values, np.nan)
    hiloUp = expand_w2d(hiloUp_w)
    # MACD semanal
    ser=pd.Series(wC)
    macd=ser.ewm(span=f,adjust=False).mean()-ser.ewm(span=s,adjust=False).mean()
    hist=(macd-macd.ewm(span=sg,adjust=False).mean()).values
    fpos=expand_w2d((hist>0).astype(float))>0.5
    # sinais
    hlvd_prev=np.roll(hlvd,1)
    buy=(hlvd_prev<=0)&(hlvd>0)&fpos
    dC_prev=np.roll(dC,1); hiloUp_prev=np.roll(hiloUp,1)
    sell=(dC_prev>=hiloUp_prev)&(dC<hiloUp)
    # trades long-only
    eq=10000.0; pos=None; rets=[]; curve=[eq]
    for i in range(len(didx)):
        if buy[i] and pos is None: pos=dC[i]
        elif sell[i] and pos is not None:
            r=(dC[i]-pos)/pos; eq*=(1+r); rets.append(r); pos=None; curve.append(eq)
    if pos is not None:
        r=(dC[-1]-pos)/pos; eq*=(1+r); rets.append(r); curve.append(eq)
    return rets, np.array(curve)

def metrics(rets,curve):
    if len(rets)<2: return None
    rets=np.array(rets)
    net=(curve[-1]/10000-1)*100
    peak=np.maximum.accumulate(curve); dd=((curve-peak)/peak*100).min()
    w=(rets>0).sum(); l=(rets<=0).sum()
    mc=0;c=0
    for r in rets:
        if r<=0: c+=1;mc=max(mc,c)
        else:c=0
    return dict(net=net,dd=dd,winners=w,losers=l,allq=len(rets),maxcons=mc)

def fitness(m):
    if m is None: return -1
    if not(m['winners']>0.5*m['allq'] and abs(m['net'])>abs(m['dd']) and m['maxcons']<=2):
        return -1
    return ((abs(m['net'])+1)/(abs(m['dd'])+1))/(abs(m['losers'])+1)

results=[]
for hp in range(4,56,4):
    for f in range(2,56,6):
        for s in range(2,56,6):
            for sg in range(2,40,6):
                r,c=run(hp,f,s,sg)
                m=metrics(r,c); fit=fitness(m)
                if fit>0: results.append((fit,hp,f,s,sg,m))
results.sort(reverse=True,key=lambda x:x[0])
print(f"Válidas: {len(results)}")
print("="*80)
print(f"{'Fit':>6s} {'hilo':>4s} {'fast':>4s} {'slow':>4s} {'sig':>4s} {'Net%':>10s} {'DD%':>7s} {'W':>3s} {'L':>3s} {'cons':>4s}")
for fit,hp,f,s,sg,m in results[:12]:
    print(f"{fit:>6.3f} {hp:>4d} {f:>4d} {s:>4d} {sg:>4d} {m['net']:>+9.0f}% {m['dd']:>6.0f}% {m['winners']:>3d} {m['losers']:>3d} {m['maxcons']:>4d}")
import pickle; pickle.dump(results[:12],open('top.pkl','wb'))

# Detalha o melhor e mostra sinais
print("\n"+"="*80)
print(" MELHOR PARA BTC: hilo=8, fast=2, slow=8, signal=8")
print("="*80)
best_params=(8,2,8,8)
hp,f,s,sg=best_params
hlvd = hilo_fast(dH,dL,dC,hp)
hlv_w = hilo_fast(wH,wL,wC,hp)
hiloUp_w = np.where(hlv_w>0, pd.Series(wL).shift(1).rolling(hp).mean().values, np.nan)
hiloUp = expand_w2d(hiloUp_w)
ser=pd.Series(wC)
macd=ser.ewm(span=f,adjust=False).mean()-ser.ewm(span=s,adjust=False).mean()
hist=(macd-macd.ewm(span=sg,adjust=False).mean()).values
fpos=expand_w2d((hist>0).astype(float))>0.5
hlvd_prev=np.roll(hlvd,1)
buy=(hlvd_prev<=0)&(hlvd>0)&fpos
dC_prev=np.roll(dC,1); hiloUp_prev=np.roll(hiloUp,1)
sell=(dC_prev>=hiloUp_prev)&(dC<hiloUp)

eq=10000.0;pos=None;state=0
print(f"{'Data':12s} {'Sinal':6s} {'Preço':>10s} {'Equity':>12s}")
for i in range(len(didx)):
    if buy[i] and pos is None:
        pos=dC[i]; print(f"{str(didx[i].date()):12s} {'BUY':6s} ${dC[i]:>9,.0f}")
    elif sell[i] and pos is not None:
        r=(dC[i]-pos)/pos; eq*=(1+r)
        print(f"{str(didx[i].date()):12s} {'SELL':6s} ${dC[i]:>9,.0f} ${eq:>11,.0f} ({r*100:+.0f}%)")
        pos=None
if pos is not None:
    r=(dC[-1]-pos)/pos; eq*=(1+r)
    print(f"{str(didx[-1].date()):12s} {'(open)':6s} ${dC[-1]:>9,.0f} ${eq:>11,.0f} ({r*100:+.0f}%)")

print(f"\n  Estado HOJE: HiLo diário={'+' if hlvd[-1]>0 else '-'} | MACD sem={'+' if fpos[-1] else '-'}")
print(f"  Posição: {'COMPRADO' if pos else 'FORA'}")
