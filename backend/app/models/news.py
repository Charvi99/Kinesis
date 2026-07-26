"""News + sentiment (Polygon insights). Kept — sentiment is an engine_3 feature."""
from sqlalchemy import (ARRAY, Column, DECIMAL, ForeignKey, Integer, String, Text,
                        TIMESTAMP)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)

    article_id = Column(String(255), unique=True, nullable=False, index=True)
    publisher = Column(String(255), nullable=True)
    title = Column(Text, nullable=False)
    author = Column(String(255), nullable=True)
    published_utc = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    article_url = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    keywords = Column(ARRAY(String), nullable=True)

    sentiment = Column(String(20), nullable=True)        # positive/negative/neutral
    sentiment_score = Column(DECIMAL(5, 4), nullable=True)  # -1.0 .. 1.0
    sentiment_reasoning = Column(Text, nullable=True)
    ticker = Column(String(10), nullable=True, index=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    stock = relationship("Stock", back_populates="news")
