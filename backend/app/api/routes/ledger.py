"""Paper-trading ledger API (/api/v1/paper-trading) — live accounts, positions, fills,
equity, health, reconciliation, and the /enable (paper-trade an engine) + /run controls.

/enable is the live on-ramp: it creates a PaperAccount and BRIDGES it from the engine's
backtest — seeding historical equity snapshots (is_live=False) so the live defense has
rv/drawdown history from day one and the equity curve is continuous, then booking the
latest bar as the first LIVE snapshot (is_live=True) by running the real cycle once. The
backtest curve's endpoint is carried in as the live capital, so the track record doesn't
reset at go-live. go_live_at is the OOS boundary.

Read routes are per-account; pass ?engine_id= or the deployed engine's account is used.
POST /run enqueues the Celery cycle (?sync=true runs it inline for ops/tests).
"""
from __future__ import annotations

import math
from decimal import Decimal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, load_closes, load_meta
from app.api.schemas import (
    EnableRequest, EquitySnapshotOut, LedgerHealthOut, PaperAccountOut,
    PaperFillOut, PaperPositionOut, PaperSummaryOut, ReconciliationOut,
)
from app.models.engine import Engine
from app.models.ledger import PaperAccount, PaperEquitySnapshot, PaperFill, PaperPosition
from app.services.ledger.cycle import run_cycle
from app.services.ledger.health import last_snapshot, reconcile_account, staleness
from app.services.momentum.engines import (
    backtest_for_engine, deployed_or_seed, engine_to_config_dict,
)

router = APIRouter(prefix="/api/v1/paper-trading", tags=["paper-trading"])


def _q(x) -> Decimal:
    return Decimal(str(float(x)))


