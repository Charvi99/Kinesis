"""Lean Polygon fetcher for Kinesis — daily OHLCV bars + the universe list.

Uses the polygon-api-client SDK. ``list_tickers`` returns names alphabetically
(NOT liquidity-sorted) — apply a liquidity cut post-backfill via
scripts/rank_universe_by_liquidity.py.
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
        aggs = self.client.list_aggs(
            ticker=symbol.upper(), multiplier=1, timespan="day",
            from_=from_date, to=to_date, limit=50000,
        )
        out: List[Dict] = []
        for b in aggs:
            ts = datetime.fromtimestamp(b.timestamp / 1000, tz=timezone.utc)
            out.append({
                "timestamp": ts, "timeframe": "1d",
                "open": float(b.open), "high": float(b.high), "low": float(b.low),
                "close": float(b.close), "volume": int(b.volume or 0),
                "adjusted_close": float(b.close),
            })
        return out

    def list_us_common_stocks(self, limit: int = 1000) -> List[Dict]:
        """Active US common stocks (reference tickers), SPACs/shells filtered out.
        Alphabetical, NOT liquidity-sorted — rank by volume after backfill."""
        out: List[Dict] = []
        for t in self.client.list_tickers(market="stocks", type="CS", active=True, limit=1000):
            sym = getattr(t, "ticker", None)
            name = getattr(t, "name", None) or ""
            if not (sym and sym.isalpha() and getattr(t, "type", None) == "CS"):
                continue
            low = name.lower()
            if "acquisition" in low or "blank check" in low:   # skip SPACs/shells
                continue
            out.append({"symbol": sym, "name": name})
            if len(out) >= limit:
                break
        return out
