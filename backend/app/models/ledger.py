"""Paper-trading ledger models — a real, position-tracking account per live engine.

Unlike the backtester (a weight matrix), this is true accounting: fractional positions,
fills at the close, cash, and daily equity snapshots. The daily cycle (services/ledger/
cycle.py) rebalances positions toward the engine's target book, so live accounting
matches the backtester (fractional shares ⇒ no rounding drift; equity_post == equity_pre
− cost). One account per live-enabled engine; created on /enable (opt-in), not auto-seeded.
"""
from sqlalchemy import (Boolean, Column, Date, DECIMAL, ForeignKey,
                        Integer, JSON, String, TIMESTAMP, UniqueConstraint)
from sqlalchemy.sql import func

from app.db.database import Base


class PaperAccount(Base):
    """One virtual account per live-enabled engine."""
    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, index=True)
    engine_id = Column(Integer, ForeignKey("engines.id", ondelete="CASCADE"),
                       nullable=False, unique=True, index=True)
    starting_cash = Column(DECIMAL(16, 2), nullable=False)
    cash = Column(DECIMAL(16, 2), nullable=False)
    is_live = Column(Boolean, nullable=False, default=False, server_default="false")
    go_live_at = Column(Date, nullable=True)           # OOS boundary (snapshots before = backtest bridge)
    config_snapshot = Column(JSON, nullable=True)      # engine knobs at go-live (attribution)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class PaperPosition(Base):
    """Current open position in an account (fractional shares)."""
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(DECIMAL(18, 6), nullable=False, default=0)
    avg_cost = Column(DECIMAL(14, 4), nullable=True)
    opened_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "stock_id", name="uq_paper_position_account_stock"),
    )


class PaperFill(Base):
    """One rebalance fill: the net delta for one stock on one cycle (idempotent per
    account+stock+cycle). BUY = added/trimmed up, SELL = trimmed down/flattened."""
    __tablename__ = "paper_fills"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id = Column(Date, nullable=False, index=True)         # the trading day (= snapshot date)
    side = Column(String(4), nullable=False)                    # 'buy' | 'sell'
    quantity = Column(DECIMAL(18, 6), nullable=False)           # |delta|, always > 0
    price = Column(DECIMAL(14, 4), nullable=False)              # fill price (the cycle's close)
    value = Column(DECIMAL(16, 2), nullable=False)              # |quantity * price|
    cost = Column(DECIMAL(16, 2), nullable=False, default=0)    # turnover * cost_bps/1e4
    reason = Column(String(16), nullable=False, default="rebalance")  # rebalance | flatten
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "stock_id", "cycle_id", name="uq_paper_fill_account_stock_cycle"),
    )


class PaperEquitySnapshot(Base):
    """One equity row per account per trading day. Idempotent per account+date. The
    equity curve the Dashboard plots; the source of rv/drawdown for the live defense."""
    __tablename__ = "paper_equity_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    cash = Column(DECIMAL(16, 2), nullable=False)
    positions_value = Column(DECIMAL(16, 2), nullable=False)
    equity = Column(DECIMAL(16, 2), nullable=False)             # cash + positions_value
    gross_exposure = Column(DECIMAL(8, 4), nullable=True)       # positions_value / equity
    realized_pnl_cumulative = Column(DECIMAL(16, 2), nullable=False, default=0)
    open_positions = Column(Integer, nullable=False, default=0)
    is_live = Column(Boolean, nullable=False, default=False, server_default="false")  # False = backtest bridge
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_paper_equity_account_date"),
    )
