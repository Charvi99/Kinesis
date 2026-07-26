"""engine_3 target-portfolio selection — the ONE place the momentum strategy lives.

Both the backtester and the live ledger call these, so a backtest run reproduces what
the paper-trading ledger actually does. Rank the universe by N-day momentum -> hold
the TOP-N -> vol-scaled (equal risk per name) -> regime-gated (longs only when the
market >= its 200d MA). Pure function of the close matrix (causal)."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def market_regime_masks(closes: pd.DataFrame, ma: int = 200):
    """Equal-weight market index vs its `ma`-day MA -> (bull_mask, bear_mask) per day.
    Warmup (MA not valid) is bull-default (selection is flat there anyway)."""
    mkt = (1 + closes.pct_change().mean(axis=1)).cumprod()
    mkt_ma = mkt.rolling(ma, min_periods=ma).mean()
    valid = mkt_ma.notna()
    bull = (mkt >= mkt_ma).fillna(True)
    bear = valid & (mkt < mkt_ma)
    return bull, bear


def compute_weights(
    closes: pd.DataFrame,
    lookback: int = 252,
    top_n: int = 30,
    target_vol: float = 0.10,
    max_weight: float = 0.10,
    regime_gate: bool = True,
) -> pd.DataFrame:
    """Daily target weights (date x stock). Decision at T close; the CALLER shifts
    by 1 to earn T+1 returns (no look-ahead). Vol-scaled, gross capped at 100%."""
    rets = closes.pct_change()
    vol = rets.rolling(63, min_periods=21).std() * np.sqrt(252)
    mom = closes.pct_change(lookback)
    raw = (target_vol / vol).clip(upper=max_weight).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    rank = mom.rank(axis=1, method="first", ascending=False)
    long_sig = (rank <= top_n).astype(float)
    w = long_sig * raw

    gross = w.sum(axis=1)
    w = w.mul((1.0 / gross).where(gross > 1.0, 1.0), axis=0)  # cap gross <= 100%

    if regime_gate:
        bull, _ = market_regime_masks(closes)
        w = w.mul(bull.astype(float), axis=0)
    return w.fillna(0.0)


def target_portfolio_asof(closes: pd.DataFrame, as_of, **kw) -> Dict:
    """Target weights as-of `as_of` close — {stock_id: weight}, causal (uses only
    rows <= as_of). What the live ledger calls each cycle to rebalance."""
    sub = closes.loc[:as_of]
    if len(sub) < 60:
        return {}
    w = compute_weights(sub, **kw)
    s = w.iloc[-1]
    return {int(k): float(v) for k, v in s.items() if v > 0}
