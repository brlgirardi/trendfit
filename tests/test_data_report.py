import numpy as np
import pandas as pd
import pytest

from trendfit.data.cache import OHLCVCache
from trendfit.data.collector import CollectorError, fetch_ohlcv_daily
from trendfit.engine.walkforward import walk_forward
from trendfit.report import build_report, format_console_summary


def test_cache_upsert_idempotent(tmp_path):
    db = tmp_path / "t.sqlite"
    with OHLCVCache(db) as cache:
        rows = [(1_600_000_000_000 + i * 86_400_000, 1.0, 2.0, 0.5, 1.5, 10.0) for i in range(5)]
        n1 = cache.upsert("BTC", "1d", rows, "test")
        n2 = cache.upsert("BTC", "1d", rows, "test")  # mesmos timestamps -> upsert, não duplica
        assert n1 == 5 and n2 == 5
        df = cache.load("BTC", "1d")
        assert len(df) == 5  # não duplicou
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        info = cache.info("BTC", "1d")
        assert info["rows"] == 5
        assert cache.last_ts("BTC", "1d") == rows[-1][0]


def test_cache_empty_load(tmp_path):
    with OHLCVCache(tmp_path / "e.sqlite") as cache:
        assert cache.load("ETH", "1d").empty
        assert cache.last_ts("ETH", "1d") is None


def test_collector_raises_when_all_sources_fail(tmp_path):
    """Sem rede/fontes válidas e cache vazio -> erro explícito (nunca inventa dados)."""
    with OHLCVCache(tmp_path / "x.sqlite") as cache:
        with pytest.raises(CollectorError):
            fetch_ohlcv_daily(cache, "BTC", "1d", exchanges=[("exchange_que_nao_existe", "BTC/USDT")])


@pytest.fixture
def wf_result():
    n = 365 * 6
    idx = pd.date_range("2017-01-01", periods=n, freq="D", tz="UTC")
    t = np.arange(n)
    close = 100 * np.exp(0.0006 * t) * (1 + 0.3 * np.sin(t / 120))
    df = pd.DataFrame(index=idx)
    df["Close"] = close
    df["Open"] = df["Close"].shift(1).fillna(df["Close"])
    df["High"] = df[["Open", "Close"]].max(axis=1) * 1.001
    df["Low"] = df[["Open", "Close"]].min(axis=1) * 0.999
    return df, walk_forward(df, train_days=365 * 4, test_days=365)


def test_console_summary_contains_key_lines(wf_result):
    df, wf = wf_result
    text = format_console_summary(wf, "BTC")
    assert "WALK-FORWARD BTC" in text
    assert "Buy & Hold" in text
    assert "Sistema" in text
    assert "Veto" in text


def test_build_report_writes_html(wf_result, tmp_path):
    df, wf = wf_result
    out = build_report(wf, df["Close"], tmp_path / "r.html", "BTC")
    assert out.exists()
    content = out.read_text()
    assert "plotly" in content.lower()
    assert "TrendFit" in content