def _fin(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _engine(db: Session, engine_id: int) -> Engine:
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    return eng


def _resolve_account(db: Session, engine_id: int | None = None) -> PaperAccount:
    """The account to read: one by engine_id, else the deployed engine's, else the first.
    404 if none exist (caller should POST /enable first)."""
    q = db.query(PaperAccount)
    if engine_id is not None:
        acct = q.filter(PaperAccount.engine_id == engine_id).first()
        if acct is None:
            raise HTTPException(404, f"no paper account for engine {engine_id}; POST /enable")
        return acct
    eng = deployed_or_seed(db)
    acct = q.filter(PaperAccount.engine_id == eng.id).first() if hasattr(eng, "id") else None
    if acct is None:
        acct = q.first()
    if acct is None:
        raise HTTPException(404, "no paper accounts; POST /paper-trading/enable first")
    return acct


def _account_out(db: Session, acct: PaperAccount) -> PaperAccountOut:
    snap = last_snapshot(db, acct)
    eng = db.get(Engine, acct.engine_id)
    return PaperAccountOut(
        id=acct.id, engine_id=acct.engine_id, engine_name=eng.name if eng else f"engine {acct.engine_id}",
        is_live=bool(acct.is_live), starting_cash=float(acct.starting_cash), cash=float(acct.cash),
        go_live_at=acct.go_live_at.isoformat() if acct.go_live_at else None,
        as_of=snap.date.isoformat() if snap else None,
        equity=float(snap.equity) if snap else None,
        open_positions=int(snap.open_positions) if snap else None,
    )


# ── /enable: create + bridge a live account ──────────────────────────────────
def _enable(db: Session, eng: Engine, starting_cash) -> PaperAccount:
    """Create a live account bridged from the engine's backtest: seed historical equity
    snapshots (is_live=False) for dates < latest, carry the curve endpoint as live
    capital, then book `latest` with the real cycle so the account is consistent from
    creation. The CALLER commits."""
    closes = load_closes(db)
    base = float(starting_cash) if starting_cash else float(eng.starting_cash)
    bridge_eq = base
    bridge_rows = []                       # (date, equity, gross, n_pos)
    if len(closes):
        res = backtest_for_engine(closes, eng)
        daily = res["daily_returns"]
        weights = res.get("weights")
        if len(daily):
            eq = (1.0 + daily.fillna(0.0)).cumprod() * base
            bridge_eq = float(eq.iloc[-1])
            latest = closes.index[-1].date()
            gross = (weights.sum(axis=1).reindex(eq.index).fillna(0.0)
                     if weights is not None else pd.Series(0.0, index=eq.index))
            npos = ((weights.reindex(eq.index).fillna(0.0) > 0).sum(axis=1)
                    if weights is not None else pd.Series(0, index=eq.index))
            for d, e, g, n in zip(eq.index, eq.values, gross.values, npos.values):
                dte = d.date() if hasattr(d, "date") else d
                if dte >= latest:
                    continue              # leave `latest` for the first LIVE cycle
                bridge_rows.append((dte, float(e), float(g), int(n)))

    acct = PaperAccount(
        engine_id=eng.id, starting_cash=_q(bridge_eq), cash=_q(bridge_eq),
        is_live=True,
        go_live_at=(closes.index[-1].date() if len(closes) else None),
        config_snapshot={**engine_to_config_dict(eng), "bridge_equity": bridge_eq,
                         "starting_cash_nominal": float(eng.starting_cash)},
    )
    db.add(acct)
    db.flush()                             # assign acct.id
    for dte, e, g, n in bridge_rows:
        pv = e * g
        db.add(PaperEquitySnapshot(
            account_id=acct.id, date=dte, cash=_q(e - pv), positions_value=_q(pv),
            equity=_q(e), gross_exposure=_q(g) if g > 0 else None,
            realized_pnl_cumulative=_q(0.0), open_positions=n, is_live=False))
    run_cycle(db, acct)                    # book `latest` live (consistent from creation)
    return acct


# ── endpoints ────────────────────────────────────────────────────────────────
@router.get("/accounts", response_model=list[PaperAccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return [_account_out(db, a) for a in db.query(PaperAccount).order_by(PaperAccount.id).all()]


@router.post("/enable", response_model=PaperAccountOut, status_code=201)
def enable_engine(req: EnableRequest, db: Session = Depends(get_db)):
    """Paper-trade an engine: create + bridge a live account (idempotent re-enable if
    one already exists for this engine)."""
    eng = _engine(db, req.engine_id)
    existing = db.query(PaperAccount).filter(PaperAccount.engine_id == req.engine_id).first()
    if existing is not None:
        existing.is_live = True            # re-enable; don't re-bridge
        db.commit()
        db.refresh(existing)
        return _account_out(db, existing)
    acct = _enable(db, eng, req.starting_cash)
    db.commit()
    db.refresh(acct)
    return _account_out(db, acct)


@router.post("/disable", response_model=PaperAccountOut)
def disable_engine(engine_id: int = Query(...), db: Session = Depends(get_db)):
    """Pause a live account (is_live=False); the beat/catch-up skip paused accounts.
    Positions are frozen (not flattened) so it can be re-enabled."""
    acct = db.query(PaperAccount).filter(PaperAccount.engine_id == engine_id).first()
    if acct is None:
        raise HTTPException(404, f"no paper account for engine {engine_id}")
    acct.is_live = False
    db.commit()
    db.refresh(acct)
    return _account_out(db, acct)


@router.get("/positions", response_model=list[PaperPositionOut])
def list_positions(engine_id: int | None = None, db: Session = Depends(get_db)):
    acct = _resolve_account(db, engine_id)
    meta = load_meta(db)
    closes = load_closes(db)
    close_row = closes.iloc[-1] if len(closes) else None
    snap = last_snapshot(db, acct)
    equity = float(snap.equity) if snap and snap.equity else float(acct.cash)
    rows = db.query(PaperPosition).filter_by(account_id=acct.id).all()
    out = []
    for p in rows:
        px = (float(close_row[p.stock_id])
              if close_row is not None and math.isfinite(float(close_row.get(p.stock_id, float("nan"))))
              else None)
        mv = (float(p.quantity) * px) if px is not None else None
        info = meta.get(int(p.stock_id), {})
        out.append(PaperPositionOut(
            stock_id=p.stock_id, symbol=info.get("symbol") or str(p.stock_id),
            name=info.get("name"), quantity=float(p.quantity),
            avg_cost=_fin(p.avg_cost), price=_fin(px), market_value=_fin(mv),
            weight=_fin(mv / equity) if (mv and equity) else None,
            unrealized_pnl_pct=_fin(px / float(p.avg_cost) - 1) if (px and p.avg_cost) else None,
        ))
    out.sort(key=lambda r: r.market_value or 0.0, reverse=True)
    return out


@router.get("/fills", response_model=list[PaperFillOut])
def list_fills(engine_id: int | None = None, limit: int = Query(100, ge=1, le=1000),
               db: Session = Depends(get_db)):
    acct = _resolve_account(db, engine_id)
    meta = load_meta(db)
    rows = (db.query(PaperFill).filter_by(account_id=acct.id)
            .order_by(PaperFill.cycle_id.desc(), PaperFill.id.desc()).limit(limit).all())
    return [PaperFillOut(
        id=f.id, stock_id=f.stock_id,
        symbol=meta.get(int(f.stock_id), {}).get("symbol") or str(f.stock_id),
        cycle_id=f.cycle_id.isoformat(), side=f.side, quantity=float(f.quantity),
        price=float(f.price), value=float(f.value), cost=float(f.cost), reason=f.reason,
    ) for f in rows]


@router.get("/equity", response_model=list[EquitySnapshotOut])
def list_equity(engine_id: int | None = None, limit: int = Query(2000, ge=1, le=10000),
                db: Session = Depends(get_db)):
    acct = _resolve_account(db, engine_id)
    rows = (db.query(PaperEquitySnapshot).filter_by(account_id=acct.id)
            .order_by(PaperEquitySnapshot.date.desc()).limit(limit).all())
    rows = list(reversed(rows))
    return [EquitySnapshotOut(
        date=s.date.isoformat(), cash=float(s.cash), positions_value=float(s.positions_value),
        equity=float(s.equity), gross_exposure=_fin(s.gross_exposure),
        open_positions=int(s.open_positions), is_live=bool(s.is_live),
    ) for s in rows]


@router.get("/summary", response_model=PaperSummaryOut)
def summary(engine_id: int | None = None, db: Session = Depends(get_db)):
    from app.services.backtest.metrics import summarize
    acct = _resolve_account(db, engine_id)
    eng = db.get(Engine, acct.engine_id)
    snaps = (db.query(PaperEquitySnapshot).filter_by(account_id=acct.id)
             .order_by(PaperEquitySnapshot.date).all())
    last = snaps[-1] if snaps else None
    starting = float(acct.starting_cash)
    equity = float(last.equity) if last else float(acct.cash)
    total_return = equity / starting - 1 if starting else 0.0
    sharpe = max_dd = None
    live_return = None
    if len(snaps) >= 2:
        eq = pd.Series([float(s.equity) for s in snaps])
        m = summarize(eq.pct_change().dropna())
        sharpe, max_dd = _fin(m.get("sharpe")), _fin(m.get("max_drawdown"))
        live = [s for s in snaps if s.is_live]
        if len(live) >= 2 and float(live[0].equity) > 0:
            live_return = float(live[-1].equity) / float(live[0].equity) - 1
    return PaperSummaryOut(
        engine_id=acct.engine_id, engine_name=eng.name if eng else f"engine {acct.engine_id}",
        is_live=bool(acct.is_live), starting_cash=starting, equity=equity, cash=float(acct.cash),
        open_positions=int(last.open_positions) if last else 0,
        gross_exposure=_fin(last.gross_exposure) if last else None,
        total_return=total_return, live_return=_fin(live_return), sharpe=sharpe,
        max_drawdown=max_dd, as_of=(last.date.isoformat() if last else None),
        go_live_at=(acct.go_live_at.isoformat() if acct.go_live_at else None),
        n_snapshots=len(snaps),
    )


@router.get("/health", response_model=list[LedgerHealthOut])
def health(db: Session = Depends(get_db)):
    out = []
    for acct in db.query(PaperAccount).order_by(PaperAccount.id).all():
        eng = db.get(Engine, acct.engine_id)
        s = staleness(db, acct)
        out.append(LedgerHealthOut(
            account_id=acct.id, engine_id=acct.engine_id,
            engine_name=eng.name if eng else f"engine {acct.engine_id}",
            is_live=bool(acct.is_live), status=s["status"],
            last_date=s.get("last_date"), latest_bar=s.get("latest_bar"),
            feed_age_days=s.get("feed_age_days"),
        ))
    return out


@router.get("/reconciliation", response_model=list[ReconciliationOut])
def reconciliation(db: Session = Depends(get_db)):
    out = []
    for acct in db.query(PaperAccount).order_by(PaperAccount.id).all():
        eng = db.get(Engine, acct.engine_id)
        r = reconcile_account(db, acct)
        out.append(ReconciliationOut(
            account_id=acct.id, engine_id=acct.engine_id,
            engine_name=eng.name if eng else f"engine {acct.engine_id}",
            ok=r["ok"], as_of=r.get("as_of"), cash=r["cash"],
            positions_value=r["positions_value"], expected_equity=r["expected_equity"],
            snapshot_equity=r.get("snapshot_equity"), identity_ok=r["identity_ok"],
            cash_ok=r["cash_ok"], open_positions=r["open_positions"],
        ))
    return out


@router.post("/run", response_model=dict)
def run_now(engine_id: int | None = None, sync: bool = Query(False),
            db: Session = Depends(get_db)):
    """Trigger the paper-trading cycle. Default: enqueue the Celery task (async).
    ?sync=true: run it inline in this request (ops/tests) and return per-engine results."""
    if sync:
        q = db.query(PaperAccount)
        if engine_id is not None:
            q = q.filter(PaperAccount.engine_id == engine_id)
        else:
            q = q.filter(PaperAccount.is_live.is_(True))
        results = []
        for acct in q.all():
            try:
                r = run_cycle(db, acct)
                db.commit()
                results.append({"engine_id": acct.engine_id, **r})
            except Exception as e:
                db.rollback()
                results.append({"engine_id": acct.engine_id, "status": "error", "error": str(e)})
        return {"sync": True, "engine_id": engine_id, "results": results}
    from app.tasks.ledger_tasks import run_paper_trading_cycle
    task = run_paper_trading_cycle.delay(engine_id)
    return {"sync": False, "engine_id": engine_id, "task_id": task.id, "queued": True}
