"""Portfolio backtester for engine_3 — thin layer over momentum.selection.

Adds the T+1 shift (no look-ahead), transaction costs, and metrics on top of the
shared target weights. So a backtest reproduces the live ledger's selection exactly.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from app.services.backtest.metrics import psr0, regime_sharpe, summarize, trade_stats
from app.services.momentum.selection import compute_weights, market_regime_masks


def backtest_momentum(
    closes: pd.DataFrame,
    lookback: int = 252,
    top_n: int = 30,
    target_vol: float = 0.10,
    max_weight: float = 0.10,
    regime_gate: bool = True,
    cost_bps: float = 5.0,
) -> Dict:
    weight = compute_weights(closes, lookback, top_n, target_vol, max_weight, regime_gate)
    rets = closes.pct_change()
    w_lag = weight.shift(1).fillna(0.0)
    port_ret = (w_lag * rets).sum(axis=1)
    turnover = weight.diff().abs().sum(axis=1).fillna(0.0)
    port_ret = port_ret - turnover * (cost_bps / 1e4)

    _, bear = market_regime_masks(closes)
    bull = ~bear
    m = summarize(port_ret)
    m.update({
        "regime_gate": regime_gate, "lookback": lookback, "top_n": top_n,
        "avg_exposure": float(w_lag.sum(axis=1).mean()), "avg_turnover": float(turnover.mean()),
        **regime_sharpe(port_ret, bear, bull),
    })
    return {"metrics": m, "daily_returns": port_ret, "weights": w_lag}


def backtest_momentum_stopped(
    closes: pd.DataFrame,
    lookback: int = 252, top_n: int = 10, k: float = 3.0,
    target_vol: float = 0.10, max_weight: float = 0.10, cost_bps: float = 5.0,
) -> Dict:
    """engine_3 with the ATR trailing-stop overlay. Drives MomentumEngine bar-by-bar
    over the v0 target weights; returns metrics (incl. trade stats) + the engine."""
    from app.services.momentum.engine import MomentumEngine
    from app.services.momentum.selection import compute_weights, market_regime_masks

    target_w = compute_weights(closes, lookback, top_n, target_vol, max_weight, regime_gate=True)
    eng = MomentumEngine(target_w, closes, k=k)
    rows = {}
    for i, date in enumerate(closes.index):
        if i < lookback:
            continue
        rows[date] = eng.step(date)
    weights = pd.DataFrame.from_dict(rows, orient="index").reindex(closes.index).fillna(0.0)

    rets = closes.pct_change()
    w_lag = weights.shift(1).fillna(0.0)
    port_ret = (w_lag * rets).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    port_ret = port_ret - turnover * (cost_bps / 1e4)

    _, bear = market_regime_masks(closes)
    m = summarize(port_ret)
    m.update({
        "lookback": lookback, "top_n": top_n, "k": k,
        "avg_exposure": float(w_lag.sum(axis=1).mean()), "avg_turnover": float(turnover.mean()),
        "bear_sharpe": summarize(port_ret[bear])["sharpe"] if bear.sum() else float("nan"),
        "bull_sharpe": summarize(port_ret[~bear])["sharpe"] if (~bear).sum() else float("nan"),
        **trade_stats(eng.trades),
    })
    return {"metrics": m, "daily_returns": port_ret, "trades": eng.trades}
