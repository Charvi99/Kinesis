# Kinesis frontend — UI/UX review (handoff doc)

> Status: written **2026-07-27** as a diagnosis of the *current* (`frontend/`) UI for
> whoever works on it next. An **approved redesign plan already exists** that fixes
> most of this — see §8. Read this for the *why*; read the plan for the *what*.

---

## 0. TL;DR

The frontend is **well-engineered (clean components, good design system) but confusing
as a product**. Three real problems, in priority order:

1. **You can't learn what the knobs do.** The Backtest lab is a wall of 11 unlabeled
   numeric inputs that returns one number — no presets, no sensitivity, no compare.
   This is the single biggest UX gap.
2. **The mental model is muddy.** 5 tabs, but **Dashboard / Selection / Trades are all
   slices of the same one backtest run** (there is no live ledger yet). Nothing tells
   you that what you're seeing is *modeled*, not live — except a buried sentence.
3. **Config is a dead, read-only panel** and there's no way to create/compare engine
   variants — yet that's exactly the "phase 2" power the user wants.

User's own words: *"I am kinda lost in there… selection and trades seem pointless for
now… backtest lab is okay but hard to preset, and I don't understand how different
knobs affect the result… config is now dead… I'd like to add support for adding and
creating engines with different settings."*

---

## 1. What this app is (context for the next agent)

Kinesis is a **portfolio-level momentum-selection** system (engine_3), NOT a per-stock
recommendation tool. Strategy: rank a ~306-name S&P-500 universe by 252-day momentum →
hold top-10, vol-scaled (equal risk) → regime-gated (flat when market < 200d MA) →
bear-defense (portfolio vol-target + drawdown throttle). Validated ~Sharpe 1.0 / maxDD
~−20% (see `RESULTS.md`, with honest caveats: bull-skewed, the 2024-26 AI-rally drives
much of it).

So the **right** mental model for the UI is: *a portfolio dashboard centered on the
current selection + equity + risk state, with a lab to explore the knobs.* The wrong
model (per-stock radar/recommendations) was the previous StockAnalyzer project — do
not reintroduce it.

**Important state fact:** there is **no live trading ledger yet** (backend task #160
pending). Today, Portfolio/Selection/Trades are all derived from a single backtest run
of the production config. They become "live" only once the ledger exists.

---

## 2. Current state (stack + files)

- **Stack:** Vite 8 + React 19 + Recharts 3 + axios; oxlint. Dev proxy `/api`→backend
  (`vite.config.js`); prod served by nginx (`nginx.conf`). Containerized
  (`frontend/Dockerfile`, `docker-compose.yml`).
- **Shell:** `src/App.jsx` — 5 tabs via a `TABS` array + `useState('dashboard')`; a
  health dot in the header calling `/health`.
- **Views:** `src/views/{DashboardView,SelectionView,TradesView,BacktestLabView,ConfigView}.jsx`.
- **Components:** `src/components/{MetricTile,EquityChart,DefenseGauge,RegimeBadge,States}.jsx`.
- **Support:** `src/api.js` (named axios fns), `src/format.js`, `src/hooks/{useQuery,useDebounce}.js`.
- **Styles:** `src/index.css` (design tokens + all component classes), `src/App.css`.
- **Design doc:** `docs/FRONTEND_DESIGN.md` (the v1 spec — still accurate for shapes).

---

## 3. The core problems (verified against the code)

