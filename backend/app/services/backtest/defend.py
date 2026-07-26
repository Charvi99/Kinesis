"""Portfolio-level bear defense — vol-targeting + drawdown throttle.

An overlay on the v0 target weights: each day, scale TOTAL exposure by a defense
factor derived from the strategy's OWN past returns (causal):
  - vol-target: f *= target_port_vol / trailing_realized_port_vol  (de-gross when vol spikes)
  - drawdown throttle: if equity < high*(1-dd_threshold), f *= de_gross  (hard backstop)

This is the classic trend-fund risk overlay (AQR/managed-futures), NOT per-name ATR
stops (which failed because they cut winners that pulled back). Scaling the whole book
preserves winners in the bull and cuts exposure exactly when bears bite.
"""
from typing import Dict
import numpy as np
import pandas as pd


def backtest_momentum_defended(
    closes: pd.DataFrame,
    lookback: int = 252, top_n: int = 10, target_vol: float = 0.10, max_weight: float = 0.10,
    target_port_vol: float = 0.15, dd_threshold: float = 0.12, de_gross: float = 0.5,
    leverage_cap: float = 1.0, cost_bps: float = 5.0,
) -> Dict:
    from app.services.momentum.selection import compute_weights, market_regime_masks
    from app.services.backtest.metrics import summarize

    W = compute_weights(closes, lookback, top_n, target_vol, max_weight, regime_gate=True)
    rets = closes.pct_change()
    dates = closes.index
    n = len(dates)

    w_out = pd.DataFrame(0.0, index=dates, columns=W.columns)
    daily = pd.Series(0.0, index=dates)         # strategy daily returns
    equity = 1.0; high = 1.0

    for i in range(n):
        if i < lookback or i + 1 >= n:
            continue
        date = dates[i]
        # defense factor from PAST strategy returns (causal: only data before today's decision)
        past = daily.iloc[lookback:i]
        rv = past.tail(63).std() * np.sqrt(252) if len(past) >= 21 else np.nan
        f = 1.0
        if np.isfinite(rv) and rv > 0:
            f = min(target_port_vol / rv, leverage_cap)
        if high > 0 and (equity / high - 1) < -dd_threshold:
            f *= de_gross                                      # drawdown backstop
        w = W.loc[date] * f
        w_out.loc[date] = w
        r = float((w * rets.iloc[i + 1]).sum())               # earn T -> T+1
        daily.iloc[i + 1] = r
        equity *= (1 + r)
        high = max(high, equity)

    turnover = w_out.diff().abs().sum(axis=1).fillna(0.0)
    daily = daily - turnover * (cost_bps / 1e4)
    # drop the warmup zeros for metrics
    traded = daily.iloc[lookback + 1:]
    _, bear = market_regime_masks(closes)
    m = summarize(traded)
    m.update({
        "lookback": lookback, "top_n": top_n, "target_port_vol": target_port_vol,
        "dd_threshold": dd_threshold, "avg_exposure": float(w_out.sum(axis=1).mean()),
        "avg_turnover": float(turnover.mean()),
        "bear_sharpe": summarize(traded[traded.index.isin(bear[bear].index)])["sharpe"],
        "bull_sharpe": summarize(traded[~traded.index.isin(bear[bear].index)])["sharpe"],
    })
    return {"metrics": m, "daily_returns": traded, "weights": w_out}
