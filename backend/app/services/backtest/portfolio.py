"""Portfolio backtester for engine_3 (momentum selection).

This is the RIGHT model for a momentum-selection strategy: each rebalance, RANK the
universe by momentum, hold the TOP-N equal-vol-weighted, regime-gated (longs only
when the market >= its 200d MA), vol-targeted, with transaction costs. Returns a
daily portfolio return series + metrics. Decision at T close, earned at T+1
(weight.shift(1)) -> no look-ahead.

(StockAnalyzer's per-stock `replay_engine` doesn't fit a cross-sectional selection
strategy — it has no notion of "rank the universe, hold the leaders".)
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from app.services.backtest.metrics import psr0, regime_sharpe, summarize


def _market_regime_mask(closes: pd.DataFrame, ma: int = 200) -> pd.DataFrame:
    """Per-day bull/bear masks from an equal-weight market index vs its `ma`-day MA.
    Warmup (MA not yet valid) is treated as bull-default (momentum longs are flat
    there anyway since mom252 is NaN)."""
    mkt = (1 + closes.pct_change().mean(axis=1)).cumprod()
    mkt_ma = mkt.rolling(ma, min_periods=ma).mean()
    valid = mkt_ma.notna()
    bull = (mkt >= mkt_ma).fillna(True)          # warmup -> bull (flat, no mom252)
    bear = valid & (mkt < mkt_ma)                # real bear only where MA valid
    return bull, bear


def backtest_momentum(
    closes: pd.DataFrame,
    lookback: int = 252,
    top_n: int = 30,
    target_vol: float = 0.10,
    max_weight: float = 0.10,
    regime_gate: bool = True,
    cost_bps: float = 5.0,
) -> Dict:
    """Run the momentum-selection portfolio backtest over a wide close matrix.

    Args:
        closes: DataFrame, index=date, columns=stock_id, values=close (ffilled).
        lookback: momentum lookback in trading days (252 ~= 12mo).
        top_n: number of top-momentum names to hold each rebalance.
        target_vol: annualized vol target per name (size = target_vol/realized_vol).
        max_weight: per-name cap after vol scaling.
        regime_gate: if True, only hold longs when market >= 200d MA (else flat).
        cost_bps: round-trip cost per unit turnover.
    """
    rets = closes.pct_change()
    vol = rets.rolling(63, min_periods=21).std() * np.sqrt(252)
    mom = closes.pct_change(lookback)
    raw_scale = (target_vol / vol).clip(upper=max_weight).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Daily cross-sectional rank: 1 = highest momentum. Long the top_n.
    rank = mom.rank(axis=1, method="first", ascending=False)
    long_sig = (rank <= top_n).astype(float)

    weight = long_sig * raw_scale
    gross = weight.sum(axis=1)
    weight = weight.mul((1.0 / gross).where(gross > 1.0, 1.0), axis=0)  # cap gross <= 100%

    if regime_gate:
        bull, _ = _market_regime_mask(closes)
        weight = weight.mul(bull.astype(float), axis=0)  # flat on bear days

    w_lag = weight.shift(1).fillna(0.0)
    port_ret = (w_lag * rets).sum(axis=1)
    turnover = weight.diff().abs().sum(axis=1).fillna(0.0)
    port_ret = port_ret - turnover * (cost_bps / 1e4)

    _, bear = _market_regime_mask(closes)
    bull = ~bear
    reg = regime_sharpe(port_ret, bear, bull)
    m = summarize(port_ret)
    m.update({
        "regime_gate": regime_gate, "lookback": lookback, "top_n": top_n,
        "avg_exposure": float(w_lag.sum(axis=1).mean()), "avg_turnover": float(turnover.mean()),
        **reg,
    })
    return {"metrics": m, "daily_returns": port_ret, "weights": w_lag}
