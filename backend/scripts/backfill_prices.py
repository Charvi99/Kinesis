#!/usr/bin/env python3
"""Backfill daily OHLCV bars for every tracked stock. Upsert (idempotent) on the
(stock_id, timeframe, timestamp) unique key. Env: BACKFILL_YEARS=5 MAX_STOCKS=0(all)."""
import os, sys, time, logging
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/app")
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.db.database import SessionLocal
from app.models import Stock, StockPrice
from app.services.polygon_fetcher import PolygonFetcher

log = logging.getLogger("backfill"); logging.basicConfig(level=logging.INFO, format="%(message)s")
YEARS = int(os.getenv("BACKFILL_YEARS", "5"))
MAX = int(os.getenv("MAX_STOCKS", "0"))

def upsert(db, stock_id, bars):
    if not bars: return 0
    rows = [{"stock_id": stock_id, **b} for b in bars]
    stmt = pg_insert(StockPrice.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_stock_price_stt",
        set_={"open": stmt.excluded.open, "high": stmt.excluded.high, "low": stmt.excluded.low,
              "close": stmt.excluded.close, "volume": stmt.excluded.volume,
              "adjusted_close": stmt.excluded.adjusted_close})
    db.execute(stmt); db.commit()
    return len(rows)

def main():
    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from_date = (datetime.now(timezone.utc) - timedelta(days=365 * YEARS)).strftime("%Y-%m-%d")
    f = PolygonFetcher()
    db = SessionLocal()
    try:
        q = db.query(Stock).filter(Stock.is_tracked == True).order_by(Stock.id)  # noqa: E712
        if MAX: q = q.limit(MAX)
        stocks = q.all()
        log.info(f"backfill {len(stocks)} stocks, {from_date}..{to_date}")
        total = 0; ok = 0
        for i, s in enumerate(stocks, 1):
            try:
                bars = f.fetch_daily_bars(s.symbol, from_date, to_date)
                n = upsert(db, s.id, bars)
                total += n; ok += 1 if n else 0
                if i % 10 == 0 or i == len(stocks):
                    log.info(f"  {i}/{len(stocks)} {s.symbol}: {n} bars (cum {total})")
            except Exception as e:
                log.warning(f"  {s.symbol} failed: {e}")
            time.sleep(float(os.getenv("POLYGON_DELAY", "0.15")))
        log.info(f"DONE: {ok}/{len(stocks)} stocks, {total} bars")
    finally:
        db.close()

if __name__ == "__main__":
    main()