### 3.1 The Backtest lab is unteachable (`src/views/BacktestLabView.jsx`)
- **11 raw numeric inputs** with bare labels (`lookback`, `top_n`, `target_vol`,
  `max_weight`, `target_port_vol`, `dd_threshold`, `de_gross`, `cost_bps`, start, end)
  and a buried `defended` checkbox (`BacktestLabView.jsx:52-75`). No plain-language
  hint, no min/max, no direction ("↑ target_port_vol = more gross → more return AND
  deeper drawdown").
- **No presets** — you start from hardcoded `DEFAULTS` every time; there's no "v0 /
  prod / conservative / aggressive" one-click.
- **No sensitivity/sweep** — you get ONE result per run; you cannot see how Sharpe and
  maxDD move as a knob changes. This is precisely "I don't understand how knobs affect
  the result."
- **No compare/A-B** — can't put two configs side by side.
- The `defended` toggle silently changes which whole backtester runs; the only signal
  is one bolded word in the subtitle (`:46`).
- Client timeout is 60s (`src/api.js:9`); a big sweep would need more.

### 3.2 Mental model / information architecture (`src/App.jsx`)
- **5 tabs, 3 redundant.** Dashboard, Selection, Trades all read the same backtest:
  - `DashboardView.jsx:41` literally says: *"Track record is engine_3 **backtested** at
    production config — there is no live ledger yet, so this is the strategy's modeled
    equity, not realized paper-trading P&L."* That caveat is buried in a `.note`, not a
    top-level badge.
  - `SelectionView` shows the *current target book* (backtest-derived), `TradesView`
    shows *closed round-trips derived from weight history* — both static until you
    rerun the backtest.
- **No "live vs model" framing** anywhere in the chrome. A user can't tell what's real.
- **No hierarchy:** all 5 tabs look equally important.

### 3.3 Config is dead (`src/views/ConfigView.jsx`)
- Read-only tiles; the header says *"Edit `defaults.py` and redeploy — knobs are not
  driven from the UI."* The user wants the opposite (phase 2): to **create engines with
  different settings**. Today there is no concept of multiple/named engine configs —
  the backend has a single global `defaults.CONFIG` dict.

### 3.4 Premature tabs
- **Selection** and **Trades** are correct *for live trading* (today's real book +
  today's real fills), but with no ledger they're just a static backtest snapshot.
  Showing them as top-level peers of the Dashboard invites the question "is this live?"
  — and the answer is no.

### 3.5 No optimization / signal-tilt surface (deferred, but relevant)
- No GA view (StockAnalyzer has `GADashboard.jsx`); no place for the eventual
  sentiment / chart-pattern signal tilt. The user explicitly wants both "later."

---

## 4. Per-view detail

### `App.jsx`
- Tab nav is a flat button row; only `.active` distinguishes the current tab. Consider
  grouping (primary vs secondary) and a "MODEL"/"LIVE" indicator in the header.
- Health dot is good — keep.

### `DashboardView.jsx`
- Strong: regime badge, exposure pill, metric tiles, equity-vs-bench chart, defense
  gauge. Reuse all of this.
- Weak: the "this is modeled, not live" caveat is a footnote. Make it a first-class
  badge so users aren't misled.
- "vs SPY ~0.69" / "vs SPY ~−25%" subs are **hardcoded** (`:34`,`:35`) — they'll lie if
  the deployed config or window changes. Derive from the benchmark, or drop.

### `SelectionView.jsx`
- Solid table (sortable, searchable, held/add/drop badges). Reuse for a live book later.
- The as-of line (`:54`) implies "current target portfolio, as-of now" — but it's the
  backtest's last rebalance, not a live position. Misleading without the MODEL badge.

### `TradesView.jsx`
- Clean trades table with reason badges. Reuse later for live fills.
- Same MODEL-vs-LIVE problem. The reason set is only `rank_drop`/`defense` (no
  trailing-stop reason etc.) because it's derived from weight history, not a real
  ledger.

### `BacktestLabView.jsx`
- See §3.1 — this is the priority rewrite. The result rendering (metric tiles +
  equity chart) is fine and reusable; the **input** half is the problem.

### `ConfigView.jsx`
- Fold into an Engines view (list/create/edit/deploy). As-is it's read-only dead weight.

### Components
- `EquityChart.jsx`: **hardcoded 2 series** (Kinesis `#0d9488`, benchmark `#94a3b8`).
  A compare view needs N named series — generalize it.
- `MetricTile`, `DefenseGauge`, `RegimeBadge`, `States` (Spinner/Error/Empty): all
  good, reuse everywhere.
- `useQuery` is **GET-only** (`src/hooks/useQuery.js`); the Lab already POSTs manually
  with local `useState`. Sweep/compare will follow that manual pattern (or add a small
  mutation hook).

---

## 5. Cross-cutting issues

- **No single source of truth for "what each knob means."** Every place that shows a
  knob (Lab, Config) re-labels it ad hoc. Add a `knobs.js` metadata module (label,
  unit, plain-language direction, min/max/step, when-it-applies) and drive all knob UI
  from it — including tooltips.
- **No concept of an "engine" / named config** anywhere (frontend or backend). This
  blocks presets, compare, create-variants, and GA. (The approved plan makes engines
  DB-backed — see §8.)
- **Numbers vs reality:** benchmark comparisons are hardcoded; "current"/"as-of now"
  language implies live data that doesn't exist yet. Either derive or badge honestly.
- **No empty-state guidance** for "ledger not built yet" — Selection/Trades just show
  backtest data without context.

---

## 6. What's good — do NOT break these

- **Engineering quality:** clean component decomposition, `useQuery`/`useDebounce`
  hooks, consistent loading/error/empty states, env-aware axios client
  (`VITE_API_URL`) + dev/prod proxy.
- **Design system (`src/index.css`):** tokens (`--accent #0d9488`, `--pos/--neg/--warn`),
  `.card`, `.tile`, `.grid/.grid-tiles/.grid-2/.grid-3`, `.btn/.btn--primary`, badges
  (`.badge--bull/--bear/--add/--drop/--held/--neutral/--reason-*`), `.field/.form-grid`,
  `.table`, tones (`.pos/.neg/.warn/.muted/.faint`). New views should reuse ~85% of this.
- **`format.js`:** `fmtMoney/fmtMoney2/fmtPct/fmtPctSigned/fmtNum/fmtX/fmtDate/pnlClass`.
- **Honest, portfolio-first framing** in copy (e.g. the Dashboard footnote). Keep that
  honesty; just promote it to a visible badge.

---

## 7. Recommended direction (high level)

1. **Engines as first-class persisted configs** (DB-backed): list / create / clone /
   edit / delete / deploy. The deployed engine is the single source of truth the
   Dashboard/Selection/Trades/Config all read. This *is* the "phase 2 modify config"
   surface and the home for future sentiment/chart-pattern weights.
2. **A teachable Lab** with three modes: **Single** (today's run), **Sweep** (one knob
   across a range → Sharpe-vs-value + maxDD-vs-value chart — *this teaches what knobs
   do*), **Compare** (two engines side by side). Presets = the DB engines. Per-knob
   tooltips from `knobs.js`.
3. **Reframe tabs to 3 primary:** Dashboard · Lab · Engines. Demote Selection/Trades
   to the end with a **"MODEL · backtest-derived, not live"** badge (flip to LIVE when
   the ledger lands). Fold Config into Engines.
4. **GA + signal-tilt deferred** but plug into the same machinery (GA → optimize an
   engine's knobs over a walk-forward/OOS fitness; signal-tilt → optional weight
   columns A/B'd via Compare).

---

## 8. Pointers

- **Approved redesign plan (read this for the *what*):**
  `~/.claude/plans/expressive-shimmying-quail.md` — "Kinesis frontend v2 —
  engines-as-first-class + a teachable backtest lab." Decisions locked with the user:
  **DB-backed engine CRUD**; **defer GA** (build sweep/compare + engines first).
- **v1 design spec:** `docs/FRONTEND_DESIGN.md` (data contracts in §4 are still valid).
- **The strategy + honest caveats the UI is displaying:** `RESULTS.md`.
- **Backend seams to use:** `app/services/momentum/engines.py` (Engine↔kwargs),
  `app/api/routes/portfolio.py` (`/backtest`, `/config`, `/portfolio/state`,
  `/selection`, `/trades`), `app/api/deps.py` (`load_closes`, `equity_curve_points`).
- **Reusable patterns from the previous project** (`~/StockAnalyzer/frontend/src/`):
  `EngineCard.jsx` (A/B scorecard), `PaperTradingLedger.jsx` (comparison strip + card
  grid), `GADashboard.jsx` (run progress + fitness curve) — borrow patterns, not the
  per-stock components.

---

*End of review.*
