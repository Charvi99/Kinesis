"""Pure-python guard for the LIVE equity-curve reconstruction
(app.api.deps.equity_curve_from_snapshots).

Locks out the two regressions that broke the live dashboard:
  1. SPY must MOVE — a timestamp-indexed SPY series reindexed onto midnight snapshot
     dates must not collapse to a flat line (the original reindex matched nothing because
     closes.index carries a time component while snapshot dates are midnight).
  2. The curve must plot the ABSOLUTE snapshot equities (start at eq[0], end at eq[-1]),
     not re-compound daily returns from a carried endpoint base (which scaled the curve
     ~3x and started it at the wrong value).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.api.deps import equity_curve_from_snapshots


def test_absolute_equity_and_moving_spy():
    # Snapshot equities: $100k -> $150k (the absolute book), MIDNIGHT dates.
    dates = pd.date_range("2022-01-03", periods=5, freq="D")
    eq = pd.Series([100000.0, 102000.0, 98000.0, 130000.0, 150000.0], index=dates)
    # SPY prices on a TIMESTAMP index WITH a time component (mirrors closes.index), rising.
    ts = pd.to_datetime([
        "2022-01-03 20:00:00", "2022-01-04 20:00:00", "2022-01-05 20:00:00",
        "2022-01-06 20:00:00", "2022-01-07 20:00:00",
    ])
    spy_px = pd.Series([100.0, 104.0, 103.0, 112.0, 120.0], index=ts)

    pts = equity_curve_from_snapshots(eq, spy_px)
    eqs = [p["equity"] for p in pts]
    sps = [p["spy"] for p in pts]

    # (2) equity is the absolute book, not a re-compound from a carried endpoint.
    assert abs(eqs[0] - 100000.0) < 1e-6, ("equity start", eqs[0])
    assert abs(eqs[-1] - 150000.0) < 1e-6, ("equity end", eqs[-1])

    # (1) SPY rebased to start at the first equity AND moves (was a dead-flat line).
    assert abs(sps[0] - 100000.0) < 1e-6, ("spy start", sps[0])
    assert max(sps) - min(sps) > 1.0, ("spy flat — regression", sps)
    assert sps[-1] > sps[0], ("spy should rise over the window", sps)
    # rebased last = 120 * (100000/100) = 120000
    assert abs(sps[-1] - 120000.0) < 1e-6, ("spy end rebase", sps[-1])


def test_downsample_keeps_endpoints():
    # Many points -> still bounded, still starts/ends at the absolute book values.
    n = 1500
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    eq = pd.Series([100000.0 + i for i in range(n)], index=dates)
    spy_px = pd.Series([100.0 + i * 0.01 for i in range(n)], index=dates)
    pts = equity_curve_from_snapshots(eq, spy_px)
    assert 0 < len(pts) <= 601, len(pts)
    assert abs(pts[0]["equity"] - 100000.0) < 1e-6
    assert abs(pts[-1]["equity"] - (100000.0 + n - 1)) < 1e-6


if __name__ == "__main__":
    test_absolute_equity_and_moving_spy()
    test_downsample_keeps_endpoints()
    print("all equity-curve guards passed")
