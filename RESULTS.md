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

## engine_3 proper — ATR trailing-stop risk layer (A/B, 2026-07-26)

Added the thesis's risk layer: trailing stop (exit if `price < high − k·ATR`) +
re-entry lockout (the lockout is essential — without it the stopped name re-enters
next day and the exit is portfolio-neutral; verified). A/B vs v0 (no stops), same
57-stock universe, daily rebalance, top-N=10:

| k | total% | Sharpe | maxDD% | payoff | win-rate |
|---|---|---|---|---|---|
| v0 (no stop) | 112.3 | **0.88** | −22.1 | — | — |
| k=3 | 24.8 | 0.40 | −17.2 | 1.83 | 0.43 |
| k=4 | 54.2 | 0.66 | −15.3 | 1.98 | 0.42 |
| k=5 | 65.2 | 0.72 | **−14.2** | 1.83 | 0.44 |
| k=8 | 67.1 | 0.68 | −17.8 | 2.05 | 0.42 |

**Verdict: the risk layer trades return for drawdown — it does NOT improve risk-
adjusted return.** The trailing stop reliably cuts max drawdown (−22% → −14..−18%)
and produces the predicted asymmetric payoff (~1.8–2.0: avg win 6% vs avg loss 3%),
**but** the re-entry lockout keeps the engine out of *winners that pulled back then
resumed*, and that opportunity cost outweighs the cut-loser benefit → lower Sharpe at
every k. You can have lower DD *or* higher Sharpe, not both.

**Honest conclusion:** on this universe the ATR trailing stop is a **risk dial, not an
alpha source** — consistent with the broader finding that large-cap daily momentum's
marginal edge isn't rescued by the risk layer. The genuine levers remain: a **broader
universe** (the seed fix is the prerequisite) and/or a **less-efficient market**.

## Universe-size A/B — breadth done right HELPS (2026-07-26)

engine_3 v0 (rank-drop, regime-gated, vol-scaled, daily) across universes, 5y:

| universe | n | Sharpe | total% | maxDD% | PSR0 |
|---|---|---|---|---|---|
| curated mega-caps | 57 | 0.88 | 112 | −22 | 0.89 |
| alphabetical Polygon (biased, A-letter) | 300 | 0.52 | 81 | −39 | 0.81 |
| **S&P 500 (representative liquid)** | **312** | **1.02** | **260** | −33 | 0.88 |

**The breadth thesis holds — when the universe is representative and liquid.** More
names to rank sharpens the cross-sectional selection (Sharpe 0.88 → 1.02, return
112% → 260%). The earlier "broad was worse" was an artifact of the alphabetical
Polygon sample (A–AZ tickers + junk/SPACs), NOT real breadth. The S&P 500 set is the
correct universe for US large-cap momentum.

**Caveats (honest):** PSR0 0.88 is still < 0.95 (economically strong, statistically
suggestive — not a slam-dunk); maxDD −33% is the weakness (the 2022 bear draws the
whole market down despite the regime gate — the one bear in-sample). The ATR trailing
stop remains net-negative (Sharpe 0.14 here) — it's a risk dial, not alpha.
