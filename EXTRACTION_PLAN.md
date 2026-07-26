# Kinesis — extraction plan (from StockAnalyzer)

**Goal:** a clean momentum-selection system — broad liquid universe → rank by
momentum → top-N → hold with trailing stops → only in bull regime → vol-targeted,
risk-managed. NO legacy signal-blend code carried over.

Born from the StockAnalyzer edge investigation (8/8 standalone signals null,
combined-ML null, momentum borderline/regime-dependent, regime-switch bear leg
not tradeable long-only). Conclusion: large-cap daily long-only has no robust
predictive edge → the edge must come from **selection + risk management**, not
signal-blending.

This doc is the file-by-file PORT / DROP / ADD / REFACTOR split + build order.
**Review before anything is copied.** Draft v1.

---

## PORT (the reusable lab — keep, ~the valuable core)

**Infra / shell:**
- `docker-compose.yml`, backend `Dockerfile`, `requirements.txt` / `pyproject` (keep talib — momentum uses MA/RSI, cheap).
- `backend/app/db/database.py` (SessionLocal, get_db).
- `backend/app/config/config.py` (settings). **Drop** `pattern_thresholds.py` (legacy).

**Models (selective) — `backend/app/models/`:**
- KEEP: `Stock`, `StockPrice` (core price data).
- KEEP: ledger — `PaperAccount`, `PaperTrade`, `PaperSignalLog`.
- KEEP: `BacktestRun`, `BacktestEquityPoint`.
- KEEP: `BenchmarkPoint` (SPY), `News` (sentiment as an optional feature).
- DROP: `ChartPattern`, `CandlestickPattern`, `TechnicalIndicator` (cache), and all alt-data tables (`insider_trades`, `sec_disclosures`, `short_volume`, `risk_factors`, `stock_floats`, `short_interest`).

**Migrations — `backend/alembic/`:** the StockAnalyzer chain is tangled (audit memory).
**Start fresh** — autogenerate clean migrations from the ported models. Don't copy the old chain.

**Risk + regime (CORE to the new design):**
- `backend/app/utils/risk_utils.py` (position sizing, portfolio heat) — becomes the edge source.
- `backend/app/services/market_regime.py` (regime + direction detection) — the bull/bear gate. Keep the label/direction logic; trim the verbose recommendation table.

**Backtester (signal-agnostic) — `backend/app/services/backtest/`:**
- KEEP: `replay_engine.py`, `fitness.py`, `runner.py`, `backtest_order_calc.py`, `precompute.py`, `backtest_regime.py`.
- REFACTOR: `backtest_signal_adapter.py` — currently dispatches engine_1/engine_2. Slim to engine_3 (momentum) only; keep the no-look-ahead invariant + AST test.

**Ledger (paper-trading) — refactor to run engine_3:**
- `ledger_service.py`, `ledger_signal_adapter.py`, `ledger_health_service.py`, `digest_service.py`, `alert_service.py`, `backend/app/tasks/ledger_tasks.py`, beat schedule.

**Data pipeline:**
- `backend/scripts/polygon_client.py` (REST client), `backend/app/services/polygon_fetcher.py`, the daily-price backfill task. Reuse to seed a **broader universe** (e.g., S&P 500 / Russell 1000 liquid names — not just 200 mega-caps).

**Validation tooling:**
- `backend/scripts/attribution_lib.py` (rank-IC harness) — to validate engine_3 the same way.
- `backend/app/services/benchmark_service.py` (SPY alpha).

**Signal types:** `backend/app/services/signal/types.py` (`SignalResult`, `config_version`) — reused by everything. KEEP.

**Frontend:** port the shell (app, routing, api client, ledger dashboard) → add a new **Selection** view (the ranked universe + open momentum trades). DROP the radar/pattern/strategies views.

---

## DROP (legacy — leave in StockAnalyzer as the research record)

- `backend/app/services/signal/systematic.py`, `swing.py`, `core.py` (the blend engines — engine_1/2).
- `backend/app/services/chart_patterns.py`, `candlestick_patterns.py`, `technical_indicators.py` (~270 KB of detectors with no standalone edge).
- `backend/app/services/strategies/` (the strategies framework).
- `backend/app/services/backtest/ga.py` (GA-over-noise) + the GA API/models/migration.
- `backend/app/services/ml_predictor.py`, the `ml_training` / `ml-training` coupling.
- All alt-data backfills + `*_attribution.py` research probes + the momentum/regime-switch probes (they stay in StockAnalyzer as the investigation record).
- Legacy routes: `analysis.py` (the radar/pattern endpoints), `strategies.py`.

---

## ADD (new — engine_3)

- `backend/app/services/momentum/`:
  - `signal.py` — pure `signal_momentum(df_prices, ...)` → `SignalResult` (ranks the universe by 252d/12-1 momentum; BUY the top-N; vol-targeted size; trailing-stop exit logic). Drops into the existing `signal_as_of` + ledger harness unchanged.
  - `ranking.py` — universe ranking + selection (top-N, equal-risk weighting).
  - `stops.py` — trailing-stop / ATR-stop logic (cut losers, run winners — the actual edge).
- A regime gate: only take momentum longs when market ≥ 200d MA (bull); defensive/cash otherwise.

---

## BUILD ORDER (each step gets the system running before the next)

1. **Skeleton:** docker-compose, Dockerfile, requirements, app package, db, config. → container boots.
2. **Models + fresh migrations** (Stock, StockPrice, BacktestRun, ledger tables). → `alembic upgrade head` clean.
3. **Data pipeline:** polygon fetcher + a broad-universe backfill (S&P 500 liquid). → prices in DB.
4. **Risk + regime + benchmark:** `risk_utils`, `market_regime`, `benchmark_service`.
5. **Backtester core** (refactored, engine_3-only) + the no-look-ahead test.
6. **engine_3:** `momentum/signal.py` + ranking + trailing stops. → first backtest of the new system.
7. **Ledger** (refactored to run engine_3) + beat + digest. → 24/7 paper-trading.
8. **Frontend** Selection view.
9. **Validation:** attribution harness confirms the edge (or honestly doesn't).

---

## Open questions (decide before step 2)

- **Universe:** S&P 500? Russell 1000 top-500 by liquidity? (Needs breadth for momentum, but liquid enough to fill — your no-intraday-illiquidity concern.)
- **Visibility:** repo Private (assumed) — confirm.
- **Sentiment/News:** keep as an optional engine_3 *feature/filter*, or drop entirely for the v1 clean test?
