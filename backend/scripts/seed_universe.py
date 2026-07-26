#!/usr/bin/env python3
"""Seed the `stocks` universe. Default = a curated ~50 very-liquid US large/mid caps
(sensible for the first momentum validation). Override with SYMBOLS=a,b,c, or
USE_POLYGON=1 to pull N active US common stocks from Polygon (MAX_STOCKS)."""
import os, sys
sys.path.insert(0, "/app")
from app.db.database import SessionLocal
from app.models import Stock

DEFAULT = """AAPL MSFT NVDA AMZN GOOGL META TSLA JPM V JNJ WMT XOM UNH MA PG HD CVX MRK
ABBV PEP KO COST AVGO BAC TMO MCD CSCO ACN ABT NFLX ADBE CRM DHR LIN ORCL WFC TXN COP
NKE VZ QCOM IBM UPS RTX LOW SPGI HON CAT GS BLK DE BMY AMGN PMCVX GILD TRV AMD INTC""".split()

def main():
    use_poly = os.getenv("USE_POLYGON") == "1"
    if use_poly:
        from app.services.polygon_fetcher import PolygonFetcher
        rows = PolygonFetcher().list_us_common_stocks(int(os.getenv("MAX_STOCKS", "200")))
    else:
        syms = os.getenv("SYMBOLS").split(",") if os.getenv("SYMBOLS") else DEFAULT
        rows = [{"symbol": s.strip().upper(), "name": None} for s in syms if s.strip()]
    db = SessionLocal()
    added = 0
    try:
        for r in rows:
            sym = r["symbol"].upper()
            if not db.query(Stock).filter(Stock.symbol == sym).first():
                db.add(Stock(symbol=sym, name=r.get("name"), is_tracked=True))
                added += 1
        db.commit()
    finally:
        db.close()
    print(f"universe seed: +{added} new ({len(rows)} requested); "
          f"{db.query(Stock).count()} total") if False else None
    print(f"universe seed: {added} added, {len(rows)} requested")

if __name__ == "__main__":
    main()
