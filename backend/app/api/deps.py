"""Shared API dependencies + price-loading helpers.

`load_closes()` reproduces the close pivot used by scripts/run_backtest.py (the
same matrix the backtester and live ledger consume), so an API backtest equals a
CLI backtest. `spy_series()` gives the benchmark overlay — real SPY if tracked,
else the equal-weight market index the regime gate itself uses.
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db  # re-export get_db


def _rows_to_closes(rows) -> pd.DataFrame:
    """[(stock_id, ts, close), ...] -> closes DataFrame (date x stock_id), ffill."""
    df = pd.DataFrame(rows, columns=["stock_id", "ts", "close"])
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert(None)
    df["close"] = df["close"].astype(float)
    closes = df.pivot(index="ts", columns="stock_id", values="close").sort_index()
    return closes.ffill()


def load_closes(db: Session, tracked_only: bool = True) -> pd.DataFrame:
    """Daily close matrix for the trading universe (date x stock_id)."""
    where = "p.timeframe = '1d'"
    if tracked_only:
        where += " AND s.is_tracked = true"
    rows = db.execute(text(f"""
        SELECT p.stock_id, p.timestamp, p.close
        FROM stock_prices p JOIN stocks s ON s.id = p.stock_id
        WHERE {where}
        ORDER BY p.timestamp
    """)).all()
    return _rows_to_closes(rows)


def load_meta(db: Session) -> Dict[int, dict]:
    """stock_id -> {symbol, name, sector} for mapping weights back to tickers."""
    rows = db.execute(text("SELECT id, symbol, name, sector FROM stocks")).all()
    return {r[0]: {"symbol": r[1], "name": r[2], "sector": r[3]} for r in rows}


def load_symbol_close(db: Session, symbol: str) -> Optional[pd.Series]:
    """Single-symbol daily close series (tz-naive), or None if not present."""
    rows = db.execute(text("""
        SELECT p.timestamp, p.close FROM stock_prices p
        JOIN stocks s ON s.id = p.stock_id
        WHERE s.symbol = :sym AND p.timeframe = '1d'
        ORDER BY p.timestamp
    """), {"sym": symbol}).all()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts", "close"])
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert(None)
    df["close"] = df["close"].astype(float)
    return df.set_index("ts")["close"].sort_index()


def spy_series(db: Session, closes: pd.DataFrame) -> pd.Series:
    """Benchmark price series aligned to `closes.index`.

    Real SPY if it is tracked in the DB; otherwise the equal-weight market index
    that the regime gate (selection.market_regime_masks) builds internally — so the
    benchmark and the gate stay consistent.
    """
    spy = load_symbol_close(db, "SPY")
    if spy is None:
        spy = (1 + closes.pct_change().mean(axis=1)).cumprod()
    return spy.reindex(closes.index).ffill()


def equity_curve_points(
    daily_ret: pd.Series, spy_ret: pd.Series, starting_cash: float, max_points: int = 600
) -> list:
    """Cumulative equity + SPY (both scaled to `starting_cash`), downsampled for the wire."""
    import numpy as np

    eq = (1 + daily_ret.fillna(0.0)).cumprod() * starting_cash
    spy = (1 + spy_ret.reindex(daily_ret.index).fillna(0.0)).cumprod() * starting_cash
    df = pd.DataFrame({"equity": eq, "spy": spy}, index=daily_ret.index)
    if len(df) > max_points:
        step = int(np.ceil(len(df) / max_points))
        last = df.iloc[[-1]]
        df = pd.concat([df.iloc[::step], last]).drop_duplicates()
    return [
        {"date": d.strftime("%Y-%m-%d"), "equity": round(float(e), 2), "spy": round(float(s), 2)}
        for d, e, s in zip(df.index, df["equity"], df["spy"])
    ]


def equity_curve_from_snapshots(
    eq: pd.Series, spy_px: pd.Series, max_points: int = 600
) -> list:
    """Display curve from the ledger's absolute-equity snapshots + a SPY price overlay.

    Used by the LIVE portfolio path. The snapshots already ARE the equity curve (absolute
    $), so plot them directly rather than re-compounding returns from a base — the earlier
    re-compound bug plotted from `acct.starting_cash`, which for a bridged account is the
    carried backtest ENDPOINT (≈$298k), not the original capital ($100k), so the curve was
    scaled ~3× too large and started at the wrong value.

    SPY (a price series on closes.index) is rebased to the first snapshot's equity so both
    lines start together for an apples-to-apples comparison. Indexes are aligned by
    calendar DATE: snapshot dates are midnight-normalized while closes.index can carry a
    time component, so both are normalized before reindex — otherwise SPY reindexes to
    nothing and renders as a dead-flat line (the regression this fixes)."""
    import numpy as np

    eq = eq.copy()
    eq.index = pd.DatetimeIndex(eq.index).normalize()
    spy = spy_px.copy()
    spy.index = pd.DatetimeIndex(spy.index).normalize()
    spy = spy.reindex(eq.index).ffill()

    start = float(eq.iloc[0]) if len(eq) else 0.0
    spy0 = float(spy.iloc[0]) if len(spy) else 0.0
    spy_rebased = spy * (start / spy0) if spy0 > 0 else spy

    df = pd.DataFrame({"equity": eq.values, "spy": spy_rebased.values}, index=eq.index)
    if len(df) > max_points:
        step = int(np.ceil(len(df) / max_points))
        last = df.iloc[[-1]]
        df = pd.concat([df.iloc[::step], last]).drop_duplicates()
    return [
        {"date": d.strftime("%Y-%m-%d"), "equity": round(float(e), 2), "spy": round(float(s), 2)}
        for d, e, s in zip(df.index, df["equity"], df["spy"])
    ]
