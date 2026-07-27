"""Kinesis portfolio API (/api/v1).

Five endpoints over the existing pure engine (momentum.selection + backtest).
No live ledger yet (EXTRACTION_PLAN step 7), so:
  - /backtest, /config: real, read from the backtester.
  - /portfolio/state: the strategy's *backtested track record* at production
    config (proxy for live P&L until the ledger exists).
  - /selection: the *current* target weights + momentum ranks (causal, as-of now).
  - /trades: round-trips *derived* from the selection's weight history
    (rank_drop / regime-flatten reasons) — a faithful approximation.
"""
from __future__ import annotations

import math
from typing import List

import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    equity_curve_points, get_db, load_closes, load_meta, spy_series,
)
from app.api.schemas import (
    BacktestRequest, BacktestResponse, ConfigOut, DefenseState, MetricSet,
    PortfolioState, SelectionRow, TradeRow,
)
from app.services.backtest.defend import backtest_momentum_defended
from app.services.backtest.metrics import summarize
from app.services.backtest.portfolio import backtest_momentum
from app.services.momentum.defaults import (
    CONFIG, DD_THRESHOLD, DE_GROSS, LEVERAGE_CAP, LOOKBACK, STARTING_CASH,
    TARGET_PORT_VOL, defended_kwargs, selection_kwargs,
)
from app.services.momentum.selection import compute_weights, market_regime_masks

router = APIRouter(prefix="/api/v1", tags=["portfolio"])


