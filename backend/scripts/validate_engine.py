#!/usr/bin/env python3
"""engine_3 A/B: v0 (weights-only, rank-drop exit) vs stopped (+ ATR trailing stop).

Same universe, same selection (rank top-N -> vol-scaled -> regime-gated). The stopped
version overlays trailing-stop exits (cut losers / lock winners). The thesis predicts
the stopped engine has a better PAYOFF RATIO (avg_win/avg_loss) and lower maxDD, at
maybe slightly lower return. Env: LOOKBACK TOP_N K."""
import os, sys
sys.path.insert(0, "/app")
import pandas as pd
from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.backtest.portfolio import backtest_momentum, backtest_momentum_stopped


def load_closes():
    db = SessionLocal()
    try:
        rows = db.execute(text("""SELECT p.stock_id, p.timestamp, p.close FROM stock_prices p
                                  JOIN stocks s ON s.id=p.stock_id WHERE p.timeframe='1d'
                                  ORDER BY p.timestamp""")).all()
    finally:
        db.close()
    df = pd.DataFrame(rows, columns=["sid", "ts", "close"])
    df["close"] = df["close"].astype(float)
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert(None)
    return df.pivot(index="ts", columns="sid", values="close").sort_index().ffill()


def main():
    closes = load_closes()
    lb = int(os.getenv("LOOKBACK", "252")); tn = int(os.getenv("TOP_N", "10")); k = float(os.getenv("K", "3.0"))
    print(f"universe={closes.shape[1]} stocks, {len(closes)} days ({len(closes)/252:.1f}y)  "
          f"lookback={lb} top_n={tn} k={k}\n")
    print(f"{'engine':>16} | {'tot%':>6} | {'Shp':>5} | {'PSR0':>5} | {'maxDD%':>6} | "
          f"{'bearSh':>6} | {'N':>4} | {'winR':>5} | {'avgW':>6} | {'avgL':>6} | {'payoff':>6}")
    print("-" * 95)
    v0 = backtest_momentum(closes, lookback=lb, top_n=tn)["metrics"]
    st = backtest_momentum_stopped(closes, lookback=lb, top_n=tn, k=k)["metrics"]
    for name, m in [("v0 (rank-drop)", v0), ("stopped (+ATR)", st)]:
        print(f"{name:>16} | {m['total_return']*100:>6.1f} | {m['sharpe']:>5.2f} | "
              f"{m['psr0']:>5.2f} | {m['max_drawdown']*100:>6.2f} | {m.get('bear_sharpe',float('nan')):>6.2f} | "
              f"{m.get('n',0):>4} | {m.get('win_rate',float('nan')):>5.2f} | "
              f"{m.get('avg_win',0)*100:>5.2f}% | {m.get('avg_loss',0)*100:>5.2f}% | {m.get('payoff',float('nan')):>5.2f}")
    print("-" * 95)
    d_sharpe = st["sharpe"] - v0["sharpe"]; d_dd = st["max_drawdown"] - v0["max_drawdown"]
    print(f"delta: Sharpe {d_sharpe:+.2f}  maxDD {d_dd*100:+.2f}pp  payoff {st.get('payoff',0):.2f}")
    print("READ: stopped should show higher payoff + less-bad maxDD (cut losers). "
          "If Sharpe also holds/improves, the risk layer works.")


if __name__ == "__main__":
    main()
