"""engine_3 production config — the single source of truth for the strategy knobs.

Both the API (/config, /backtest, /portfolio/state, /selection, /trades) and the
backtester read these. Edit here + redeploy to change the system — the UI is
read-only by design (decisions locked 2026-07-26, see FRONTEND_DESIGN.md §2).

These match the validated S&P-500 result (RESULTS.md): top-10, 252d lookback,
vol-scaled selection, regime-gated, defended with 15% vol-target + 12% DD throttle.
"""
from __future__ import annotations

# Selection (momentum/selection.py::compute_weights)
LOOKBACK = 252            # momentum lookback (trading days)
TOP_N = 10                # hold the top-N names
TARGET_VOL = 0.10         # per-name vol target (equal risk per name)
MAX_WEIGHT = 0.10         # single-name gross cap
REGIME_GATE = True        # go flat when market < 200d MA

# Bear defense (backtest/defend.py::backtest_momentum_defended)
TARGET_PORT_VOL = 0.15    # portfolio vol target (de-gross when realized vol spikes)
DD_THRESHOLD = 0.12       # drawdown backstop: scale *de_gross if DD past high exceeds this
DE_GROSS = 0.50           # exposure multiplier under the drawdown backstop
LEVERAGE_CAP = 1.0        # never scale above 1x even if realized vol < target

# Costs
COST_BPS = 5.0            # round-trip cost per unit turnover (bps)

STARTING_CASH = 100_000.0

# Flattened dict for JSON serialization (GET /config).
CONFIG = {
    "lookback": LOOKBACK,
    "top_n": TOP_N,
    "target_vol": TARGET_VOL,
    "max_weight": MAX_WEIGHT,
    "regime_gate": REGIME_GATE,
    "target_port_vol": TARGET_PORT_VOL,
    "dd_threshold": DD_THRESHOLD,
    "de_gross": DE_GROSS,
    "leverage_cap": LEVERAGE_CAP,
    "cost_bps": COST_BPS,
}


def selection_kwargs() -> dict:
    """kwargs for compute_weights() from the production config."""
    return {
        "lookback": LOOKBACK,
        "top_n": TOP_N,
        "target_vol": TARGET_VOL,
        "max_weight": MAX_WEIGHT,
        "regime_gate": REGIME_GATE,
    }


def defended_kwargs() -> dict:
    """kwargs for backtest_momentum_defended() from the production config.

    Drops regime_gate — the defended backtester forces regime_gate=True internally
    (selection.py gates longs to the bull regime unconditionally there).
    """
    sk = {k: v for k, v in selection_kwargs().items() if k != "regime_gate"}
    return {
        **sk,
        "target_port_vol": TARGET_PORT_VOL,
        "dd_threshold": DD_THRESHOLD,
        "de_gross": DE_GROSS,
        "leverage_cap": LEVERAGE_CAP,
        "cost_bps": COST_BPS,
    }
