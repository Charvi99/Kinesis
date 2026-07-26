"""Pure market-regime detection from a daily OHLCV DataFrame (no DB, no ``now``).

Kinesis uses ONE regime module for both the live cycle and the backtester — it is
a pure function of the price series truncated at T, so it is causal and unit-
testable. Mirrors the StockAnalyzer MarketRegimeService math (ADX + MA slopes +
TCR regime/direction), without the verbose recommendation table or DB coupling.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def calculate_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma20"] = df["close"].rolling(20, min_periods=1).mean()
    df["ma50"] = df["close"].rolling(50, min_periods=1).mean()
    return df


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = (df["high"] - df["close"].shift(1)).abs()
    df["low_close"] = (df["low"] - df["close"].shift(1)).abs()
    df["true_range"] = df[["high_low", "high_close", "low_close"]].max(axis=1)
    df["up_move"] = df["high"] - df["high"].shift(1)
    df["down_move"] = df["low"].shift(1) - df["low"]
    df["plus_dm"] = np.where((df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0)
    df["minus_dm"] = np.where((df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0)
    atr = df["true_range"].rolling(period, min_periods=1).mean().replace(0, np.nan)
    df["plus_di"] = 100 * (df["plus_dm"].rolling(period, min_periods=1).mean() / atr)
    df["minus_di"] = 100 * (df["minus_dm"].rolling(period, min_periods=1).mean() / atr)
    di_sum = (df["plus_di"] + df["minus_di"]).replace(0, np.nan)
    df["dx"] = 100 * abs(df["plus_di"] - df["minus_di"]) / di_sum
    df["adx"] = df["dx"].rolling(period, min_periods=1).mean()
    return df


def ma_slope(series: pd.Series, period: int = 5) -> float:
    if len(series) < period:
        return 0.0
    y = series.iloc[-period:].values
    x = np.arange(len(y))
    slope = np.polyfit(x, y, 1)[0]
    avg = np.mean(y)
    return float((slope / avg) * 100) if avg > 0 else 0.0


def detect_tcr_regime(adx, plus_di, minus_di, ma20_slope, ma50_slope) -> Dict[str, str]:
    regime = "trend" if adx >= 25 else ("channel" if adx >= 20 else "range")
    thr = 0.05
    di_bull, di_bear = plus_di > minus_di, minus_di > plus_di
    ma20b, ma20n = ma20_slope > thr, ma20_slope < -thr
    ma50b, ma50n = ma50_slope > thr, ma50_slope < -thr
    if ma20b and ma50b and di_bull:
        direction = "bullish"
    elif ma20n and ma50n and di_bear:
        direction = "bearish"
    elif ma20b and di_bull:
        direction = "bullish_weak"
    elif ma20n and di_bear:
        direction = "bearish_weak"
    else:
        direction = "neutral"
    return {"regime": regime, "direction": direction, "full_regime": f"{direction}_{regime}"}


def detect_regime(df: pd.DataFrame, lookback: int = 100) -> Dict:
    """Regime + direction as-of the LAST bar of ``df`` (causal). Degrades to
    ``unknown``/``neutral`` on insufficient data (< 50 bars)."""
    if df is None or len(df) < 50:
        return {"regime": "unknown", "direction": "neutral", "full_regime": "unknown_unknown"}
    d = calculate_moving_averages(df.tail(lookback).copy())
    d = calculate_adx(d, period=14)
    adx = float(d["adx"].iloc[-1]); plus = float(d["plus_di"].iloc[-1]); minus = float(d["minus_di"].iloc[-1])
    s20 = ma_slope(d["ma20"], 5); s50 = ma_slope(d["ma50"], 5)
    tcr = detect_tcr_regime(adx, plus, minus, s20, s50)
    return {**tcr, "adx": round(adx, 2), "plus_di": round(plus, 2), "minus_di": round(minus, 2),
            "ma20_slope": round(s20, 4), "ma50_slope": round(s50, 4)}
