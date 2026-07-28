"""Kinesis portfolio API (/api/v1).

Endpoints over the pure engine (momentum.selection + backtest):
  - /backtest, /config: real, read from the backtester.
  - /portfolio/state: the strategy's *backtested track record* at the DEPLOYED engine
    config (proxy for live P&L until the ledger exists — EXTRACTION_PLAN step 7).
  - /selection: the *current* target weights + momentum ranks (causal, as-of now).
  - /trades: round-trips *derived* from the selection's weight history.
  - /backtest/sweep, /backtest/compare: knob exploration over the same engine.

The DEPLOYED engine (one Engine row, is_deployed=True) is the source of truth for the
knobs; defaults.py is only the seed/fallback. See momentum/engines.py for the seam.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    equity_curve_from_snapshots, equity_curve_points, get_db, load_closes, load_meta,
    spy_series,
)
from app.api.schemas import (
    BacktestRequest, BacktestResponse, CompareDelta, CompareRequest, CompareResponse,
    CompareSide, ConfigOut, DefenseState, MetricSet, PortfolioState, SelectionRow,
    SweepPoint, SweepRequest, SweepResponse, TradeRow,
)
from app.models.engine import Engine
from app.models.ledger import PaperAccount, PaperEquitySnapshot, PaperFill, PaperPosition
from app.services.backtest.metrics import summarize
from app.services.momentum import defaults
from app.services.momentum.engines import (
    backtest_for_engine, deployed_or_seed, engine_to_config_dict,
    selection_kwargs as engine_selection_kwargs,
)
from app.services.momentum.selection import compute_weights, market_regime_masks

router = APIRouter(prefix="/api/v1", tags=["portfolio"])

# Knobs a sweep may vary (categorical/window fields excluded).
SWEEPABLE_KNOBS = {
    "lookback", "top_n", "target_vol", "max_weight", "target_port_vol",
    "dd_threshold", "de_gross", "leverage_cap", "cost_bps",
}


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


def _run_req(closes, req: BacktestRequest):
    """Dispatch a BacktestRequest to the right backtester (v0 vs defended)."""
    from app.services.backtest.defend import backtest_momentum_defended
    from app.services.backtest.portfolio import backtest_momentum

    if req.defended:
        return backtest_momentum_defended(
            closes, lookback=req.lookback, top_n=req.top_n, target_vol=req.target_vol,
            max_weight=req.max_weight, target_port_vol=req.target_port_vol,
            dd_threshold=req.dd_threshold, de_gross=req.de_gross,
            leverage_cap=req.leverage_cap, cost_bps=req.cost_bps,
        )
    return backtest_momentum(
        closes, lookback=req.lookback, top_n=req.top_n, target_vol=req.target_vol,
        max_weight=req.max_weight, regime_gate=req.regime_gate, cost_bps=req.cost_bps,
    )


def _backtest_from_req(closes, spy_ret, bear_mask, req: BacktestRequest, starting_cash: float) -> dict:
    """Run one req → {metrics(MetricSet), equity_curve, trades_count}.

    Shared by /backtest, /backtest/sweep, /backtest/compare so they all window +
    summarize identically.
    """
    res = _run_req(closes, req)
    daily = res["daily_returns"]
    weights = res["weights"]
    win = daily
    if req.start_date or req.end_date:
        win = daily.loc[req.start_date:req.end_date]
        if win.empty:
            win = daily
    m = _build_metrics(win, weights, bear_mask)
    curve = equity_curve_points(win, spy_ret, starting_cash)
    return {"metrics": _metric_set(m), "equity_curve": curve, "trades_count": _count_entries(weights)}


def _engine_to_req(eng, start_date=None, end_date=None) -> BacktestRequest:
    """An Engine row → a BacktestRequest (the shape sweep/compare operate on)."""
    return BacktestRequest(
        lookback=eng.lookback, top_n=eng.top_n, target_vol=eng.target_vol,
        max_weight=eng.max_weight, regime_gate=eng.regime_gate, defended=eng.defended,
        target_port_vol=eng.target_port_vol, dd_threshold=eng.dd_threshold,
        de_gross=eng.de_gross, leverage_cap=eng.leverage_cap, cost_bps=eng.cost_bps,
        start_date=start_date, end_date=end_date,
    )


def _get_engine_or_404(db: Session, engine_id: int) -> Engine:
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    return eng


# In-process cache for the deployed-engine run (drives /portfolio/state + /trades).
# A full 5y backtest is ~1-2s; this avoids re-running on every reload.
_cache = {"at": 0.0, "payload": None}


def invalidate_state_cache() -> None:
    """Bust the deployed-engine cache — call after a deploy / config change
    (imported by the engines router's deploy endpoint)."""
    _cache.update(at=0.0, payload=None)


def _default_backtest(db: Session) -> dict:
    import time
    now = time.time()
    if _cache["payload"] and (now - _cache["at"]) < 60:
        return _cache["payload"]
    eng = deployed_or_seed(db)
    closes = load_closes(db)
    spy = spy_series(db, closes)
    res = backtest_for_engine(closes, eng)
    payload = {"eng": eng, "closes": closes, "spy": spy, "res": res}
    _cache.update(at=now, payload=payload)
    return payload


# ── live ledger (prefer real positions/snapshots when a live account exists) ──
def _live_account(db: Session):
    """The deployed engine's LIVE paper account, or None (→ modeled fallback)."""
    eng = deployed_or_seed(db)
    if not hasattr(eng, "id"):
        return None
    return (db.query(PaperAccount)
            .filter(PaperAccount.engine_id == eng.id, PaperAccount.is_live.is_(True))
            .first())


def _live_state(db: Session, acct, closes, spy, eng, bear_mask):
    """PortfolioState from the account's snapshots (the real book), or None if too few.

    Curve + metrics span the full snapshot history (bridge + live) so the track record
    is continuous and the defense has history; `live=True` flags it as the real book."""
    snaps = (db.query(PaperEquitySnapshot).filter_by(account_id=acct.id)
             .order_by(PaperEquitySnapshot.date).all())
    if len(snaps) < 2:
        return None
    from app.services.ledger.cycle import defense_factor

    eq = pd.Series([float(s.equity) for s in snaps],
                   index=pd.DatetimeIndex([s.date for s in snaps]))
    daily = eq.pct_change().dropna()
    starting = float(acct.starting_cash)
    last = snaps[-1]
    df = defense_factor(eng, eq)
    m = _build_metrics(daily, None, bear_mask)
    return PortfolioState(
        equity=float(last.equity), starting_cash=starting, live=True,
        equity_curve=equity_curve_from_snapshots(eq, spy),
        metrics=_metric_set(m),
        regime="bull" if not bool(bear_mask.iloc[-1]) else "bear",
        exposure=_fin(last.gross_exposure) or 0.0,
        defense=DefenseState(vol_target_factor=float(df["factor"]),
                             drawdown=float(df["dd"]), dd_threshold=eng.dd_threshold),
        as_of=last.date.isoformat(),
    )


def _live_selection(db: Session, acct, eng, closes, meta, limit: int):
    """Real current holdings as SelectionRows (weight from the live book; momentum/rank
    from the universe for context). held=True; changed=None (use /fills for activity)."""
    positions = db.query(PaperPosition).filter_by(account_id=acct.id).all()
    from app.services.ledger.health import last_snapshot
    snap = last_snapshot(db, acct)
    equity = float(snap.equity) if snap else float(acct.cash)
    close_row = closes.iloc[-1]
    mom = closes.pct_change(eng.lookback).iloc[-1]
    ranked = mom.rank(method="first", ascending=False).fillna(10 ** 9).astype(int)
    rows = []
    for p in positions:
        sid = p.stock_id
        px = float(close_row.get(sid, float("nan")))
        if not math.isfinite(px) or float(p.quantity) <= 0:
            continue
        info = meta.get(int(sid), {})
        rows.append(SelectionRow(
            symbol=info.get("symbol") or str(sid), name=info.get("name"),
            momentum_score=_fin(mom.get(sid)) or 0.0, rank=int(ranked.get(sid, 999999)),
            weight=_fin(float(p.quantity) * px / equity) or 0.0, held=True, changed=None,
        ))
    rows.sort(key=lambda r: r.weight, reverse=True)
    return rows[:limit]


def _live_trades(db: Session, acct, closes, meta, limit: int):
    """Round-trips reconstructed from the account's fills (FIFO lots) — the real trade
    log. Closed lots become trips at the sell; open lots are marked at the latest close."""
    fills = (db.query(PaperFill).filter_by(account_id=acct.id)
             .order_by(PaperFill.cycle_id.asc(), PaperFill.id.asc()).all())
    lots: dict = {}              # sid -> [[qty, price, entry_date_str], ...]
    out = []                     # (sid, entry, exit, entry_date, exit_date, reason)
    for f in fills:
        sid = f.stock_id
        if f.side == "buy":
            lots.setdefault(sid, []).append([float(f.quantity), float(f.price), f.cycle_id.isoformat()])
            continue
        to_close = float(f.quantity)
        while to_close > 1e-9 and lots.get(sid):
            lot = lots[sid][0]
            q = min(to_close, lot[0])
            lot[0] -= q
            if lot[0] <= 1e-9:
                lots[sid].pop(0)
            to_close -= q
            out.append((sid, lot[1], float(f.price), lot[2], f.cycle_id.isoformat(), f.reason))
    close_row = closes.iloc[-1] if len(closes) else None
    for sid, stack in lots.items():           # open lots -> open trips at latest close
        px = float(close_row.get(sid, float("nan"))) if close_row is not None else float("nan")
        if not math.isfinite(px):
            continue
        for lot in stack:
            out.append((sid, lot[1], px, lot[2], "", "open"))
    out.sort(key=lambda t: (t[4] or t[3]), reverse=True)
    rows = []
    for sid, entry, exitp, ed, xd, reason in out:
        info = meta.get(int(sid), {})
        rows.append(TradeRow(
            symbol=info.get("symbol") or str(sid), entry_date=ed, exit_date=xd,
            entry=round(entry, 4), exit=round(exitp, 4),
            ret=float(exitp / entry - 1.0) if entry else 0.0, reason=reason,
        ))
    return rows[:limit]


# ── endpoints ─────────────────────────────────────────────────────────────────
@router.get("/config", response_model=ConfigOut)
def get_config(db: Session = Depends(get_db)):
    """The DEPLOYED engine's knobs (read-only display; manage via /engines)."""
    eng = deployed_or_seed(db)
    return ConfigOut(**engine_to_config_dict(eng))


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    closes = load_closes(db)
    spy_ret = spy_series(db, closes).pct_change()
    bear_mask = market_regime_masks(closes)[1]
    r = _backtest_from_req(closes, spy_ret, bear_mask, req, defaults.STARTING_CASH)
    return BacktestResponse(
        metrics=r["metrics"], equity_curve=r["equity_curve"], trades_count=r["trades_count"],
        defended=req.defended, start_date=req.start_date, end_date=req.end_date,
    )


@router.post("/backtest/sweep", response_model=SweepResponse)
def backtest_sweep(req: SweepRequest, db: Session = Depends(get_db)):
    """Sweep ONE knob across `values` over a base engine → metrics per value.

    The base is the engine named by `engine_id` (or the deployed one). Each value is
    re-validated through BacktestRequest's Field constraints, so out-of-range values
    422 rather than reaching the backtester.
    """
    if req.knob not in SWEEPABLE_KNOBS:
        raise HTTPException(400, f"knob must be one of {sorted(SWEEPABLE_KNOBS)}")
    eng = _get_engine_or_404(db, req.engine_id) if req.engine_id else deployed_or_seed(db)
    base = _engine_to_req(eng, req.start_date, req.end_date)
    closes = load_closes(db)
    spy_ret = spy_series(db, closes).pct_change()
    bear_mask = market_regime_masks(closes)[1]

    points = []
    for v in req.values:
        val = int(round(v)) if req.knob in ("lookback", "top_n") else float(v)
        # Reconstruct (not model_copy) so Field ge/le constraints re-validate `val`.
        b = BacktestRequest(**{**base.model_dump(), req.knob: val})
        r = _backtest_from_req(closes, spy_ret, bear_mask, b, defaults.STARTING_CASH)
        points.append(SweepPoint(value=float(val), metrics=r["metrics"], equity_curve=r["equity_curve"]))
    return SweepResponse(knob=req.knob, base=ConfigOut(**engine_to_config_dict(eng)), points=points)


@router.post("/backtest/compare", response_model=CompareResponse)
def backtest_compare(req: CompareRequest, db: Session = Depends(get_db)):
    """Run two configs side by side → metrics + equity for each + a delta (a − b)."""
    closes = load_closes(db)
    spy_ret = spy_series(db, closes).pct_change()
    bear_mask = market_regime_masks(closes)[1]
    cash = defaults.STARTING_CASH

    a_name, a_req = _resolve_compare_side(db, req.a_engine_id, req.a, req.start_date, req.end_date)
    b_name, b_req = _resolve_compare_side(db, req.b_engine_id, req.b, req.start_date, req.end_date)
    ra = _backtest_from_req(closes, spy_ret, bear_mask, a_req, cash)
    rb = _backtest_from_req(closes, spy_ret, bear_mask, b_req, cash)

    def _side(name, r):
        return CompareSide(name=name, metrics=r["metrics"], equity_curve=r["equity_curve"])

    return CompareResponse(
        a=_side(a_name, ra), b=_side(b_name, rb),
        delta=CompareDelta(
            sharpe=ra["metrics"].sharpe - rb["metrics"].sharpe,
            max_drawdown=ra["metrics"].max_drawdown - rb["metrics"].max_drawdown,
            total_return=ra["metrics"].total_return - rb["metrics"].total_return,
        ),
    )


def _resolve_compare_side(db, engine_id, inline, start_date, end_date):
    """(name, BacktestRequest) for one compare side: engine_id wins, else inline req,
    else the deployed engine."""
    if engine_id is not None:
        eng = _get_engine_or_404(db, engine_id)
        return eng.name, _engine_to_req(eng, start_date, end_date)
    if inline is not None:
        req = inline.model_copy(update={
            "start_date": start_date or inline.start_date,
            "end_date": end_date or inline.end_date,
        })
        return "custom", req
    eng = deployed_or_seed(db)
    return eng.name, _engine_to_req(eng, start_date, end_date)


@router.get("/portfolio/state", response_model=PortfolioState)
def portfolio_state(db: Session = Depends(get_db)):
    """Live track record when a live account exists (real book); else the backtested
    track record at the DEPLOYED engine config (modeled P&L proxy)."""
    acct = _live_account(db)
    if acct is not None:
        eng = db.get(Engine, acct.engine_id)
        closes = load_closes(db)
        spy = spy_series(db, closes)
        bear_mask = market_regime_masks(closes)[1]
        st = _live_state(db, acct, closes, spy, eng, bear_mask)
        if st is not None:
            return st
    payload = _default_backtest(db)
    eng, closes, spy, res = payload["eng"], payload["closes"], payload["spy"], payload["res"]
    daily = res["daily_returns"]
    weights = res["weights"]
    spy_ret = spy.pct_change()
    bull_mask, bear_mask = market_regime_masks(closes)
    starting_cash = eng.starting_cash

    eq = (1 + daily.fillna(0.0)).cumprod() * starting_cash
    final_equity = float(eq.iloc[-1]) if len(eq) else starting_cash
    rv = float(daily.tail(63).std() * np.sqrt(252)) if len(daily) >= 2 else 0.0
    factor = min(eng.target_port_vol / rv, eng.leverage_cap) if rv > 0 else 1.0
    dd = float(eq.iloc[-1] / eq.cummax().iloc[-1] - 1) if len(eq) else 0.0

    m = _build_metrics(daily, weights, bear_mask)
    # Current exposure: the backtester skips the final day (no T+1 to earn), so its
    # last weight row is zeros. Reconstruct live exposure from the as-of target gross
    # scaled by the current vol-target factor and the drawdown throttle.
    sel_last = float(compute_weights(closes, **engine_selection_kwargs(eng)).iloc[-1].sum())
    throttle = eng.de_gross if dd < -eng.dd_threshold else 1.0
    exposure = max(0.0, min(sel_last * factor * throttle, eng.leverage_cap))
    return PortfolioState(
        equity=final_equity, starting_cash=starting_cash,
        equity_curve=equity_curve_points(daily, spy_ret, starting_cash),
        metrics=_metric_set(m),
        regime="bull" if bool(bull_mask.iloc[-1]) else "bear",
        exposure=exposure,
        defense=DefenseState(vol_target_factor=float(factor), drawdown=dd, dd_threshold=eng.dd_threshold),
        as_of=closes.index[-1].strftime("%Y-%m-%d") if len(closes) else "",
    )


@router.get("/selection", response_model=list[SelectionRow])
def selection(limit: int = Query(default=50, ge=1, le=1000), db: Session = Depends(get_db)):
    """Universe rank by momentum, current target weights + held/changed flags."""
    eng = deployed_or_seed(db)
    closes = load_closes(db)
    meta = load_meta(db)
    if len(closes) < 2:
        return []

    acct = _live_account(db)
    if acct is not None:
        return _live_selection(db, acct, eng, closes, meta, limit)

    W = compute_weights(closes, **engine_selection_kwargs(eng))
    mom = closes.pct_change(eng.lookback)
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


@router.get("/trades", response_model=list[TradeRow])
def trades(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)):
    """Closed round-trips derived from the selection's weight history.

    Entry = a name entering the top-N target set; exit = leaving it. Reason is
    'defense' when the exit coincides with a regime flatten (whole book to cash),
    'rank_drop' otherwise. An honest, ledger-free approximation of the trade log.
    """
    acct = _live_account(db)
    if acct is not None:
        closes = load_closes(db)
        meta = load_meta(db)
        return _live_trades(db, acct, closes, meta, limit)
    payload = _default_backtest(db)
    eng, closes = payload["eng"], payload["closes"]
    meta = load_meta(db)
    W = compute_weights(closes, **engine_selection_kwargs(eng))
    _, bear_mask = market_regime_masks(closes)
    dates = W.index
    px = closes.reindex(dates)

    out: list[TradeRow] = []
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
