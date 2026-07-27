"""Engines API (/api/v1/engines) — CRUD over named, persisted engine_3 configs.

Exactly one engine is `is_deployed` at a time; that row is the source of truth the
portfolio routes (/config, /portfolio/state, /selection, /trades) read. Deploying or
editing busts the portfolio state cache so the Dashboard follows immediately.

Each engine carries a cached `metrics` JSON (Sharpe/DD/etc.) computed on create/update
and lazily on first read, so the Engines grid can show risk numbers without a live
backtest per list call. POST /{id}/refresh recomputes (e.g. after a price re-backfill).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, load_closes
from app.api.schemas import EngineCreate, EngineOut, EngineUpdate
from app.models.engine import Engine
from app.services.momentum.engines import backtest_for_engine, metrics_for_engine, seed_default_engine

router = APIRouter(prefix="/api/v1/engines", tags=["engines"])

# knob keys that change the backtest (=> metrics must be recomputed on update)
_BACKTEST_KEYS = {"lookback", "top_n", "target_vol", "max_weight", "regime_gate",
                  "defended", "target_port_vol", "dd_threshold", "de_gross",
                  "leverage_cap", "cost_bps", "starting_cash"}


def _out(eng: Engine) -> EngineOut:
    return EngineOut.model_validate(eng)


def _invalidate_state_cache() -> None:
    from app.api.routes.portfolio import invalidate_state_cache
    invalidate_state_cache()


def _ensure_metrics(db: Session, eng: Engine) -> Engine:
    """Lazily compute + cache metrics on first read (NULL after migration)."""
    if eng.metrics is None:
        eng.metrics = metrics_for_engine(load_closes(db), eng)
        db.commit()
        db.refresh(eng)
    return eng


@router.get("", response_model=list[EngineOut])
def list_engines(db: Session = Depends(get_db)):
    """All engines, deployed first. Auto-seeds `prod` if the table is empty."""
    if db.query(Engine).count() == 0:
        seed_default_engine(db)
    rows = db.query(Engine).order_by(Engine.is_deployed.desc(), Engine.id).all()
    return [_out(_ensure_metrics(db, e)) for e in rows]


@router.get("/curves", response_model=list)
def engine_curves(db: Session = Depends(get_db)):
    """Every engine's backtested equity path (downsampled) for the Engines comparison
    overlay. Runs one backtest per engine (few engines; cache later if this grows)."""
    import numpy as np
    import pandas as pd
    if db.query(Engine).count() == 0:
        seed_default_engine(db)
    engines = db.query(Engine).order_by(Engine.is_deployed.desc(), Engine.id).all()
    closes = load_closes(db)
    out = []
    for e in engines:
        daily = backtest_for_engine(closes, e)["daily_returns"]
        eq = (1 + daily.fillna(0.0)).cumprod() * float(e.starting_cash or 100_000.0)
        if len(eq) > 200:
            step = int(np.ceil(len(eq) / 200))
            eq = pd.concat([eq.iloc[::step], eq.iloc[[-1]]]).drop_duplicates()
        out.append({
            "name": e.name, "is_deployed": e.is_deployed,
            "curve": [{"date": d.strftime("%Y-%m-%d"), "equity": round(float(v), 2)}
                      for d, v in zip(eq.index, eq)],
        })
    return out

@router.get("/{engine_id}", response_model=EngineOut)
def get_engine(engine_id: int, db: Session = Depends(get_db)):
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    return _out(_ensure_metrics(db, eng))


@router.post("", response_model=EngineOut, status_code=201)
def create_engine(req: EngineCreate, db: Session = Depends(get_db)):
    if db.query(Engine).filter(Engine.name == req.name).first():
        raise HTTPException(409, f"engine {req.name!r} already exists")
    eng = Engine(**req.model_dump(), is_deployed=False)
    db.add(eng)
    db.commit()
    db.refresh(eng)
    eng.metrics = metrics_for_engine(load_closes(db), eng)
    db.commit()
    db.refresh(eng)
    return _out(eng)


@router.patch("/{engine_id}", response_model=EngineOut)
def update_engine(engine_id: int, req: EngineUpdate, db: Session = Depends(get_db)):
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    data = req.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != eng.name:
        clash = db.query(Engine).filter(Engine.name == data["name"], Engine.id != engine_id).first()
        if clash:
            raise HTTPException(409, f"engine {data['name']!r} already exists")
    for k, v in data.items():
        setattr(eng, k, v)
    db.commit()
    db.refresh(eng)
    if data.keys() & _BACKTEST_KEYS:        # a knob changed -> recompute metrics
        eng.metrics = metrics_for_engine(load_closes(db), eng)
        db.commit()
        db.refresh(eng)
    _invalidate_state_cache()
    return _out(eng)


@router.delete("/{engine_id}", response_model=dict)
def delete_engine(engine_id: int, db: Session = Depends(get_db)):
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    if eng.is_deployed:
        raise HTTPException(409, "cannot delete the deployed engine; deploy another first")
    db.delete(eng)
    db.commit()
    return {"deleted": engine_id}


@router.post("/{engine_id}/deploy", response_model=EngineOut)
def deploy_engine(engine_id: int, db: Session = Depends(get_db)):
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    db.query(Engine).filter(Engine.is_deployed.is_(True)).update({Engine.is_deployed: False})
    eng.is_deployed = True
    db.commit()
    db.refresh(eng)
    _ensure_metrics(db, eng)
    _invalidate_state_cache()
    return _out(eng)




@router.post("/{engine_id}/refresh", response_model=EngineOut)
def refresh_engine(engine_id: int, db: Session = Depends(get_db)):
    """Recompute cached metrics (e.g. after a price re-backfill)."""
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    eng.metrics = metrics_for_engine(load_closes(db), eng)
    db.commit()
    db.refresh(eng)
    return _out(eng)
