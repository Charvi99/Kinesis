"""Lean Polygon fetcher for Kinesis — daily OHLCV bars + the universe list.

adjusted=True so every bar is split/dividend-adjusted consistently (without it the
SDK default is inconsistent — NVDA's 2024 split smoothed but COHR's 2022 merger
leaked through). sort='asc' for a clean causal series.

RENAME_MAP handles tickers that changed symbol mid-history (FB->META, BK->BNY).
Fetching the *current* symbol across a window predating the rename yields Polygon
placeholder/synthetic data for the gap (META +1395%, BNY +1263% single-day snaps).
For these we splice: old-ticker bars up to the rename, current-ticker bars after.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from polygon import RESTClient

log = logging.getLogger(__name__)

# current_symbol -> (predecessor_symbol, first_date_current_symbol_is_valid)
RENAME_MAP: Dict[str, Tuple[str, str]] = {
    "META": ("FB", "2022-06-09"),   # Meta Platforms (ex-Facebook)
    "BNY": ("BK", "2024-07-15"),    # BNY Mellon
}


class PolygonFetcher:
    def __init__(self, api_key: Optional[str] = None):
        self.client = RESTClient(api_key or os.getenv("POLYGON_API_KEY"))

    def _raw(self, symbol: str, from_date: str, to_date: str) -> List[Dict]:
        aggs = self.client.list_aggs(
            ticker=symbol.upper(), multiplier=1, timespan="day",
            from_=from_date, to=to_date, adjusted=True, sort="asc", limit=50000,
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

    def fetch_daily_bars(self, symbol: str, from_date: str, to_date: str) -> List[Dict]:
        sym = symbol.upper()
        if sym in RENAME_MAP and from_date < RENAME_MAP[sym][1]:
            old, since = RENAME_MAP[sym]
            try:
                pre = self._raw(old, from_date, since)
                post = self._raw(sym, since, to_date)
                # dedup on timestamp (post wins at the boundary), keep chronological order
                merged = {b["timestamp"]: b for b in pre}
                merged.update({b["timestamp"]: b for b in post})
                bars = sorted(merged.values(), key=lambda b: b["timestamp"])
                log.info(f"rename splice {sym}: {len(pre)} {old}-bars + {len(post)} {sym}-bars -> {len(bars)}")
                return bars
            except Exception as e:
                log.warning(f"rename splice {sym} failed ({e}); falling back to current ticker only")
        return self._raw(sym, from_date, to_date)

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
