import { useState } from 'react';
import KnobGroup from './KnobGroup';
import { GROUPS } from '../knobs';

// Production defaults (mirror backend EngineBase / the seeded `prod` engine).
const PROD = {
  lookback: 252, top_n: 10, target_vol: 0.10, max_weight: 0.10,
  regime_gate: true, defended: true, target_port_vol: 0.22, dd_threshold: 0.12,
  de_gross: 0.5, leverage_cap: 1.0, cost_bps: 5.0, starting_cash: 100000.0,
};
const DEFAULTS = { name: '', description: '', ...PROD };

// One-click starting points (clone-then-tweak). Only the differing knobs override PROD.
const PRESET_VALUES = {
  prod: { ...PROD },
  'v0-no-defense': { ...PROD, defended: false },
  conservative: { ...PROD, target_port_vol: 0.15, dd_threshold: 0.10, de_gross: 0.40 },
  aggressive: { ...PROD, target_port_vol: 0.30, dd_threshold: 0.15, de_gross: 0.60 },
};

// Knobs render via KnobGroup (grouped, bool toggles, tooltips). `onHelp` wires the
// '?' Learn deep-link (optional). `initial` = an engine to edit (or null for new).
export default function EngineForm({ initial, onSave, onCancel, submitLabel = 'Save', onHelp }) {
  const [form, setForm] = useState({ ...DEFAULTS, ...(initial || {}) });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const editing = !!initial;

  const applyPreset = (name) => {
    if (PRESET_VALUES[name]) setForm((f) => ({ ...f, ...PRESET_VALUES[name] }));
  };

  const submit = (e) => {
    e.preventDefault();
    onSave({
      name: form.name.trim(),
      description: form.description?.trim() || null,
      lookback: +form.lookback, top_n: +form.top_n,
      target_vol: +form.target_vol, max_weight: +form.max_weight,
      regime_gate: !!form.regime_gate, defended: !!form.defended,
      target_port_vol: +form.target_port_vol, dd_threshold: +form.dd_threshold,
      de_gross: +form.de_gross, leverage_cap: +form.leverage_cap,
      cost_bps: +form.cost_bps, starting_cash: +form.starting_cash,
    });
  };

  return (
    <form className="card" onSubmit={submit} style={{ marginBottom: 16 }}>
      <div className="card-title">{editing ? `Edit “${initial.name}”` : 'New engine'}</div>

      <div className="form-grid" style={{ marginBottom: 4 }}>
        <label className="field"><span>Name</span>
          <input value={form.name} required maxLength={64} onChange={(e) => set('name', e.target.value)} placeholder="e.g. aggressive" /></label>
        {!editing && (
          <label className="field"><span>Start from (optional)</span>
            <select value="" onChange={(e) => { if (e.target.value) applyPreset(e.target.value); }}>
              <option value="">— blank / production defaults —</option>
              <option value="prod">prod (validated)</option>
              <option value="v0-no-defense">v0 — no defense</option>
              <option value="conservative">conservative (tighter defense)</option>
              <option value="aggressive">aggressive (looser defense)</option>
            </select></label>
        )}
        <label className="field" style={{ gridColumn: 'span 2' }}><span>Description (optional)</span>
          <input value={form.description || ''} onChange={(e) => set('description', e.target.value)} /></label>
      </div>

      {GROUPS.map((g) => (
        <div key={g.title} style={{ marginTop: 14 }}>
          <KnobGroup group={g} values={form} onChange={set} onHelp={onHelp} />
        </div>
      ))}

      <p className="note" style={{ marginTop: 12 }}>
        <strong>Bear defense on</strong> = the vol-target + drawdown throttle runs. Off = raw v0 selection (more return, deeper drawdowns).
      </p>

      <div style={{ marginTop: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn btn--primary" type="submit">{submitLabel}</button>
        {onCancel && <button className="btn" type="button" onClick={onCancel}>Cancel</button>}
        <span className="faint" style={{ fontSize: 12 }}>Hover any field for what it does.</span>
      </div>
    </form>
  );
}
