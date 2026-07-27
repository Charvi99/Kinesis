"""Engine — a named, persisted engine_3 config.

The source of truth for the strategy knobs is now a DB row (exactly one Engine is
`is_deployed`); the backtester itself is unchanged — it still takes plain kwargs.
See docs/FRONTEND_DESIGN.md and the engines service (momentum/engines.py) for the
Engine <-> kwargs seam.
"""
from sqlalchemy import (Boolean, Column, Float, Integer, String, TIMESTAMP, Text)
from sqlalchemy.sql import func

from app.db.database import Base


class Engine(Base):
    __tablename__ = "engines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # ── selection (momentum/selection.py::compute_weights) ──
    lookback = Column(Integer, nullable=False, default=252)
    top_n = Column(Integer, nullable=False, default=10)
    target_vol = Column(Float, nullable=False, default=0.10)
    max_weight = Column(Float, nullable=False, default=0.10)
    regime_gate = Column(Boolean, nullable=False, default=True)

    # ── bear defense (backtest/defend.py::backtest_momentum_defended) ──
    defended = Column(Boolean, nullable=False, default=True)
    target_port_vol = Column(Float, nullable=False, default=0.22)
    dd_threshold = Column(Float, nullable=False, default=0.12)
    de_gross = Column(Float, nullable=False, default=0.50)
    leverage_cap = Column(Float, nullable=False, default=1.0)

    # ── cost + capital ──
    cost_bps = Column(Float, nullable=False, default=5.0)
    starting_cash = Column(Float, nullable=False, default=100_000.0)

    # ── bookkeeping ──
    is_deployed = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
