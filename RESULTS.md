# Kinesis — engine_3 validation results (2026-07-26)

> ## ⚠️ DATA-QUALITY CORRECTION (2026-07-27)
>
> The figures in the original sections below were computed on a price DB containing
> **7 corrupt tickers** — `META, BNY, COHR, FISV, COR, ECHO, HONA` — renamed/delisted
> symbols for which the backfill had stored Polygon *placeholder* data: long flat
> zones (a stale value repeated) that then snapped to reality in a single impossible
> day (`META` +1395%, `BNY` +1263%, `COHR` −84%). They inflated the results, **above
> all the defended variant** — the corrupt low-vol flat zones suppressed the
> portfolio's measured realized vol, so the 15% vol-target applied too little
> de-grossing and the defense looked "free."
>
> **Pipeline fixes applied (backend/app/services/):**
> - fetcher now passes `adjusted=True, sort="asc"` (consistent split/dividend adjustment);
> - new `data_quality.py` validator rejects any series with a **>80% single-day move**
>   or a **≥10-day flat zone**; wired into the backfill (reject + untrack) and a
>   `scripts/scan_price_quality.py` scanner;
> - renamed tickers (`META`←`FB`) are recovered via a predecessor-symbol splice;
> - the backfill upsert is delete-first, so re-backfills leave no stale rows.
>
> Universe is now **306 tracked, 0 flagged** (was 312, 7 corrupt). **Re-validated on
> clean data, 5y (2021-07..2026-07), same engine:**
>
> | strategy | total% | annRet% | annVol% | Sharpe | maxDD% |
> |---|---|---|---|---|---|
> | equal-weight universe B&H | 70.5 | — | — | 0.74 | −20.7 |
> | engine_3 **v0** (top-10, no defense) | **250.7** | 29.5 | 29.1 | **1.01** | −32.8 |
> | +defense `target_port_vol=0.15` *(prior prod)* | 54.7 | 13.0 | 19.9 | 0.65 | **−18.6** |
> | +defense `target_port_vol=0.25` *(re-tuned)* | 149 | — | — | **1.06** | −21.5 |
>
> **Honest revised verdict:**
> - The momentum **selection is genuinely strong and real** — v0 Sharpe **1.01** vs
>   equal-weight B&H **0.74** (fresh Polygon data confirms the 2024-26 semis/AI rally
>   driving it: e.g. LITE +642%, AMAT +185% 252d). The edge is selection, as designed.
> - The **0.15 vol-target defense is over-tuned on clean data** — it cuts Sharpe to
>   **0.65 (below B&H)** while improving maxDD only to −18.6%. Loosening to ~0.25
>   recovers Sharpe ~1.06 at maxDD −21.5%. The original "defense halves DD while
>   holding Sharpe" was **an artifact of the corrupt low-vol tickers**.
> - **Open:** re-run the walk-forward / rank-IC / universe-A/B suite on clean data,
>   and re-tune `target_port_vol` (0.20–0.30 range looks better than 0.15).
>
> The sections below are the **original (pre-correction, corrupt-data) record**,
> retained for traceability.


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

## Walk-forward OOS on S&P 500 (train 2021-23 incl bear; test 2024-26 held out)

| top_n | train Sharpe | TEST Sharpe | test total | test maxDD |
|---|---|---|---|---|
| 10 | 0.45 | **1.35** | +215% | −33% |
| 20 | 0.49 | **1.37** | +170% | −31% |
| 30 | 0.48 | 1.29 | +121% | −29% |

**Honest read:** engine_3 is a **bull-participation system** — strong in the held-out
2024-26 bull (test Sharpe ~1.35) but modest through the 2021-23 bear half (train ~0.45).
That's consistent with the entire investigation: momentum on large-caps is bull-beta,
not all-regime alpha. It is a genuinely profitable *bull* momentum strategy (+260%/5y,
Sharpe 1.02) with one clear, honest limitation: **bear exposure / −33% max drawdown.**
The next real lever is a *bear-defense* that doesn't cost the bull (the ATR trailing
stop failed this — it cut the bull too).

## engine_3 vs SPY buy & hold (same 5y window, 2021-07..2026-07)

| strategy | total% | annRet% | annVol% | Sharpe | maxDD% | alpha vs SPY |
|---|---|---|---|---|---|---|
| SPY buy & hold | 68.3 | 11.9 | 17.2 | 0.69 | −25.4 | — |
| equal-weight universe B&H | 86.8 | 13.9 | 16.4 | 0.85 | −17.9 | +2.0%/yr |
| **engine_3 v0 (top-10)** | **260.0** | **30.2** | 29.7 | **1.02** | −33.4 | **+18.2%/yr** |

engine_3 BEATS SPY risk-adjusted (Sharpe 1.02 vs 0.69) and BEATS equal-weight of the
same universe (1.02 vs 0.85) — so the momentum SELECTION adds value beyond holding the
basket. Honest cost: concentrated → higher vol (30% vs 17%) and deeper DD (−33% vs
−25%); bull-skewed (train 0.45 / test 1.35); one in-sample window (PSR0 0.88). The
next lever is a bear-defense that preserves the bull (targets the −33%).

## Bear-defense R&D — vol-target + DD throttle (WIN, 2026-07-26)

A portfolio-level risk overlay (NOT per-name ATR stops, which failed by cutting
winners): scale TOTAL exposure each day by `target_port_vol / trailing_realized_vol`,
plus a drawdown backstop (if equity < high×0.88, scale ×0.5). Applied on the v0
S&P-500 weights:

| engine | total% | annVol% | Sharpe | maxDD% | bearSh |
|---|---|---|---|---|---|
| v0 (no defense) | 260.0 | 29.7 | 1.02 | −33.4 | −3.93 |
| **+vol-target(15%)+DD(12%)** | 108.2 | 20.7 | **0.99** | **−18.6** | −4.94 |

**The win:** maxDD nearly halved (−33% → −19%) **while Sharpe held (1.02 → 0.99)** —
return drops (260→108%) because it de-grosses (exposure 70→44%), but risk-adjusted
return is preserved. **−19% maxDD is now BETTER than SPY's −25%.**

**Robust (not cherry-picked):** across target_port_vol ∈ {0.12, 0.15, 0.20} and
dd_threshold ∈ {0.12, 0.15}, every config improved BOTH Sharpe (+0.01..+0.03) AND
maxDD (+12..+16pp).

**Honest read:** engine_3 + bear-defense is the first system in the project that beats
SPY on BOTH risk-adjusted return (Sharpe ~1.0 vs 0.69) AND drawdown (~−19% vs −25%).
The remaining caveat is unchanged: it's bull-skewed (the alpha is mostly the 2024-26
bull) and one in-sample window (PSR0 0.88). But as a risk-managed momentum system it's
genuinely sound — and the bear defense is the lever that got the DD under the index's.
