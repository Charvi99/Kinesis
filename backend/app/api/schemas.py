"""Pydantic request/response models for the /api/v1 portfolio + engines API.

Shapes match the contracts in FRONTEND_DESIGN.md §4. Floats throughout — these are
display/risk numbers, not accounting; the frontend formats with fmtPct/fmtMoney.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConfigOut(BaseModel):
    lookback: int
    top_n: int
    target_vol: float
    max_weight: float
    regime_gate: bool
    target_port_vol: float
    dd_threshold: float
    de_gross: float
    leverage_cap: float
    cost_bps: float


class BacktestRequest(BaseModel):
    lookback: int = Field(default=252, ge=10, le=504)
    top_n: int = Field(default=10, ge=1, le=100)
    target_vol: float = Field(default=0.10, gt=0, le=1.0)
    max_weight: float = Field(default=0.10, gt=0, le=1.0)
    regime_gate: bool = True
    # defense overlay
    defended: bool = True
    target_port_vol: float = Field(default=0.15, gt=0, le=1.0)
    dd_threshold: float = Field(default=0.12, gt=0, le=1.0)
    de_gross: float = Field(default=0.5, gt=0, le=1.0)
    leverage_cap: float = Field(default=1.0, gt=0, le=3.0)
    cost_bps: float = Field(default=5.0, ge=0, le=100)
    # window (optional; backtest always runs on full history for correct warmup)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class MetricSet(BaseModel):
    total_return: float
    ann_return: float
    ann_vol: float
    sharpe: float
    max_drawdown: float
    psr0: Optional[float] = None
    avg_exposure: Optional[float] = None
    avg_turnover: Optional[float] = None
    bear_sharpe: Optional[float] = None
    bull_sharpe: Optional[float] = None


class EquityPoint(BaseModel):
    date: str
    equity: float
    spy: float


class BacktestResponse(BaseModel):
    metrics: MetricSet
    equity_curve: List[EquityPoint]
    trades_count: int
    defended: bool
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class DefenseState(BaseModel):
    vol_target_factor: float   # target_port_vol / trailing realized vol (current)
    drawdown: float            # current drawdown vs equity high
    dd_threshold: float


class PortfolioState(BaseModel):
    equity: float
    starting_cash: float
    equity_curve: List[EquityPoint]
    metrics: MetricSet
    regime: str                # "bull" | "bear"
    exposure: float            # current gross exposure (last day)
    defense: DefenseState
    as_of: str                 # last date in the series


class SelectionRow(BaseModel):
    symbol: str
    name: Optional[str] = None
    momentum_score: float      # 252d return (the actual signal)
    rank: int
    weight: float
    held: bool
    changed: Optional[str] = None   # "add" | "drop" | None


class TradeRow(BaseModel):
    symbol: str
    entry_date: str
    exit_date: str
    entry: float
    exit: float
    ret: float
    reason: str                # "rank_drop" | "defense"


# ── Engines (named, persisted configs) ───────────────────────────────────────
# Range constraints mirror BacktestRequest so a saved engine is always backtestable.
class EngineBase(BaseModel):
    lookback: int = Field(default=252, ge=10, le=504)
    top_n: int = Field(default=10, ge=1, le=100)
    target_vol: float = Field(default=0.10, gt=0, le=1.0)
    max_weight: float = Field(default=0.10, gt=0, le=1.0)
    regime_gate: bool = True
    defended: bool = True
    target_port_vol: float = Field(default=0.22, gt=0, le=1.0)
    dd_threshold: float = Field(default=0.12, gt=0, le=1.0)
    de_gross: float = Field(default=0.5, gt=0, le=1.0)
    leverage_cap: float = Field(default=1.0, gt=0, le=3.0)
    cost_bps: float = Field(default=5.0, ge=0, le=100)
    starting_cash: float = Field(default=100_000.0, gt=0)


class EngineCreate(EngineBase):
    name: str = Field(min_length=1, max_length=64)
    description: Optional[str] = None


class EngineUpdate(BaseModel):
    """All-optional PATCH payload."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = None
    lookback: Optional[int] = Field(default=None, ge=10, le=504)
    top_n: Optional[int] = Field(default=None, ge=1, le=100)
    target_vol: Optional[float] = Field(default=None, gt=0, le=1.0)
    max_weight: Optional[float] = Field(default=None, gt=0, le=1.0)
    regime_gate: Optional[bool] = None
    defended: Optional[bool] = None
    target_port_vol: Optional[float] = Field(default=None, gt=0, le=1.0)
    dd_threshold: Optional[float] = Field(default=None, gt=0, le=1.0)
    de_gross: Optional[float] = Field(default=None, gt=0, le=1.0)
    leverage_cap: Optional[float] = Field(default=None, gt=0, le=3.0)
    cost_bps: Optional[float] = Field(default=None, ge=0, le=100)
    starting_cash: Optional[float] = Field(default=None, gt=0)


class EngineOut(EngineBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    is_deployed: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metrics: Optional[dict] = None


# ── Sweep (one knob across a range) ───────────────────────────────────────────
class SweepRequest(BaseModel):
    engine_id: Optional[int] = None     # base config; None → deployed engine
    knob: str                            # one of SWEEPABLE_KNOBS (validated in the route)
    values: List[float] = Field(min_length=1, max_length=16)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class SweepPoint(BaseModel):
    value: float
    metrics: MetricSet
    equity_curve: List[EquityPoint] = []   # for the overlay (compare paths visually)


class SweepResponse(BaseModel):
    knob: str
    base: ConfigOut
    points: List[SweepPoint]


# ── Compare (two configs side by side) ────────────────────────────────────────
class CompareRequest(BaseModel):
    a_engine_id: Optional[int] = None
    a: Optional[BacktestRequest] = None          # inline config (if no engine_id)
    b_engine_id: Optional[int] = None
    b: Optional[BacktestRequest] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CompareSide(BaseModel):
    name: str
    metrics: MetricSet
    equity_curve: List[EquityPoint]


class CompareDelta(BaseModel):
    sharpe: float
    max_drawdown: float
    total_return: float


class CompareResponse(BaseModel):
    a: CompareSide
    b: CompareSide
    delta: CompareDelta
