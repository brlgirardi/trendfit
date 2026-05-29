import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def trend_df():
    """Série sintética: subida limpa, queda, subida — para checar trend-following."""
    idx = pd.date_range("2020-01-01", periods=600, freq="D", tz="UTC")
    up1 = np.linspace(100, 300, 200)
    down = np.linspace(300, 120, 200)
    up2 = np.linspace(120, 400, 200)
    close = np.concatenate([up1, down, up2])
    df = pd.DataFrame(index=idx)
    df["Close"] = close
    df["Open"] = df["Close"].shift(1).fillna(df["Close"])
    # padding pequeno (0.1%): o breakout Donchian precisa de ganho diário > padding
    df["High"] = df[["Open", "Close"]].max(axis=1) * 1.001
    df["Low"] = df[["Open", "Close"]].min(axis=1) * 0.999
    df["Volume"] = 1.0
    return df
