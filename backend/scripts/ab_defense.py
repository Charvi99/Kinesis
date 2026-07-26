#!/usr/bin/env python3
"""A/B bear-defense: v0 vs +vol-target(+DD throttle). Goal: cut the -33% maxDD
WITHOUT killing the bull Sharpe. Env: TARGET_PORT_VOL DD_THRESHOLD DE_GROSS."""
import os, sys
sys.path.insert(0, "/app")
import pandas as pd
from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.backtest.portfolio import backtest_momentum
from app.services.backtest.defend import backtest_momentum_defended


def load_closes():
    db = SessionLocal()
    try:
        rows = db.execute(text("""SELECT p.stock_id, p.timestamp, p.close FROM stock_prices p
            JOIN stocks s ON s.id=p.stock_id WHERE p.timeframe='1d' AND s.is_tracked=true
            ORDER BY p.timestamp""")).all()
    finally:
        db.close()
    df = pd.DataFrame(rows, columns=["sid", "ts", "close"])
    df["close"] = df["close"].astype(float)
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert(None)
    return df.pivot(index="ts", columns="sid", values="close").sort_index().ffill()


def main():
    c = load_closes()
    tpv = float(os.getenv("TARGET_PORT_VOL", "0.15")); ddt = float(os.getenv("DD_THRESHOLD", "0.12"))
    dg = float(os.getenv("DE_GROSS", "0.5"))
    print(f"universe={c.shape[1]} stocks, {len(c)} days  | defense: target_port_vol={tpv} dd_thresh={ddt} de_gross={dg}\n")
    v0 = backtest_momentum(c, lookback=252, top_n=10)["metrics"]
    df = backtest_momentum_defended(c, lookback=252, top_n=10, target_port_vol=tpv,
                                    dd_threshold=ddt, de_gross=dg)["metrics"]
    print(f"{'engine':>22} | {'tot%':>7} | {'annRet%':>8} | {'annVol%':>8} | {'Shp':>5} | {'maxDD%':>7} | {'bearSh':>6} | {'exposure':>8}")
    print("-" * 88)
    for name, m in [("v0 (no defense)", v0), ("+vol-target+DD throttle", df)]:
        print(f"{name:>22} | {m['total_return']*100:>7.1f} | {m['ann_return']*100:>8.2f} | "
              f"{m['ann_vol']*100:>8.2f} | {m['sharpe']:>5.2f} | {m['max_drawdown']*100:>7.2f} | "
              f"{m.get('bear_sharpe',float('nan')):>6.2f} | {m.get('avg_exposure',0):>8.2%}")
    print("-" * 88)
    print(f"delta: Sharpe {df['sharpe']-v0['sharpe']:+.2f}  maxDD {(df['max_drawdown']-v0['max_drawdown'])*100:+.2f}pp")
    print("WIN if maxDD improves a lot AND Sharpe holds (vs v0).")


if __name__ == "__main__":
    main()
