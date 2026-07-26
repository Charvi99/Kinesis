"""engine_3 proper — ATR trailing stops + re-entry lockout on v0 selection.

Per-position state machine over the v0 target weights. Two layers:
  1. trailing stop: exit a name if it drops k*ATR below its high-since-entry.
  2. lockout: after a STOP exit, block re-entry for L days — otherwise the stopped
     name re-enters immediately (still top-N) and the exit is a no-op (verified: an
     A/B without lockout gave identical portfolio returns despite 1190 stop trades).
The lockout is what makes "cut losers" actually reduce exposure to a falling name.

ATR: close-based proxy (rolling mean |daily price change|); refine to true high/low
ATR (risk_utils.calculate_atr) once the loader carries intraday range.
"""
from typing import Dict, List
import pandas as pd


def _atr_proxy(close: pd.Series, period: int = 14) -> pd.Series:
    return close.diff().abs().rolling(period, min_periods=period).mean()


class MomentumEngine:
    def __init__(self, target_weights: pd.DataFrame, closes: pd.DataFrame,
                 k: float = 3.0, lockout_days: int = 10):
        self.W = target_weights
        self.closes = closes
        self.k = k
        self.lockout_days = lockout_days
        self.held: Dict = {}
        self.lockout: Dict = {}   # sid -> date until which re-entry is blocked
        self.trades: List[Dict] = []

    def step(self, date) -> pd.Series:
        target = self.W.loc[date]
        target_sids = set(target.index[target.fillna(0) > 0])
        close = self.closes.loc[date]

        # 1. EXITS (trailing stop OR rank-drop)
        for sid in list(self.held.keys()):
            if sid not in self.closes.columns:
                continue
            px = float(close[sid]); pos = self.held[sid]
            pos["high"] = max(pos["high"], px)
            atr = float(_atr_proxy(self.closes[sid].loc[:date]).iloc[-1])
            reason = None
            if atr and atr > 0 and px < pos["high"] - self.k * atr:
                reason = "stop"
            elif sid not in target_sids:
                reason = "rank"
            if reason:
                self._close(sid, date, px, reason)
                if reason == "stop":
                    self.lockout[sid] = date   # block re-entry

        # 2. ENTERS (target names not held + not in lockout)
        for sid in target_sids:
            if sid in self.held or sid not in self.closes.columns:
                continue
            if sid in self.lockout:
                last = self.lockout[sid]
                # block until lockout_days trading-days have passed
                idx = self.closes.index
                pos = idx.get_loc(last)
                if pos + self.lockout_days > idx.get_loc(date):
                    continue
                del self.lockout[sid]
            px = float(close[sid])
            self.held[sid] = {"entry_date": date, "entry_price": px, "high": px}

        # 3. WEIGHTS: target, zeroed for names not held; re-scale gross <= 100%
        w = target.copy()
        for sid in list(w.index):
            if sid not in self.held:
                w[sid] = 0.0
        gross = w.sum()
        if gross > 1.0:
            w = w / gross
        return w

    def _close(self, sid, date, px, reason):
        pos = self.held.pop(sid)
        ret = (px - pos["entry_price"]) / pos["entry_price"] if pos["entry_price"] else 0.0
        self.trades.append({
            "sid": sid, "entry_date": pos["entry_date"], "exit_date": date,
            "entry": pos["entry_price"], "exit": px, "ret": ret, "reason": reason,
        })
