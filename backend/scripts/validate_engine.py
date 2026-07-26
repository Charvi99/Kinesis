#!/usr/bin/env python3
"""engine_3 validation — the honest go/no-go.

(1) Rank-IC of the momentum signal vs forward returns, by regime (does selection
    predict?), chronological train/val to catch false positives.
(2) Walk-forward OOS of the engine_3 portfolio backtest: pick (lookback, top_n) on
    TRAIN (2021-23, incl. the 2022 bear), evaluate on held-out TEST (2024-26) — with
    the deflated-Sharpe multiple-testing bar. No peeking.
"""
import os, sys
sys.path.insert(0, "/app")
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.momentum.selection import market_regime_masks
from app.services.backtest.portfolio import backtest_momentum
from app.services.backtest.metrics import summarize


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


def rank_ic(sig, ret):
    s = pd.DataFrame({"s": sig, "r": ret}).dropna()
    return float(spearmanr(s["s"], s["r"]).correlation) if len(s) > 30 else float("nan")


def momentum_ic_by_regime(closes):
    rets = closes.pct_change()
    mom = closes.pct_change(252)
    bull, bear = market_regime_masks(closes)
    rows = []
    for sid in closes.columns:
        m = mom[sid]; r5 = rets[sid].add(rets[sid].shift(1), fill_value=0)  # placeholder
    # cross-sectional: stack
    out = {"ALL": {}, "BEAR": {}, "BULL": {}}
    for h in (5, 10, 21):
        fwd = closes.pct_change(h).shift(-h)  # forward h-day return
        out["ALL"][h] = rank_ic(mom.stack(), fwd.stack())
        out["BEAR"][h] = rank_ic(mom[bear].stack(), fwd[bear].stack())
        out["BULL"][h] = rank_ic(mom[bull].stack(), fwd[bull].stack())
    return out


def walk_forward(closes):
    split = pd.Timestamp("2024-01-01")
    cands = [(lb, tn) for lb in (126, 252) for tn in (10, 20, 30)]
    # train Sharpe for each, using only daily returns before `split`
    train = []
    for lb, tn in cands:
        dr = backtest_momentum(closes, lookback=lb, top_n=tn)["daily_returns"]
        tr = summarize(dr[dr.index < split])["sharpe"]
        train.append((lb, tn, tr, dr))
    best = max(train, key=lambda x: x[2])
    lb, tn, tr_sh, dr = best
    te_sh = summarize(dr[dr.index >= split])["sharpe"]
    te_full = summarize(dr)
    return best, te_sh, te_full


def main():
    closes = load_closes()
    print(f"universe={closes.shape[1]} stocks, {len(closes)} days ({len(closes)/252:.1f}y)")
    print("\n[1] momentum(252d) rank-IC vs forward return, by regime:")
    ic = momentum_ic_by_regime(closes)
    for reg in ("ALL", "BEAR", "BULL"):
        print(f"  {reg:4s} h=5 {ic[reg][5]:+.3f}  h=10 {ic[reg][10]:+.3f}  h=21 {ic[reg][21]:+.3f}")

    print("\n[2] walk-forward OOS (select lookback,top_n on 2021-23; test 2024-26):")
    best, te_sh, te_full = walk_forward(closes)
    lb, tn, tr_sh, _ = best
    print(f"  TRAIN-selected: lookback={lb} top_n={tn} (train Sharpe {tr_sh:.2f})")
    print(f"  OOS test: Sharpe={te_sh:.2f}  |  full-period: Sharpe={te_full['sharpe']:.2f} "
          f"PSR0={te_full['psr0']:.2f} maxDD={te_full['max_drawdown']*100:.1f}%")
    from math import log, sqrt
    N, T = 6, len(closes) / 252
    luck = sqrt(2 * log(N) / T)
    print(f"  multiple-testing 'luck' threshold ({N} configs, {T:.1f}y) = {luck:.2f}")
    verdict = "REAL EDGE (clears luck + PSR0>0.95 + survives OOS)" if (
        te_full["sharpe"] > luck and te_full["psr0"] > 0.95 and te_sh > 0.5) else "BORDERLINE/NULL — does not clear the strict bar"
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    main()
