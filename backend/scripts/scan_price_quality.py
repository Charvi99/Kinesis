#!/usr/bin/env python3
"""Scan tracked stocks' price series for corruption. Prints a report; with
--exclude, sets is_tracked=false on the flagged tickers (validate before excluding).

Flags: impossible single-day moves (>80%, the rename/placeholder mode) and flat
zones (>=10 stale closes). Real high-beta names (CVNA, APP) stay tracked."""
import sys, argparse
sys.path.insert(0, "/app")
import pandas as pd
from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.data_quality import validate_series

def load_closes(db):
    rows = db.execute(text("""SELECT p.stock_id, p.timestamp, p.close FROM stock_prices p
        JOIN stocks s ON s.id=p.stock_id WHERE p.timeframe='1d' AND s.is_tracked
        ORDER BY p.timestamp""")).all()
    df = pd.DataFrame(rows, columns=["sid", "ts", "close"])
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert(None)
    df["close"] = df["close"].astype(float)
    return df.pivot(index="ts", columns="sid", values="close").sort_index().ffill()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclude", action="store_true", help="set is_tracked=false on flagged tickers")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        meta = {r[0]: r[1] for r in db.execute(text("SELECT id, symbol FROM stocks")).all()}
        closes = load_closes(db)
        flagged = []
        for sid in closes.columns:
            f = validate_series(closes[sid])
            if not f["ok"]:
                flagged.append((meta.get(int(sid), str(sid)), f))
        print(f"scanned {len(closes.columns)} tracked tickers; {len(flagged)} flagged")
        for sym, f in sorted(flagged, key=lambda x: x[1]["max_daily_move"], reverse=True):
            print(f"  {sym:6} max_daily={f['max_daily_move']*100:7.1f}%  flat={f['longest_flat_run']:3}  {', '.join(f['reasons'])}")
        if args.exclude and flagged:
            syms = [s for s, _ in flagged]
            db.execute(text("UPDATE stocks SET is_tracked=false WHERE symbol = ANY(:s)"), {"s": syms})
            db.commit()
            print(f"\nexcluded {len(syms)}: {', '.join(syms)}")
        elif args.exclude:
            print("nothing to exclude")
    finally:
        db.close()

if __name__ == "__main__":
    main()
