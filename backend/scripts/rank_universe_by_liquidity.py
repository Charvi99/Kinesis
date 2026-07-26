#!/usr/bin/env python3
"""After backfill, keep only the TOP-N most-liquid names (by avg 30d volume) — sets
is_tracked=False on the rest so the momentum engine ignores illiquid junk. This is the
liquidity cut list_tickers can't do at fetch time. Env: KEEP_TOP=300."""
import os, sys
sys.path.insert(0, "/app")
from sqlalchemy import text
from app.db.database import SessionLocal
from app.models import Stock

KEEP_TOP = int(os.getenv("KEEP_TOP", "300"))

def main():
    db = SessionLocal()
    try:
        # avg 30-calendar-day volume per stock, from the most recent bars
        rows = db.execute(text("""
            SELECT stock_id, AVG(volume::numeric) avg_vol
            FROM stock_prices
            WHERE timeframe='1d' AND timestamp > now() - interval '45 days'
            GROUP BY stock_id
            ORDER BY avg_vol DESC
        """)).all()
        top_ids = {r[0] for r in rows[:KEEP_TOP]}
        all_tracked = {s.id for s in db.query(Stock).filter(Stock.is_tracked == True).all()}  # noqa: E712
        demoted = all_tracked - top_ids
        promoted = top_ids - all_tracked
        for sid in demoted:
            db.query(Stock).filter(Stock.id == sid).update({"is_tracked": False})
        for sid in promoted:
            db.query(Stock).filter(Stock.id == sid).update({"is_tracked": True})
        db.commit()
        n_tracked = db.query(Stock).filter(Stock.is_tracked == True).count()  # noqa: E712
        print(f"liquidity rank: {len(rows)} stocks had volume; keep top {KEEP_TOP}; "
              f"tracked now = {n_tracked} (demoted {len(demoted)}, promoted {len(promoted)})")
    finally:
        db.close()

if __name__ == "__main__":
    main()
