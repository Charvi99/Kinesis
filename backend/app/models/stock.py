"""Kinesis stock + price models (slimmed from StockAnalyzer).

Drops the legacy analysis-tracking/pattern/ML columns — engine_3 doesn't use them.
StockPrice uses a plain integer PK + a unique constraint (no manual sequence hack).
"""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, DECIMAL,
                        ForeignKey, Integer, String, TIMESTAMP, UniqueConstraint)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    is_tracked = Column(Boolean, default=True, server_default="true")

    # Liquidity / vol context used by selection + vol-targeting.
    avg_volume_30d = Column(BigInteger, nullable=True)
    avg_price_30d = Column(DECIMAL(12, 4), nullable=True)
    volatility_30d = Column(DECIMAL(8, 4), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    prices = relationship("StockPrice", back_populates="stock", cascade="all, delete-orphan")
    news = relationship("News", back_populates="stock", cascade="all, delete-orphan")


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, default="1d", server_default="1d")
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    open = Column(DECIMAL(12, 4))
    high = Column(DECIMAL(12, 4))
    low = Column(DECIMAL(12, 4))
    close = Column(DECIMAL(12, 4))
    volume = Column(BigInteger)
    adjusted_close = Column(DECIMAL(12, 4))

    __table_args__ = (
        UniqueConstraint("stock_id", "timeframe", "timestamp", name="uq_stock_price_stt"),
        CheckConstraint(
            "timeframe IN ('1m','5m','15m','30m','1h','2h','4h','1d','1w','1mo')",
            name="check_valid_timeframe",
        ),
    )

    stock = relationship("Stock", back_populates="prices")
