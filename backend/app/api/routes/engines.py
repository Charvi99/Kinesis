"""Engines API (/api/v1/engines) — CRUD over named, persisted engine_3 configs.

Exactly one engine is `is_deployed` at a time; that row is the source of truth the
portfolio routes (/config, /portfolio/state, /selection, /trades) read. Deploying or
editing busts the portfolio state cache so the Dashboard follows immediately.

Range constraints live on the Pydantic schemas (mirror BacktestRequest), so a saved
engine is always backtestable.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import EngineCreate, EngineOut, EngineUpdate
from app.models.engine import Engine
from app.services.momentum.engines import seed_default_engine

router = APIRouter(prefix="/api/v1/engines", tags=["engines"])


def _out(eng: Engine) -> EngineOut:
    return EngineOut.model_validate(eng)


def _invalidate_state_cache() -> None:
    """Bust the portfolio state cache after a config change (lazy import: portfolio
    routes don't import this module, so no cycle)."""
    from app.api.routes.portfolio import invalidate_state_cache
    invalidate_state_cache()


@router.get("", response_model=list[EngineOut])
def list_engines(db: Session = Depends(get_db)):
    """All engines, deployed first. Auto-seeds `prod` if the table is empty so the UI
    always shows the baseline config."""
    if db.query(Engine).count() == 0:
        seed_default_engine(db)
    rows = db.query(Engine).order_by(Engine.is_deployed.desc(), Engine.id).all()
    return [_out(e) for e in rows]


@router.get("/{engine_id}", response_model=EngineOut)
def get_engine(engine_id: int, db: Session = Depends(get_db)):
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"engine {engine_id} not found")
    return _out(eng)


@router.post("", response_model=EngineOut, status_code=201)
def create_engine(req: EngineCreate, db: Session = Depends(get_db)):
    if db.query(Engine).filter(Engine.name == req.name).first():
        raise HTTPException(409, f"engine {req.name!r} already exists")
    eng = Engine(**req.model_dump(), is_deployed=False)
    db.add(eng)
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
    # App-level invariant: exactly one deployed engine.
    db.query(Engine).filter(Engine.is_deployed.is_(True)).update({Engine.is_deployed: False})
    eng.is_deployed = True
    db.commit()
    db.refresh(eng)
    _invalidate_state_cache()
    return _out(eng)
