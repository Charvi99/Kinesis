"""Lean Polygon fetcher for Kinesis — daily OHLCV bars + the universe list.

Uses the polygon-api-client SDK (same as StockAnalyzer). No news/metadata/pattern
fluff — engine_3 only needs price bars; sentiment/news reuse polygon_client.py.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from polygon import RESTClient

log = logging.getLogger(__name__)


class PolygonFetcher:
    def __init__(self, api_key: Optional[str] = None):
        self.client = RESTClient(api_key or os.getenv("POLYGON_API_KEY"))

    def fetch_daily_bars(self, symbol: str, from_date: str, to_date: str) -> List[Dict]:
        aggs = self.client.get_aggs(
            ticker=symbol.upper(), multiplier=1, timespan="day",
            from_=from_date, to=to_date, limit=50000,
        )
        out: List[Dict] = []
        for b in aggs or []:
            ts = datetime.fromtimestamp(b.timestamp / 1000, tz=timezone.utc)
            out.append({
                "timestamp": ts, "timeframe": "1d",
                "open": float(b.open), "high": float(b.high), "low": float(b.low),
                "close": float(b.close), "volume": int(b.volume or 0),
                "adjusted_close": float(b.close),
            })
        return out

    def list_us_common_stocks(self, limit: int = 1000) -> List[Dict]:
        out: List[Dict] = []
        for t in self.client.get_tickers(market="stocks", ticker_type="CS", active=True, limit=1000):
            sym = getattr(t, "ticker", None)
            if sym and sym.isalpha() and getattr(t, "type", None) == "CS":
                out.append({"symbol": sym, "name": getattr(t, "name", None)})
            if len(out) >= limit:
                break
        return out