# ── helpers ───────────────────────────────────────────────────────────────────
def _fin(v):
    """Finite float or None (keeps NaN/inf out of the JSON — JSON.parse rejects them)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _metric_set(m: dict) -> MetricSet:
    return MetricSet(
        total_return=_fin(m.get("total_return")) or 0.0,
        ann_return=_fin(m.get("ann_return")) or 0.0,
        ann_vol=_fin(m.get("ann_vol")) or 0.0,
        sharpe=_fin(m.get("sharpe")) or 0.0,
        max_drawdown=_fin(m.get("max_drawdown")) or 0.0,
        psr0=_fin(m.get("psr0")),
        avg_exposure=_fin(m.get("avg_exposure")),
        avg_turnover=_fin(m.get("avg_turnover")),
        bear_sharpe=_fin(m.get("bear_sharpe")),
        bull_sharpe=_fin(m.get("bull_sharpe")),
    )


def _build_metrics(win, weights, bear_mask) -> dict:
    """MetricSet fields from a (possibly windowed) daily-return Series."""
    m = dict(summarize(win))
    if len(win) and weights is not None:
        ww = weights.reindex(win.index)
        m["avg_exposure"] = float(ww.sum(axis=1).mean())
        to = ww.diff().abs().sum(axis=1)
        m["avg_turnover"] = float(to.iloc[1:].mean()) if len(to) > 1 else 0.0
        bear_days = win.index.isin(bear_mask[bear_mask].index)
        m["bear_sharpe"] = summarize(win[bear_days])["sharpe"] if bear_days.sum() else float("nan")
        m["bull_sharpe"] = summarize(win[~bear_days])["sharpe"] if (~bear_days).sum() else float("nan")
    return m


def _count_entries(weights) -> int:
    """Number of 0->active weight transitions (buys) — a trades_count proxy."""
    if weights is None or not len(weights):
        return 0
    active = (weights.fillna(0.0) > 0).astype(int)
    return int((active.diff().fillna(0) == 1).sum(axis=1).sum())


# In-process cache for the default-config defended run (drives /portfolio/state
# + /trades). A full 5y backtest is ~1-2s; this avoids re-running on every reload.
_cache = {"at": 0.0, "payload": None}


def _default_defended(db: Session) -> dict:
    import time
    now = time.time()
    if _cache["payload"] and (now - _cache["at"]) < 60:
        return _cache["payload"]
    closes = load_closes(db)
    spy = spy_series(db, closes)
    res = backtest_momentum_defended(closes, **defended_kwargs())
    payload = {"closes": closes, "spy": spy, "res": res}
    _cache.update(at=now, payload=payload)
    return payload


# ── endpoints ─────────────────────────────────────────────────────────────────
@router.get("/config", response_model=ConfigOut)
def get_config():
    """Read-only engine config (edit momentum/defaults.py + redeploy to change)."""
    return ConfigOut(**CONFIG)


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    closes = load_closes(db)
    spy = spy_series(db, closes)
    spy_ret = spy.pct_change()
    bear_mask = market_regime_masks(closes)[1]

    if req.defended:
        res = backtest_momentum_defended(
            closes, lookback=req.lookback, top_n=req.top_n, target_vol=req.target_vol,
            max_weight=req.max_weight, target_port_vol=req.target_port_vol,
            dd_threshold=req.dd_threshold, de_gross=req.de_gross,
            leverage_cap=req.leverage_cap, cost_bps=req.cost_bps,
        )
    else:
        res = backtest_momentum(
            closes, lookback=req.lookback, top_n=req.top_n, target_vol=req.target_vol,
            max_weight=req.max_weight, regime_gate=req.regime_gate, cost_bps=req.cost_bps,
        )

    daily = res["daily_returns"]
    weights = res["weights"]
    win = daily
    if req.start_date or req.end_date:
        win = daily.loc[req.start_date:req.end_date]
        if win.empty:
            win = daily

    m = _build_metrics(win, weights, bear_mask)
    curve = equity_curve_points(win, spy_ret, STARTING_CASH)
    return BacktestResponse(
        metrics=_metric_set(m), equity_curve=curve, trades_count=_count_entries(weights),
        defended=req.defended, start_date=req.start_date, end_date=req.end_date,
    )


@router.get("/portfolio/state", response_model=PortfolioState)
def portfolio_state(db: Session = Depends(get_db)):
    """Strategy backtested track record at production config (proxy for live P&L)."""
    payload = _default_defended(db)
    closes, spy, res = payload["closes"], payload["spy"], payload["res"]
    daily = res["daily_returns"]
    weights = res["weights"]
    spy_ret = spy.pct_change()
    bull_mask, bear_mask = market_regime_masks(closes)

    eq = (1 + daily.fillna(0.0)).cumprod() * STARTING_CASH
    final_equity = float(eq.iloc[-1]) if len(eq) else STARTING_CASH
    rv = float(daily.tail(63).std() * np.sqrt(252)) if len(daily) >= 2 else 0.0
    factor = min(TARGET_PORT_VOL / rv, LEVERAGE_CAP) if rv > 0 else 1.0
    dd = float(eq.iloc[-1] / eq.cummax().iloc[-1] - 1) if len(eq) else 0.0

    m = _build_metrics(daily, weights, bear_mask)
    # Current exposure: the backtester skips the final day (no T+1 to earn), so its
    # last weight row is zeros. Reconstruct live exposure from the as-of target gross
    # scaled by the current vol-target factor and the drawdown throttle.
    sel_last = float(compute_weights(closes, **selection_kwargs()).iloc[-1].sum())
    throttle = DE_GROSS if dd < -DD_THRESHOLD else 1.0
    exposure = max(0.0, min(sel_last * factor * throttle, LEVERAGE_CAP))
    return PortfolioState(
        equity=final_equity, starting_cash=STARTING_CASH,
        equity_curve=equity_curve_points(daily, spy_ret, STARTING_CASH),
        metrics=_metric_set(m),
        regime="bull" if bool(bull_mask.iloc[-1]) else "bear",
        exposure=exposure,
        defense=DefenseState(vol_target_factor=float(factor), drawdown=dd, dd_threshold=DD_THRESHOLD),
        as_of=closes.index[-1].strftime("%Y-%m-%d") if len(closes) else "",
    )


@router.get("/selection", response_model=List[SelectionRow])
def selection(limit: int = Query(default=50, ge=1, le=1000), db: Session = Depends(get_db)):
    """Universe ranked by 252d momentum, current target weights + held/changed flags."""
    closes = load_closes(db)
    meta = load_meta(db)
    if len(closes) < 2:
        return []

    W = compute_weights(closes, **selection_kwargs())
    mom = closes.pct_change(LOOKBACK)
    w_today, w_prev = W.iloc[-1], W.iloc[-2]
    mom_today = mom.iloc[-1]
    held_today = set(w_today[w_today > 0].index)
    held_prev = set(w_prev[w_prev > 0].index)
    ranked = mom_today.rank(method="first", ascending=False).fillna(10 ** 9).astype(int)

    rows = []
    for sid in closes.columns:
        info = meta.get(int(sid), {})
        changed = (
            "add" if (sid in held_today and sid not in held_prev)
            else "drop" if (sid not in held_today and sid in held_prev)
            else None
        )
        rows.append(SelectionRow(
            symbol=info.get("symbol") or str(sid),
            name=info.get("name"),
            momentum_score=_fin(mom_today.get(sid)) or 0.0,
            rank=int(ranked.get(sid, 999999)),
            weight=_fin(w_today.get(sid)) or 0.0,
            held=sid in held_today,
            changed=changed,
        ))
    rows.sort(key=lambda r: r.rank)
    return rows[:limit]


@router.get("/trades", response_model=List[TradeRow])
def trades(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)):
    """Closed round-trips derived from the selection's weight history.

    Entry = a name entering the top-N target set; exit = leaving it. Reason is
    'defense' when the exit coincides with a regime flatten (whole book to cash),
    'rank_drop' otherwise. An honest, ledger-free approximation of the trade log.
    """
    payload = _default_defended(db)
    closes = payload["closes"]
    meta = load_meta(db)
    W = compute_weights(closes, **selection_kwargs())
    _, bear_mask = market_regime_masks(closes)
    dates = W.index
    px = closes.reindex(dates)

    out: List[TradeRow] = []
    for sid in W.columns:
        if sid not in px.columns:
            continue
        active = (W[sid] > 0)
        in_pos = False
        entry_i = None
        for i in range(len(dates)):
            on = bool(active.iloc[i])
            if on and not in_pos:
                in_pos, entry_i = True, i
            elif not on and in_pos:
                entry_px = float(px[sid].iloc[entry_i])
                exit_px = float(px[sid].iloc[i])
                if math.isfinite(entry_px) and entry_px > 0 and math.isfinite(exit_px):
                    info = meta.get(int(sid), {})
                    reason = "defense" if bool(bear_mask.reindex(dates).iloc[i]) else "rank_drop"
                    out.append(TradeRow(
                        symbol=info.get("symbol") or str(sid),
                        entry_date=dates[entry_i].strftime("%Y-%m-%d"),
                        exit_date=dates[i].strftime("%Y-%m-%d"),
                        entry=round(entry_px, 4), exit=round(exit_px, 4),
                        ret=float(exit_px / entry_px - 1.0), reason=reason,
                    ))
                in_pos = False
    out.sort(key=lambda t: t.exit_date, reverse=True)
    return out[:limit]
