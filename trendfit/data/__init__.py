"""Camada de dados: coleta (CCXT/yfinance) e cache local em SQLite."""

from trendfit.data.cache import OHLCVCache
from trendfit.data.collector import CollectorError, fetch_ohlcv_daily

__all__ = ["OHLCVCache", "fetch_ohlcv_daily", "CollectorError"]
