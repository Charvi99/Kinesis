"""SPY benchmark series (adapted for Kinesis's lean fetcher).

Same purpose as StockAnalyzer: overlay SPY (scaled to starting capital) alongside
the engine's equity, and compute alpha for backtests. Uses fetch_daily_bars (the
Kinesis lean fetcher) instead of the period-based fetch_historical_data.
"""
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)

BENCHMARK_SYMBOL = "SPY"
_CACHE_TTL_SECONDS = 15 * 60
_cache: Dict[str, Dict] = {}


def _with_returns(window: List[Dict]) -> List[Dict]:
    if not window:
        return []
    first = window[0]["close"]
    out = []
    for bar in window:
        close = bar["close"]
        ret = (close - first) / first if first else 0.0
        out.append({"date": bar["date"], "close": close, "return_pct": ret})
    return out


def _fetch_spy_range(from_date: str, to_date: str) -> List[Dict]:
    from app.services.polygon_fetcher import PolygonFetcher
    bars = PolygonFetcher().fetch_daily_bars(BENCHMARK_SYMBOL, from_date, to_date)
    out = []
    for b in bars:
        ts = b["timestamp"]
        d = ts.astimezone(timezone.utc).strftime("%Y-%m-%d") if isinstance(ts, datetime) else str(ts)[:10]
        out.append({"date": d, "close": float(b["close"])})
    return out


def _fetch_cached(period_years: int = 5) -> List[Dict]:
    key = f"{period_years}y"
    now = time.time()
    entry = _cache.get(key)
    if entry and entry["series"] and (now - entry["fetched_at"]) < _CACHE_TTL_SECONDS:
        return entry["series"]
    from datetime import timedelta
    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from_date = (datetime.now(timezone.utc) - timedelta(days=365 * period_years)).strftime("%Y-%m-%d")
    fetched = _fetch_spy_range(from_date, to_date)
    if fetched:
        _cache[key] = {"fetched_at": now, "series": fetched}
    return fetched


def get_spy_series(days: int = 90) -> List[Dict]:
    try:
        series = _fetch_cached()
        if not series:
            return []
        window = series[-days:] if days and days < len(series) else series
        return _with_returns(window)
    except Exception as e:
        logger.warning("[benchmark] SPY series failed: %s", e)
        return []


def get_spy_series_for_window(start, end) -> List[Dict]:
    try:
        import pandas as pd
        start_s = pd.Timestamp(start).strftime("%Y-%m-%d")
        end_s = pd.Timestamp(end).strftime("%Y-%m-%d")
        series = _fetch_cached()
        if not series:
            return []
        window = [b for b in series if start_s <= b["date"] <= end_s]
        return _with_returns(window)
    except Exception as e:
        logger.warning("[benchmark] SPY window series failed: %s", e)
        return []
