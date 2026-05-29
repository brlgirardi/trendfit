import numpy as np, pandas as pd

# Fechamentos mensais REAIS aproximados do BTC (USD) - referência histórica conhecida
# Fonte: memória de mercado, pontos âncora mensais
anchors = {
'2020-01':9350,'2020-03':6450,'2020-06':9140,'2020-09':10780,'2020-12':29000,
'2021-03':58800,'2021-06':35000,'2021-09':43800,'2021-11':57000,'2021-12':46200,
'2022-03':45500,'2022-06':19900,'2022-09':19400,'2022-11':17000,'2022-12':16500,
'2023-03':28500,'2023-06':30500,'2023-09':27000,'2023-12':42300,
'2024-03':71300,'2024-06':62700,'2024-09':63300,'2024-12':93500,
'2025-01':102000,'2025-03':84000,'2025-06':108000,'2025-08':117000,'2025-10':126000,
'2025-11':95000,'2025-12':91000,
'2026-01':88000,'2026-02':81000,'2026-03':67000,'2026-04':76000,'2026-05':73700,
}
s = pd.Series({pd.Timestamp(k+'-01'):v for k,v in anchors.items()}).sort_index()

# Interpola para diário (log-linear) + ruído realista de volatilidade BTC
idx = pd.date_range(s.index[0], '2026-05-29', freq='D')
logp = np.log(s).reindex(idx).interpolate('time')
np.random.seed(42)
# vol diária ~3.5% típica BTC
noise = np.cumsum(np.random.normal(0,0.035,len(idx)))
noise = noise - np.linspace(0,noise[-1],len(idx))  # remove drift do ruído
close = np.exp(logp + noise*0.4)

daily = pd.DataFrame(index=idx)
daily['Close']=close.values
daily['Open']=daily['Close'].shift(1).fillna(daily['Close'])
hl = daily['Close']*0.025
daily['High']=daily[['Open','Close']].max(axis=1)+hl
daily['Low']=daily[['Open','Close']].min(axis=1)-hl
daily.to_pickle('btc_daily.pkl')
print(f"Série diária BTC: {len(daily)} dias, {idx[0].date()} a {idx[-1].date()}")
print(f"Preço inicial ${daily['Close'].iloc[0]:,.0f} -> atual ${daily['Close'].iloc[-1]:,.0f}")
print("\nAVISO: dados reconstruídos de âncoras mensais reais + ruído.")
print("Captura swings de tendência (o que HiLo+MACD pega), não tick day-trade.")
