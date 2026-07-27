"""Pure-python guards for the Engine <-> kwargs seam (no DB, no pytest).

Verifies the shapes that the whole config-seam depends on: engine_to_config_dict
produces exactly the 10-knob ConfigOut shape, selection_kwargs / defended_kwargs map
an Engine to the backtester's kwargs (and the defended path drops regime_gate), and
the deployed-engine fallback is usable when the DB has no row.

Run: python3 backend/tests/test_engines_seam.py  (inside the backend container)
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.momentum import engines as E  # noqa: E402

CONFIG_KEYS = {"lookback", "top_n", "target_vol", "max_weight", "regime_gate",
               "target_port_vol", "dd_threshold", "de_gross", "leverage_cap", "cost_bps"}


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        raise SystemExit(1)


# defaults_engine() is the DB-empty fallback — must be Engine-like (getattr-able).
eng = E.defaults_engine()
cfg = E.engine_to_config_dict(eng)
check("engine_to_config_dict -> exactly the 10 ConfigOut keys", set(cfg) == CONFIG_KEYS)

sk = E.selection_kwargs(eng)
check("selection_kwargs -> compute_weights shape",
      set(sk) == {"lookback", "top_n", "target_vol", "max_weight", "regime_gate"})

dk = E.defended_kwargs(eng)
check("defended_kwargs drops regime_gate + carries defense knobs",
      "regime_gate" not in dk
      and {"target_port_vol", "dd_threshold", "de_gross", "leverage_cap", "cost_bps"} <= set(dk))

# A hand-built Engine-like object works too (proves the helpers aren't ORM-coupled).
custom = types.SimpleNamespace(lookback=120, top_n=20, target_vol=0.12, max_weight=0.08,
                               regime_gate=True, defended=False, target_port_vol=0.18,
                               dd_threshold=0.10, de_gross=0.4, leverage_cap=1.0,
                               cost_bps=5.0, starting_cash=100000.0)
check("helpers work on a hand-built Engine-like", E.selection_kwargs(custom)["top_n"] == 20)

print("\nall engine-seam guards passed")
