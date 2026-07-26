#!/usr/bin/env python3
"""Run the engine_3 portfolio backtest on the DB universe. Prints metrics + a
regime split. Env: LOOKBACK=252 TOP_N=30 TARGET_VOL=0.10 MAX_STOCKS=0 COST_BPS=5."""
import os, sys
sys.path.insert(0, "/app")
import pandas as pd
from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.backtest.portfolio import backtest_momentum

def main():
    max_stocks = int(os.getenv("MAX_STOCKS", "0"))
    db = SessionLocal()
    try:
        q = text("""SELECT p.stock_id, p.timestamp, p.close FROM stock_prices p
                   JOIN stocks s ON s.id=p.stock_id WHERE p.timeframe='1d' AND s.is_tracked = true ORDER BY p.timestamp""")
        rows = db.execute(q).all()
    finally:
        db.close()
    df = pd.DataFrame(rows, columns=["stock_id", "ts", "close"])
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert(None)
    df["close"] = df["close"].astype(float)
    closes = df.pivot(index="ts", columns="stock_id", values="close").sort_index().ffill()
    if max_stocks:
        closes = closes.iloc[:, :max_stocks]
    print(f"universe={closes.shape[1]} stocks, {len(closes)} days ({len(closes)/252:.1f}y)")
    res = backtest_momentum(
        closes,
        lookback=int(os.getenv("LOOKBACK", "252")),
        top_n=int(os.getenv("TOP_N", "30")),
        target_vol=float(os.getenv("TARGET_VOL", "0.10")),
        cost_bps=float(os.getenv("COST_BPS", "5")),
    )
    m = res["metrics"]
    print(f"total={m['total_return']*100:.1f}%  annRet={m['ann_return']*100:.2f}%  "
          f"vol={m['ann_vol']*100:.2f}%  Sharpe={m['sharpe']:.2f}  PSR0={m['psr0']:.2f}  "
          f"maxDD={m['max_drawdown']*100:.2f}%")
    print(f"bearSharpe={m['bear_sharpe']:.2f}  bullSharpe={m['bull_sharpe']:.2f}  "
          f"exposure={m['avg_exposure']:.2%}  turnover={m['avg_turnover']:.3f}")

if __name__ == "__main__":
    main()
