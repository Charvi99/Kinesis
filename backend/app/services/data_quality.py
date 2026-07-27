"""Price-series data-quality checks for the backfill.

The backfill fetches each ticker's *current* symbol across a multi-year window.
For tickers that changed (FB->META, BK->BNY, FISV->FI) or had unhandled corporate
actions, Polygon returns placeholder/synthetic data for the gap, which surfaces as
(a) flat zones (a stale value repeated for many days) and (b) impossible single-day
moves when the series snaps back to reality (META +1395%, BNY +1263% in one day).
These validators reject such series before they contaminate the trading universe.

Thresholds are deliberately conservative: real high-beta names (CVNA, APP, DOC) do
move 40-60% on a single day, so the move gate sits at 80% — only rename/placeholder
corruption exceeds it. The flat-zone gate catches the stale-placeholder mode that
can sneak in under the move gate.
"""
from __future__ import annotations

from typing import Dict, List

IMPOSSIBLE_MOVE = 0.80   # |daily return| above this is corruption (continuous data never moves >80%/day)
FLAT_RUN_LIMIT = 10      # >= N consecutive near-identical closes = placeholder/stale data


def _longest_flat_run(values: List[float], tol: float = 0.01) -> int:
    best = run = 1
    for i in range(1, len(values)):
        run = run + 1 if abs(values[i] - values[i - 1]) <= tol else 1
        best = max(best, run)
    return best


def validate_bars(bars: List[Dict]) -> Dict:
    """Validate a fetched bar list (the form PolygonFetcher.fetch_daily_bars returns)."""
    closes = [float(b["close"]) for b in bars if b.get("close") is not None]
    return _validate(closes)


def validate_series(closes) -> Dict:
    """Validate a close Series (DB-loaded form)."""
    import math
    vals = [float(x) for x in closes.dropna().tolist()] if hasattr(closes, "dropna") else [float(x) for x in closes]
    return _validate(vals)


def _validate(closes: List[float]) -> Dict:
    flags: Dict = {"ok": True, "n": len(closes), "max_daily_move": 0.0, "longest_flat_run": 0, "reasons": []}
    if len(closes) < 30:
        flags["ok"] = False
        flags["reasons"].append("insufficient_history")
        return flags
    max_move = 0.0
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev > 0:
            max_move = max(max_move, abs(closes[i] / prev - 1.0))
    flat = _longest_flat_run(closes)
    flags["max_daily_move"] = max_move
    flags["longest_flat_run"] = flat
    if max_move > IMPOSSIBLE_MOVE:
        flags["ok"] = False
        flags["reasons"].append(f"impossible_move_{max_move:.2f}")
    if flat >= FLAT_RUN_LIMIT:
        flags["ok"] = False
        flags["reasons"].append(f"flat_zone_{flat}")
    return flags
