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
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import equity_curve_points, get_db, load_closes, load_meta, spy_series
from app.api.schemas import (
    BacktestRequest, BacktestResponse, CompareDelta, CompareRequest, CompareResponse,
    CompareSide, ConfigOut, DefenseState, MetricSet, PortfolioState, SelectionRow,
    SweepPoint, SweepRequest, SweepResponse, TradeRow,
)
from app.models.engine import Engine
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
        points.append(SweepPoint(value=float(val), metrics=r["metrics"]))
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
    """Strategy backtested track record at the DEPLOYED engine config (live-P&L proxy)."""
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
