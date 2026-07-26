# Kinesis — engine_3 validation results (2026-07-26)

Universe: 57 liquid US large/mid caps, 5y daily (2021-07..2026-07). Backtest = the
`momentum.selection` portfolio (rank by 252d momentum → top-N → vol-scaled →
regime-gated, 5bps cost), decision at T close / earned T+1 (no look-ahead).

## Momentum rank-IC by regime (does the selection signal predict?)

| regime | h=5 | h=10 | h=21 |
|---|---|---|---|
| ALL   | +0.008 | +0.010 | +0.015 |
| BEAR  | +0.025 | **+0.129** | **+0.095** |
| BULL  | +0.013 | +0.012 | +0.019 |

Unconditional IC is ~null (averages opposite regimes). Bear-sample IC is strong but
noisy (n=1 regime — the 2022 bear). Consistent with the StockAnalyzer finding that
the unconditional null is an averaging artifact.

## Walk-forward OOS (select lookback+top_n on 2021-23; test 2024-26)

- TRAIN-selected: lookback=252, top_n=10 (train Sharpe 0.65)
- OOS test Sharpe = **1.05** (survives the held-out window)
- Full period: Sharpe 0.88, PSR0 **0.89**, maxDD −22%
- Multiple-testing "luck" bar (6 configs, 5y) ≈ 0.85

## Verdict: BORDERLINE

Promising — positive return, survives walk-forward OOS — but **not statistically
conclusive** (PSR0 0.89 < 0.95; one bull test window; bear IC is n=1). This is an
**honest, expected result**: marginal signal edge that needs (a) a **bigger universe**
for cleaner cross-sectional ranking (57 → Russell-1000-style breadth), and (b) the
**risk-management layer** (trailing stops, cut losers) carrying the return — exactly
the thesis from `docs/EDUCATION_AND_EDGE.md`.

Re-run: `docker exec kinesis_backend python /app/scripts/validate_engine.py`
