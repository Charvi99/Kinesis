"""Engines service — read/write persisted engine_3 configs (the config seam).

The backtester takes plain kwargs; THIS module is the only place that maps an
Engine row <-> those kwargs, so API routes stay thin and the backtester is never
touched when config moves from a module dict to a DB row. `defaults.py` remains the
seed (the migration + a DB-empty fallback), NOT the live source of truth.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from sqlalchemy.orm import Session

from app.models.engine import Engine
from app.services.backtest.defend import backtest_momentum_defended
from app.services.backtest.portfolio import backtest_momentum
from app.services.momentum import defaults


# ── Engine <-> backtester kwargs ─────────────────────────────────────────────
def selection_kwargs(eng) -> dict:
    """kwargs for compute_weights() from an Engine (or Engine-like) object."""
    return {
        "lookback": eng.lookback,
        "top_n": eng.top_n,
        "target_vol": eng.target_vol,
        "max_weight": eng.max_weight,
        "regime_gate": eng.regime_gate,
    }


def defended_kwargs(eng) -> dict:
    """kwargs for backtest_momentum_defended() from an Engine object.

    Drops regime_gate — the defended backtester forces it True internally
    (selection gates longs to the bull regime unconditionally there).
    """
    sk = {k: v for k, v in selection_kwargs(eng).items() if k != "regime_gate"}
    return {
        **sk,
        "target_port_vol": eng.target_port_vol,
        "dd_threshold": eng.dd_threshold,
        "de_gross": eng.de_gross,
        "leverage_cap": eng.leverage_cap,
        "cost_bps": eng.cost_bps,
    }


def backtest_for_engine(closes, eng):
    """Run the right backtester (v0 vs defended) for an Engine's `defended` flag."""
    if eng.defended:
        return backtest_momentum_defended(closes, **defended_kwargs(eng))
    return backtest_momentum(
        closes, lookback=eng.lookback, top_n=eng.top_n, target_vol=eng.target_vol,
        max_weight=eng.max_weight, regime_gate=eng.regime_gate, cost_bps=eng.cost_bps,
    )


def engine_to_config_dict(eng) -> dict:
    """The 10-knob ConfigOut shape (no defended/starting_cash)."""
    keys = ["lookback", "top_n", "target_vol", "max_weight", "regime_gate",
            "target_port_vol", "dd_threshold", "de_gross", "leverage_cap", "cost_bps"]
    return {k: getattr(eng, k) for k in keys}


# ── deployed engine access ───────────────────────────────────────────────────
def defaults_engine() -> SimpleNamespace:
    """A synthetic Engine-like built from defaults — the fallback when the DB has
    no row yet (pre-migration / empty test DB). Works with all helpers above via
    getattr, so the read paths never hard-fail."""
    return SimpleNamespace(
        name="prod (seed)", description=None, is_deployed=True,
        lookback=defaults.LOOKBACK, top_n=defaults.TOP_N,
        target_vol=defaults.TARGET_VOL, max_weight=defaults.MAX_WEIGHT,
        regime_gate=defaults.REGIME_GATE, defended=True,
        target_port_vol=defaults.TARGET_PORT_VOL, dd_threshold=defaults.DD_THRESHOLD,
        de_gross=defaults.DE_GROSS, leverage_cap=defaults.LEVERAGE_CAP,
        cost_bps=defaults.COST_BPS, starting_cash=defaults.STARTING_CASH,
    )


def get_deployed_engine(db: Session) -> Optional[Engine]:
    """The deployed engine, else the first row, else None (caller falls back to seed)."""
    eng = db.query(Engine).filter(Engine.is_deployed.is_(True)).first()
    if eng:
        return eng
    return db.query(Engine).order_by(Engine.id).first()


def deployed_or_seed(db: Session):
    """Deployed engine from the DB, or the defaults seed if none exists."""
    return get_deployed_engine(db) or defaults_engine()


def seed_default_engine(db: Session) -> None:
    """Idempotent: insert the `prod` engine if the table is empty.

    The migration already seeds prod on fresh DBs; this covers a running system
    whose DB predates the migration (e.g. a dev DB). Safe to call from app startup.
    """
    if db.query(Engine).count() > 0:
        return
    db.add(Engine(
        name="prod",
        description="engine_3 production config (validated — see RESULTS.md)",
        is_deployed=True,
        lookback=defaults.LOOKBACK, top_n=defaults.TOP_N,
        target_vol=defaults.TARGET_VOL, max_weight=defaults.MAX_WEIGHT,
        regime_gate=defaults.REGIME_GATE, defended=True,
        target_port_vol=defaults.TARGET_PORT_VOL, dd_threshold=defaults.DD_THRESHOLD,
        de_gross=defaults.DE_GROSS, leverage_cap=defaults.LEVERAGE_CAP,
        cost_bps=defaults.COST_BPS, starting_cash=defaults.STARTING_CASH,
    ))
    db.commit()


# ── cached metrics (for the Engines grid) ────────────────────────────────────
def _fin(v):
    import math
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# Keys cached on the Engine row for the Engines card grid (Sharpe/DD/return).
_METRIC_KEYS = ["sharpe", "max_drawdown", "total_return", "ann_return", "ann_vol",
                "psr0", "bull_sharpe", "bear_sharpe"]


def metrics_for_engine(closes, eng) -> dict:
    """Run this engine's backtest and trim to the metrics the grid shows. The
    route caches the result on eng.metrics so list/get stay fast."""
    m = backtest_for_engine(closes, eng)["metrics"]
    return {k: _fin(m.get(k)) for k in _METRIC_KEYS}
