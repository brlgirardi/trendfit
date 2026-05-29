import numpy as np, pandas as pd

# ============================================================
# REPLICA FIEL DO OFFICIAL SCRIPT (AmiBroker AFL) -> Python
# BTC params: hilo=22, fast=8, slow=2, signal=2 (diario + filtro semanal)
# ============================================================

# ---- HiLo Activator (igual AFL) ----
def hilo(df, period):
    H, L, C = df['High'], df['Low'], df['Close']
    ma_h = H.rolling(period).mean().shift(1)   # Ref(MA(H,period),-1)
    ma_l = L.rolling(period).mean().shift(1)
    hld = np.where(C > ma_h, 1, np.where(C <= ma_l, -1, 0))
    hld = pd.Series(hld, index=df.index)
    hlv = hld.replace(0, np.nan).ffill().fillna(1)  # ValueWhen(Hld!=0,Hld,1)
    hiloUp = pd.Series(np.where(hlv>0, L.shift(1).rolling(period).mean(), np.nan), index=df.index)
    return hlv, hiloUp

# ---- MACD (igual AFL: MACD(fast,slow) - Signal) ----
def macd_filter(s, fast, slow, signal):
    ema_f = s.ewm(span=fast, adjust=False).mean()
    ema_s = s.ewm(span=slow, adjust=False).mean()
    macd = ema_f - ema_s
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return hist > 0, hist < 0

def cross_up(s, level=0):   # Cross(s, level)
    return (s.shift(1) <= level) & (s > level)
def cross_dn_price(price, line):  # Cross(0, HiloUp) = preço rompe linha p/ baixo
    return (price.shift(1) >= line.shift(1)) & (price < line)

def run_system(daily, hilo_p=22, fast=8, slow=2, signal=2):
    # HiLo diario
    hlvd, _ = hilo(daily, hilo_p)
    # HiLo semanal (resample W) + filtro MACD semanal
    wk = daily.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
    _, hiloUp_w = hilo(wk, hilo_p)
    fpos_w, fneg_w = macd_filter(wk['Close'], fast, slow, signal)
    # expand semanal -> diario
    hiloUp = hiloUp_w.reindex(daily.index, method='ffill')
    fpos = fpos_w.reindex(daily.index, method='ffill').fillna(False)
    fneg = fneg_w.reindex(daily.index, method='ffill').fillna(False)
    # Sinais (igual AFL)
    buy = cross_up(hlvd,0) & fpos
    sell = cross_dn_price(daily['Close'], hiloUp)
    short = sell & fneg
    # ExRem (remove repetidos)
    sig = pd.Series(0, index=daily.index)
    state = 0
    out = []
    for i in daily.index:
        if buy[i] and state<=0:
            out.append((i,'BUY',daily['Close'][i])); state=1
        elif sell[i] and state>0:
            out.append((i,'SELL',daily['Close'][i])); state=0
        elif short[i] and state==0:
            out.append((i,'SHORT',daily['Close'][i])); state=-1
    return out, hlvd, hiloUp, fpos

print("Sistema carregado. Lógica AFL replicada fielmente.")
print("HiLo diário + HiLo semanal + filtro MACD semanal + ExRem")
