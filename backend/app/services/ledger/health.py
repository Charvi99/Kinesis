"""Ledger health — staleness + reconciliation for a paper account.

Staleness: is the account's last snapshot current with the bar feed? Reconciliation:
does the stored book satisfy the accounting identity (equity == cash + positions mark at
the snapshot's close) within tolerance? Both are surfaced via /health and
/reconciliation and feed the digest's warnings section.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Dict, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.api.deps import load_closes
from app.models.ledger import PaperAccount, PaperEquitySnapshot, PaperPosition

STALE_DAYS = 3


def last_snapshot(db: Session, account: PaperAccount) -> Optional[PaperEquitySnapshot]:
    return (db.query(PaperEquitySnapshot)
            .filter_by(account_id=account.id)
            .order_by(PaperEquitySnapshot.date.desc()).first())


def staleness(db: Session, account: PaperAccount) -> Dict:
    """Is the account booked up to the bar feed?

    {'status': 'no_data'|'stale'|'ok', 'last_date', 'latest_bar', 'feed_age_days'}
      - no_data: the bar feed itself is empty
      - stale: the account's last snapshot is behind the latest bar, OR the feed is
        itself stale (no new bar in STALE_DAYS — weekend/holiday/outage)
      - ok: the last snapshot == the latest bar"""
    closes = load_closes(db)
    if not len(closes):
        return {"status": "no_data", "last_date": None, "latest_bar": None,
                "feed_age_days": None}
    latest_bar = closes.index[-1].date()
    feed_age = (date.today() - latest_bar).days
    snap = last_snapshot(db, account)
    if snap is None:
        return {"status": "stale", "last_date": None,
                "latest_bar": latest_bar.isoformat(), "feed_age_days": feed_age}
    last_date = snap.date
    if last_date >= latest_bar and feed_age <= STALE_DAYS:
        status = "ok"
    else:
        status = "stale"
    return {"status": status, "last_date": last_date.isoformat(),
            "latest_bar": latest_bar.isoformat(), "feed_age_days": feed_age}


def reconcile_account(db: Session, account: PaperAccount, tolerance: float = 0.05) -> Dict:
    """Verify the accounting identity for the last snapshot, marked at THAT snapshot's
    close (so a stale-but-consistent book passes; only real drift fails):

      snapshot.equity ≈ account.cash + Σ(qty × close[as_of])   within `tolerance`
      snapshot.cash   ≈ account.cash                           within `tolerance`

    Returns per-check detail + an aggregate `ok`. Tolerance defaults to 5¢ (sub-cent
    drift from fractional-share quantization is expected and harmless)."""
    closes = load_closes(db)
    snap = last_snapshot(db, account)
    positions = db.query(PaperPosition).filter_by(account_id=account.id).all()

    # mark at the snapshot's own close when possible (apples-to-apples with snapshot.equity).
    # closes.index is Timestamps; snap.date is a date -> compare/lookup via Timestamp.
    as_of = None
    as_of_ts = None
    if snap is not None and len(closes):
        ts = pd.Timestamp(snap.date)
        if ts in closes.index:
            as_of, as_of_ts = snap.date, ts
    if as_of is None and len(closes):
        as_of_ts = closes.index[-1]
        as_of = as_of_ts.date()
    close_row = closes.loc[as_of_ts] if as_of_ts is not None else None

    mark = 0.0
    if close_row is not None:
        for p in positions:
            px = float(close_row.get(p.stock_id, float("nan")))
            if math.isfinite(px):
                mark += float(p.quantity) * px

    live_cash = float(account.cash)
    expected_equity = live_cash + mark
    identity_ok = True
    cash_ok = True
    snapshot_equity = None
    snapshot_cash = None
    if snap is not None:
        snapshot_equity = float(snap.equity)
        snapshot_cash = float(snap.cash)
        identity_ok = abs(snapshot_equity - expected_equity) <= tolerance
        cash_ok = abs(snapshot_cash - live_cash) <= tolerance

    return {
        "ok": identity_ok and cash_ok,
        "tolerance": tolerance,
        "as_of": as_of.isoformat() if as_of is not None else None,
        "cash": live_cash,
        "positions_value": mark,
        "expected_equity": expected_equity,
        "snapshot_equity": snapshot_equity,
        "snapshot_cash": snapshot_cash,
        "identity_ok": identity_ok,
        "cash_ok": cash_ok,
        "open_positions": len(positions),
    }
