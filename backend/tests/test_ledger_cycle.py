"""Pure-python guards for the ledger cycle (no DB, no pytest).

Verifies the three properties the whole live ledger depends on:
  (1) accounting identity — rebalance satisfies equity_post == equity_pre - cost, and
      cash + positions_value == equity, across a multi-day rebalance with cost;
  (2) defense factor — defense_factor() reproduces /portfolio/state's vol-target +
      drawdown-throttle math (incl. the <21-pt warmup -> factor 1.0);
  (3) target-book seam — target_book() is the regime-gated compute_weights().iloc[-1]
      scaled by factor*throttle (the live seam, NOT the backtester's zero last row).

Run: python3 backend/tests/test_ledger_cycle.py  (inside the backend container)
"""
import math
import os
import sys
import types

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.ledger import cycle as C  # noqa: E402


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        raise SystemExit(1)


def _series(d):
    return pd.Series(d)


# ── (1) accounting identity over a 2-day rebalance with cost + realized P&L ─────
cost_bps = 5.0
close0 = _series({1: 50.0, 2: 100.0, 3: 25.0})
target0 = _series({1: 0.3, 2: 0.3, 3: 0.3})          # gross 0.9

# day 0: all cash -> buy the target book
out0 = C.rebalance(100_000.0, 100_000.0, {}, target0, close0, cost_bps, 0.0)
check("day0: identity equity == equity_pre - cost",
      abs(out0["equity"] - (100_000.0 - out0["cost"])) < 1e-6)
check("day0: cash + positions_value == equity",
      abs(out0["cash"] + out0["positions_value"] - out0["equity"]) < 1e-6)
check("day0: 3 buys recorded", out0["n_fills"] == 3 and all(f["side"] == "buy" for f in out0["fills"]))
check("day0: cost = turnover * bps/1e4",
      abs(out0["cost"] - 90_000.0 * 5 / 1e4) < 1e-6)

# day 1: prices move; flatten 2 & 3, reload 1 -> realized P&L on the sells
close1 = _series({1: 60.0, 2: 90.0, 3: 30.0})
target1 = _series({1: 0.5, 2: 0.0, 3: 0.0})
equity_pre1 = out0["cash"] + sum(q * close1[sid] for sid, (q, _) in out0["holdings"].items())
out1 = C.rebalance(equity_pre1, out0["cash"], out0["holdings"], target1, close1, cost_bps, out0["realized"])
check("day1: identity equity == equity_pre - cost",
      abs(out1["equity"] - (equity_pre1 - out1["cost"])) < 1e-6)
check("day1: cash + positions_value == equity",
      abs(out1["cash"] + out1["positions_value"] - out1["equity"]) < 1e-6)
check("day1: realized P&L recorded on sells", out1["realized"] != 0.0)
check("day1: flattens are sell/flatten, reload is buy/rebalance",
      any(f["side"] == "sell" and f["reason"] == "flatten" for f in out1["fills"])
      and any(f["side"] == "buy" and f["reason"] == "rebalance" for f in out1["fills"]))
check("day1: only stock 1 held after", set(out1["holdings"]) == {1})


# ── (2) defense factor: warmup, vol-target, drawdown throttle ──────────────────
eng = types.SimpleNamespace(target_port_vol=0.15, dd_threshold=0.12, de_gross=0.5,
                            leverage_cap=1.0)

# <21 daily returns -> rv undefined -> factor 1.0 (warmup), but deep DD -> throttle
short_dd = pd.Series([1.00, 1.05, 1.02, 0.98, 0.92, 0.85, 0.80])   # dd = 0.80/1.05-1
df_short = C.defense_factor(eng, short_dd)
check("defense: <21pt warmup -> factor 1.0", abs(df_short["factor"] - 1.0) < 1e-9)
check("defense: deep drawdown -> throttle = de_gross", abs(df_short["throttle"] - 0.5) < 1e-9)
check("defense: dd computed", abs(df_short["dd"] - (0.80 / 1.05 - 1)) < 1e-9)

# 22-pt oscillation -> rv defined; hand-compute factor and compare (throttle off)
rets = [0.05, -0.05] * 11                              # 22 daily returns, mean ~0
eq = [1.0]
for r in rets:
    eq.append(eq[-1] * (1 + r))
osc = pd.Series(eq)
df_osc = C.defense_factor(eng, osc)
daily = osc.pct_change().dropna().tail(63)
rv = float(daily.std() * math.sqrt(252))
expected_factor = min(eng.target_port_vol / rv, eng.leverage_cap)
check("defense: rv matches hand-computed trailing vol", abs(df_osc["rv"] - rv) < 1e-9)
check("defense: factor == min(target_port_vol/rv, leverage_cap)",
      abs(df_osc["factor"] - expected_factor) < 1e-9)
check("defense: shallow drawdown -> throttle 1.0", abs(df_osc["throttle"] - 1.0) < 1e-9)


# ── (3) target-book seam: compute_weights().iloc[-1] scaled by factor*throttle ──
rng = np.arange(300)
closes = pd.DataFrame({                                  # 3 uptrending stocks, bull regime
    1: 50.0 * (1.001 ** rng) + rng * 0.01,
    2: 25.0 * (1.0015 ** rng),
    3: 100.0 * (1.0008 ** rng) + rng * 0.02,
}, index=pd.date_range("2024-01-01", periods=300, name="ts"))
eng_full = types.SimpleNamespace(lookback=252, top_n=3, target_vol=0.10, max_weight=0.10,
                                 regime_gate=True, target_port_vol=0.15, dd_threshold=0.12,
                                 de_gross=0.5, leverage_cap=1.0, cost_bps=5.0)

from app.services.momentum.selection import compute_weights  # noqa: E402
from app.services.momentum.engines import selection_kwargs    # noqa: E402
sel_last = compute_weights(closes, **selection_kwargs(eng_full)).iloc[-1]

tb1 = C.target_book(closes, eng_full, factor=1.0, throttle=1.0)
check("target_book(factor=1,throttle=1) == compute_weights().iloc[-1]",
      np.allclose(tb1.values, sel_last.values))
check("target_book selects names (non-zero)", (tb1 > 0).sum() >= 1)

tb_half = C.target_book(closes, eng_full, factor=0.5, throttle=1.0)
check("target_book scales by factor", np.allclose(tb_half.values, (sel_last * 0.5).values))
tb_flat = C.target_book(closes, eng_full, factor=1.0, throttle=0.0)
check("target_book throttle=0 -> all cash (no names)", (tb_flat > 0).sum() == 0)


print("\nall ledger-cycle guards passed")
