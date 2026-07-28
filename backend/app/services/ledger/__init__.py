"""Paper-trading ledger services — the live counterpart of the backtester.

`cycle.run_cycle` rebalances a live PaperAccount toward the engine's target book each
trading day; `health` reports staleness + reconciliation. The cycle core is a plain
function (scheduler-agnostic) — Celery, a /run endpoint, or a test all call it.
"""
