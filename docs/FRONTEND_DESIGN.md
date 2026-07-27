# Kinesis — frontend design + onboarding doc

A self-contained brief for whoever builds the UI next (human or agent). It carries the
full context, the design, the data contracts, the setup, and explicit pointers into the
**previous StockAnalyzer** frontend for reusable patterns.

---

## 1. Context — what Kinesis is

Kinesis is a **momentum-selection trading system** (born from the StockAnalyzer edge
investigation, which proved per-stock signal-blending has no edge on large-cap daily).
The strategy (`engine_3`) is **portfolio-level**, not per-stock:

> Rank a broad liquid universe (312 S&P-500 names) by 252-day momentum → hold the
> **top-10**, vol-scaled (equal risk per name) → **regime-gated** (go flat when the
> market < its 200-day MA) → **bear-defense** (scale total exposure by portfolio
> vol-target 15% + a drawdown backstop).

**Validated result (5y, in-sample, see `RESULTS.md`):** Sharpe ~1.0 vs SPY 0.69;
maxDD ~−19% vs SPY −25% — i.e. it beats the index on **both** risk-adjusted return and
drawdown. Honest caveats: bull-skewed, one in-sample window (PSR0 0.88).

**So the frontend is a PORTFOLIO dashboard**, centered on the current selection + equity
curve + risk state — NOT a per-stock recommendation/radar tool (that was StockAnalyzer's
model, and it's the wrong mental model here).

## 2. Decisions locked (with the user, 2026-07-26)

- **Stack:** fresh **Vite + React 18 + Recharts + axios** (NOT a port of StockAnalyzer's
  CRA app — rebuild clean, but borrow *patterns* from it; see §7).
- **V1 views:** Portfolio dashboard + Selection ranking + Trades log + Backtest lab.
- **Config:** **read-only display** (knobs change via code + redeploy, not from the UI).

## 3. The four views

### 3.1 Portfolio dashboard (home)
The "is the system working" glance.
- **Equity curve vs SPY** (Recharts line chart, SPY scaled to same starting capital).
- **Headline metrics:** total return, ann return, ann vol, **Sharpe**, **maxDD**, current
  **exposure** (% gross), time in market.
- **Regime badge:** `BULL` / `BEAR` (market vs 200d MA) — green/red.
- **Defense status:** the current vol-target scale factor (`target_port_vol / realized_vol`)
  and the current drawdown vs the `dd_threshold` (visual: drawdown gauge; turns red when
  within the throttle zone).

### 3.2 Selection ranking (the core of a momentum UI)
- A table of the **universe ranked by momentum score** (252d return), with the **top-N
  (held) names highlighted** and their **current weights**.
- Columns: rank · symbol · name · momentum score · weight (held) · status (HELD / ADD /
  DROP). "ADD"/"DROP" = entered/left the top-N at the last rebalance.
- Sortable; search/filter by symbol.

### 3.3 Trades log
- Entry/exit history with **reason** (`rank_drop` / `trailing_stop` / `defense`), entry &
  exit price, **return**, hold time.
- Reuse StockAnalyzer's trades-table pattern (§7).

### 3.4 Backtest lab
- A form with the knobs: `lookback`, `top_n`, `target_vol`, `target_port_vol`,
  `dd_threshold`, `de_gross`, `cost_bps`, start/end dates, v0-vs-defended toggle.
- `POST /api/backtest` → show the metrics table + the equity curve. Lets you dial the
  risk knob live and see the DD/return trade-off.

### 3.5 Config (read-only)
- Shows the current engine knobs (`lookback=252`, `top_n=10`, `target_vol=0.10`,
  `target_port_vol=0.15`, `dd_threshold=0.12`, `de_gross=0.5`, `regime_gate=true`).
  Display only — note "edit in `momentum/selection.py` + redeploy".

## 4. Backend API contract (endpoints to build)

The frontend calls these (all under `/api/v1`, FastAPI in `backend/app/api/routes/`).
Example JSON shapes are **synthetic** — the contract, not live data:

```
GET /api/v1/portfolio/state
→ { "equity": 208030.12, "starting_cash": 100000,
    "equity_curve": [{"date":"2024-01-02","equity":100120,"spy":100000}, ...],
    "metrics": {"total_return":1.08,"ann_return":0.206,"ann_vol":0.207,
                "sharpe":0.99,"max_drawdown":-0.186},
    "regime":"bull",
    "defense":{"vol_target_factor":0.72,"drawdown":-0.04,"dd_threshold":0.12},
    "exposure":0.44 }

GET /api/v1/selection?limit=50
→ [{ "symbol":"NVDA","name":"NVIDIA","momentum_score":0.82,"rank":1,"weight":0.10,
    "held":true,"changed":null },
   { "symbol":"AAPL","name":"Apple","momentum_score":0.71,"rank":2,"weight":0.10,
    "held":true,"changed":"add" },
   { "symbol":"X","name":"...", "rank":11, "held":false, "changed":"drop" }, ...]

GET /api/v1/trades?limit=100
→ [{ "symbol":"AAPL","entry_date":"2024-03-04","exit_date":"2024-05-10",
    "entry":172.0,"exit":184.5,"ret":0.073,"reason":"rank_drop" }, ...]

POST /api/v1/backtest   { "lookback":252,"top_n":10,"target_port_vol":0.15,
                          "dd_threshold":0.12,"start_date":"2021-07-26","end_date":"2026-07-25" }
→ { "metrics": {...same shape...}, "equity_curve":[...], "trades_count":815 }

GET /api/v1/config
→ { "lookback":252,"top_n":10,"target_vol":0.10,"target_port_vol":0.15,
    "dd_threshold":0.12,"de_gross":0.5,"regime_gate":true }
```

Note: **`/portfolio/state`, `/selection`, `/trades` require the live ledger (step 7)** —
not built yet. `/backtest` and `/config` can be built now (they read from the backtester,
no ledger needed). Build `/backtest`+`/config` first so the dashboard's backtest lab works
end-to-end before the ledger exists.

## 5. Tech & setup

- **Scaffold:** `npm create vite@latest frontend -- --template react` inside `~/Kinesis`,
  then `npm i recharts axios`.
- **Dev proxy:** in `vite.config.js`, proxy `/api` → `http://localhost:8081` (the backend)
  so dev (`npm run dev`, default :5173) talks to the backend without CORS fuss.
- **Prod:** add a `frontend` service to `docker-compose.yml` (build, serve the Vite build
  on :3001, offset from StockAnalyzer's :3000). The backend already serves CORS `*`.
- **Layout:** tab navigation across the 4 views (simple state toggle or `react-router` —
  StockAnalyzer uses a state toggle; a small tab bar is fine for 4 views).

## 6. Build order

1. Vite scaffold + `src/api.js` (axios client, baseURL `/api/v1`) + dev proxy.
2. **Backend:** `GET /config` + `POST /backtest` (no ledger needed).
3. **Backtest lab view** (form → chart + metrics) — first end-to-end UI.
4. **Backend:** `GET /portfolio/state` + `GET /selection` + `GET /trades` (needs ledger).
5. **Portfolio dashboard** + **Selection ranking** + **Trades** views.
6. **Config** read-only panel.

## 7. Reuse / inspiration from the PREVIOUS project — `~/StockAnalyzer/frontend/src/`

Stack is fresh, but **borrow these patterns** (the previous agent solved the same charting
+ table problems; don't redo them):

| want | look at | what to borrow |
|---|---|---|
| equity-vs-SPY line chart | `components/PaperTradingLedger.jsx` | the Recharts equity+benchmark overlay + scaling-to-starting-cash |
| A/B scorecard / metric tiles | `components/PaperTradingLedger.jsx`, `EngineCard.jsx` | metric-tile layout (Sharpe / return / DD / exposure) |
| trades table w/ reasoning | `components/EngineDetail.jsx`, `PaperTradingLedger.jsx` | expandable trade rows, reason badges |
| market/regime badge | `components/MarketStatus.jsx` | green/red status pill (use for BULL/BEAR) |
| portfolio risk display | `components/PortfolioHeatMonitor.jsx` | gauge-style risk readout (use for defense/drawdown) |
| price/equity chart | `components/StockChart.jsx` | Recharts line/area setup |
| axios api client | `services/api.js` | baseURL derivation from `window.location` (works on localhost/LAN/Tailscale) |
| view navigation | `App.jsx` | the view-toggle pattern (or upgrade to a tab bar) |

**Do NOT port** (wrong model for a portfolio strategy): `SignalRadar`, `CandlestickPatterns`,
`ChartPatterns`, `TechnicalAnalysis`, `TradingStrategies`, `SentimentAnalysis`,
`GADashboard`, `AddStockModal` — all per-stock/legacy.

## 8. Reading order for the next agent

1. `EXTRACTION_PLAN.md` — what Kinesis is, what was ported/dropped.
2. `RESULTS.md` — the validated strategy + honest caveats (what the UI is displaying).
3. `backend/app/services/momentum/selection.py` + `backtest/defend.py` — the actual
   engine (the knobs the Config view shows + the Backtest lab drives).
4. This doc.
5. StockAnalyzer's `PaperTradingLedger.jsx` (§7) for chart/table patterns to reuse.
