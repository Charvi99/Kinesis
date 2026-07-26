"""Portfolio metrics + probabilistic Sharpe (Bailey & Lopez de Prado).

Pure: operates on a daily return Series (+ optional SPY benchmark). Used by the
portfolio backtester and the validation harness."""
from math import sqrt
from typing import Dict, Optional

import numpy as np
import pandas as pd


def psr0(sharpe: float, ret: pd.Series) -> float:
    """P(true Sharpe > 0 | observed), accounting for skew/kurt + sample length."""
    r = ret.dropna()
    n = len(r)
    if n < 30 or sharpe == 0:
        return float("nan")
    T = n / 252.0
    sk = r.skew()
    ku = r.kurt() + 3.0
    inner = 1 - sk * sharpe + (ku - 1) / 4.0 * sharpe ** 2
    if T <= 1 or inner <= 0:
        return float("nan")
    try:
        from scipy.stats import norm
    except Exception:
        return float("nan")
    return float(norm.cdf(sharpe * sqrt(T - 1) / sqrt(inner)))


def summarize(ret: pd.Series, spy_ret: Optional[pd.Series] = None) -> Dict:
    r = ret.dropna()
    if len(r) < 2:
        return {"sharpe": float("nan"), "total_return": float("nan"), "max_drawdown": float("nan")}
    ann_ret = r.mean() * 252
    ann_vol = r.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    eq = (1 + r).cumprod()
    mdd = float((eq / eq.cummax() - 1).min())
    out = {
        "total_return": float(eq.iloc[-1] - 1), "ann_return": float(ann_ret),
        "ann_vol": float(ann_vol), "sharpe": float(sharpe), "max_drawdown": mdd,
        "psr0": psr0(sharpe, r),
    }
    if spy_ret is not None:
        sa = spy_ret.reindex(r.index).dropna()
        if len(sa) > 2:
            out["spy_sharpe"] = float(sa.mean() * 252 / (sa.std() * np.sqrt(252)))
            out["alpha_ann"] = float(ann_ret - sa.mean() * 252)
    return out


def regime_sharpe(ret: pd.Series, bear_mask: pd.Series, bull_mask: pd.Series) -> Dict:
    return {
        "bear_sharpe": summarize(ret[bear_mask])["sharpe"] if bear_mask.sum() else float("nan"),
        "bull_sharpe": summarize(ret[bull_mask])["sharpe"] if bull_mask.sum() else float("nan"),
    }


def trade_stats(trades: list) -> Dict:
    """Exit-trade stats: hit rate, avg win/loss, payoff (avg_win/avg_loss). The
    numbers that show whether the trailing stop created the asymmetric payoff."""
    if not trades:
        return {"n": 0, "win_rate": float("nan"), "avg_win": float("nan"),
                "avg_loss": float("nan"), "payoff": float("nan")}
    rets = [t["ret"] for t in trades]
    wins = [r for r in rets if r > 0]; losses = [r for r in rets if r <= 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "n": len(rets), "win_rate": len(wins) / len(rets),
        "avg_win": aw, "avg_loss": al, "payoff": (aw / al) if al > 0 else float("inf"),
    }
