"""The paper-trading cycle — rebalance a live account toward the engine's target book.

Plain function `run_cycle(db, account)` (scheduler-agnostic): callable from a Celery
task, a /run endpoint, or a test. Per latest trading day it (1) skips if a snapshot
already exists for that day (idempotent), (2) builds the regime-gated + defended target
book as-of the latest close, (3) rebalances fractional positions at the close with cost
on turnover, (4) writes fills + a daily equity snapshot. The CALLER commits.

Accounting identity (fractional shares, no rounding): equity_post == equity_pre - cost.
The rebalance, defense factor, and target book are pure helpers so the identity and the
defense math are unit-testable without a DB.

This is the ONE live counterpart of backtest_momentum_defended — same selection
(compute_weights) + same vol-target/drawdown overlay, but real fractional fills instead
of a weight matrix, and the defense reads the account's OWN equity (the real book).
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.api.deps import load_closes
from app.models.engine import Engine
from app.models.ledger import PaperAccount, PaperEquitySnapshot, PaperFill, PaperPosition
from app.services.momentum.engines import selection_kwargs
from app.services.momentum.selection import compute_weights


def _q(x) -> Decimal:
    """Decimal from a float/numpy value via str() (avoids binary-float noise)."""
    return Decimal(str(float(x)))


# ── pure helpers (no DB) ──────────────────────────────────────────────────────
def defense_factor(eng, equity: pd.Series) -> Dict:
    """Live counterpart of backtest_momentum_defended's overlay.

    rv = trailing realized vol of the account's daily returns (needs >=21 pts, else
    undefined -> factor 1.0, matching the backtester warmup); drawdown from the
    account's equity vs its all-time high. Mirrors /portfolio/state exactly so a live
    cycle reproduces the displayed exposure. Returns {factor, throttle, rv, dd}."""
    daily = equity.pct_change().dropna() if len(equity) else pd.Series(dtype=float)
    rv = float(daily.tail(63).std() * math.sqrt(252)) if len(daily) >= 21 else float("nan")
    factor = min(eng.target_port_vol / rv, eng.leverage_cap) if (np.isfinite(rv) and rv > 0) else 1.0
    dd = float(equity.iloc[-1] / equity.cummax().iloc[-1] - 1) if len(equity) else 0.0
    throttle = eng.de_gross if dd < -eng.dd_threshold else 1.0
    return {"factor": float(factor), "throttle": float(throttle), "rv": rv, "dd": dd}


def target_book(closes: pd.DataFrame, eng, factor: float, throttle: float) -> pd.Series:
    """Defended target weights as-of the latest close: regime-gated selection (the
    compute_weights().iloc[-1] seam, NOT the backtester's zero last weight row) scaled
    by the live defense factor + drawdown throttle. Series stock_id -> weight."""
    sel = compute_weights(closes, **selection_kwargs(eng)).iloc[-1]
    return (sel * factor * throttle).clip(lower=0.0)


def rebalance(equity_pre: float, cash: float, holdings: Dict[int, tuple],
              target: pd.Series, close_row: pd.Series, cost_bps: float,
              realized_prev: float) -> Dict:
    """Pure rebalance toward `target` at `close_row` prices, cost on turnover.

    holdings: {stock_id: (qty, avg_cost_or_None)}. Returns the post-state:
      {cash, positions_value, equity, cost, n_fills, realized,
       fills:[{sid,side,qty,price,value,cost,reason}], holdings, post_held}
    Fractional shares at the close => equity == equity_pre - cost (no rounding)."""
    cost_rate = cost_bps / 1e4
    target = target.fillna(0.0)
    held = set(holdings.keys())
    tgt = {int(s) for s in target.index[target > 0]}

    new_cash = cash
    total_cost = 0.0
    n_fills = 0
    realized = realized_prev
    fills = []
    new_holdings: Dict[int, tuple] = {}
    post_held = set()

    for sid in held | tgt:
        px = float(close_row.get(sid, np.nan))
        if not math.isfinite(px) or px <= 0:
            # carry an unchanged position we can't price; can't trade it today
            if sid in holdings:
                new_holdings[sid] = holdings[sid]
            continue
        tw = float(target.get(sid, 0.0) or 0.0)
        target_qty = (tw * equity_pre) / px
        cur_qty, cur_avg = holdings.get(sid, (0.0, None))
        delta = target_qty - cur_qty
        if abs(delta) < 1e-9:
            if cur_qty > 1e-9:
                new_holdings[sid] = (cur_qty, cur_avg)
                post_held.add(sid)
            continue

        trade_value = delta * px                       # +buy / -sell
        cost = abs(trade_value) * cost_rate
        total_cost += cost
        new_cash -= trade_value + cost
        n_fills += 1

        # realized P&L on the sold leg + avg-cost on adds (lot accounting)
        if delta < 0 and cur_avg is not None and cur_qty > 0:
            realized += (px - cur_avg) * abs(delta)
        if delta > 0:
            base = cur_avg if cur_avg is not None else px
            base_qty = cur_qty if cur_avg is not None else 0.0
            new_avg = (base_qty * base + delta * px) / (cur_qty + delta)
        else:
            new_avg = cur_avg

        if target_qty > 1e-9:
            new_holdings[sid] = (target_qty, new_avg)
            post_held.add(sid)
        # target_qty <= 0 => position fully closed (dropped from new_holdings)

        fills.append({
            "sid": sid,
            "side": "buy" if delta > 0 else "sell",
            "qty": abs(delta), "price": px,
            "value": abs(trade_value), "cost": cost,
            "reason": "flatten" if target_qty <= 1e-9 else "rebalance",
        })

    target_gross = float(target.sum())
    positions_value = equity_pre * target_gross
    return {
        "cash": new_cash, "positions_value": positions_value,
        "equity": equity_pre - total_cost, "cost": total_cost, "n_fills": n_fills,
        "realized": realized, "fills": fills, "holdings": new_holdings,
        "post_held": post_held,
    }


# ── equity history (for the defense) ─────────────────────────────────────────
def equity_history(db: Session, account: PaperAccount) -> pd.Series:
    """Past equity curve (date -> float) — the live book's track record. Includes
    bridged backtest history (is_live=False) seeded on /enable, so the defense has
    vol/drawdown history from day one. Sorted ascending by date."""
    rows = (db.query(PaperEquitySnapshot.date, PaperEquitySnapshot.equity)
            .filter(PaperEquitySnapshot.account_id == account.id)
            .order_by(PaperEquitySnapshot.date).all())
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series([float(r[1]) for r in rows],
                     index=pd.DatetimeIndex([r[0] for r in rows]))


def _last_snapshot(db: Session, account: PaperAccount) -> Optional[PaperEquitySnapshot]:
    return (db.query(PaperEquitySnapshot)
            .filter_by(account_id=account.id)
            .order_by(PaperEquitySnapshot.date.desc()).first())


# ── the cycle ─────────────────────────────────────────────────────────────────
def run_cycle(db: Session, account: PaperAccount) -> Dict:
    """Advance the account one trading day. Idempotent per (account, latest close date).
    Mutates the session (positions/fills/snapshot + account.cash); the CALLER commits.
    Returns {date, equity, n_fills, cost, skipped, reason?}."""
    closes = load_closes(db)
    if not len(closes):
        return {"date": None, "equity": None, "n_fills": 0, "cost": 0.0,
                "skipped": True, "reason": "no_data"}
    latest = closes.index[-1]
    cycle_date = latest.date()

    done = db.query(PaperEquitySnapshot).filter_by(
        account_id=account.id, date=cycle_date).first()
    if done is not None:
        return {"date": cycle_date.isoformat(), "equity": float(done.equity),
                "n_fills": 0, "cost": 0.0, "skipped": True, "reason": "already_booked"}

    eng = db.get(Engine, account.engine_id)
    if eng is None:
        return {"date": cycle_date.isoformat(), "equity": None, "n_fills": 0,
                "cost": 0.0, "skipped": True, "reason": "no_engine"}

    eq_hist = equity_history(db, account)
    df = defense_factor(account, eng, eq_hist)
    target = target_book(closes, eng, df["factor"], df["throttle"])
    close_row = closes.iloc[-1]

    positions = {p.stock_id: p for p in
                 db.query(PaperPosition).filter_by(account_id=account.id).all()}
    holdings = {sid: (float(p.quantity),
                      (float(p.avg_cost) if p.avg_cost is not None else None))
                for sid, p in positions.items()}
    cash = float(account.cash)
    positions_value_pre = sum(q * float(close_row.get(sid, 0.0) or 0.0)
                              for sid, (q, _) in holdings.items()
                              if math.isfinite(float(close_row.get(sid, np.nan))))
    equity_pre = cash + positions_value_pre
    last = _last_snapshot(db, account)
    realized_prev = float(last.realized_pnl_cumulative) if last else 0.0

    out = rebalance(equity_pre, cash, holdings, target, close_row,
                    float(eng.cost_bps), realized_prev)

    # ── persist: positions, fills, snapshot, account.cash ──
    for sid, (qty, avg) in out["holdings"].items():
        pos = positions.get(sid)
        if pos is None:
            db.add(PaperPosition(account_id=account.id, stock_id=sid,
                                 quantity=_q(qty), avg_cost=_q(avg) if avg is not None else None))
        else:
            pos.quantity = _q(qty)
            pos.avg_cost = _q(avg) if avg is not None else None
    # any held position absent from the post-state was flattened -> delete
    for sid, pos in positions.items():
        if sid not in out["holdings"]:
            db.delete(pos)

    for f in out["fills"]:
        db.add(PaperFill(
            account_id=account.id, stock_id=f["sid"], cycle_id=cycle_date,
            side=f["side"], quantity=_q(f["qty"]), price=_q(f["price"]),
            value=_q(f["value"]), cost=_q(f["cost"]), reason=f["reason"]))

    equity_post = out["equity"]
    gross = (out["positions_value"] / equity_post) if equity_post > 0 else None
    db.add(PaperEquitySnapshot(
        account_id=account.id, date=cycle_date, cash=_q(out["cash"]),
        positions_value=_q(out["positions_value"]), equity=_q(equity_post),
        gross_exposure=_q(gross) if gross is not None else None,
        realized_pnl_cumulative=_q(out["realized"]),
        open_positions=len(out["post_held"]),
        is_live=bool(account.is_live)))

    account.cash = _q(out["cash"])

    return {"date": cycle_date.isoformat(), "equity": equity_post,
            "n_fills": out["n_fills"], "cost": out["cost"], "skipped": False}
