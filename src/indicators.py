"""Technical indicator calculations for simple trade analysis."""

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator


def add_indicators(market_data: pd.DataFrame) -> pd.DataFrame:
    frame = market_data.copy()
    frame["ma_20"] = SMAIndicator(close=frame["close"], window=20).sma_indicator()
    frame["ma_50"] = SMAIndicator(close=frame["close"], window=50).sma_indicator()
    frame["rsi"] = RSIIndicator(close=frame["close"], window=14).rsi()
    frame["volume_ma_20"] = frame["volume"].rolling(window=20).mean()
    frame["volume_vs_average"] = (frame["volume"] / frame["volume_ma_20"]) * 100
    frame["volume_change"] = frame["volume"].pct_change() * 100
    frame["support"] = frame["close"].shift(1).rolling(window=20).min()
    frame["resistance"] = frame["close"].shift(1).rolling(window=20).max()
    return frame
