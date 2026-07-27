import { useState } from 'react';
import { KNOBS } from '../knobs';

// Defaults mirror the backend EngineBase (schemas.py).
const DEFAULTS = {
  name: '', description: '',
  lookback: 252, top_n: 10, target_vol: 0.10, max_weight: 0.10,
  regime_gate: true, defended: true, target_port_vol: 0.22, dd_threshold: 0.12,
  de_gross: 0.5, leverage_cap: 1.0, cost_bps: 5.0, starting_cash: 100000.0,
};

const GROUPS = [
  { title: 'Selection', keys: ['lookback', 'top_n', 'target_vol', 'max_weight', 'regime_gate'] },
  { title: 'Bear defense', keys: ['defended', 'target_port_vol', 'dd_threshold', 'de_gross', 'leverage_cap'] },
  { title: 'Cost & capital', keys: ['cost_bps', 'starting_cash'] },
];

// Renders every knob from knobs.js (so labels/units/ranges/tooltips stay in one place).
// `initial` = an engine to edit (or null for new). onSave receives a clean payload.
export default function EngineForm({ initial, onSave, onCancel, submitLabel = 'Save' }) {
  const [form, setForm] = useState({ ...DEFAULTS, ...(initial || {}) });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

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
      <div className="card-title">{initial ? `Edit “${initial.name}”` : 'New engine'}</div>

      <div className="form-grid" style={{ marginBottom: 4 }}>
        <label className="field"><span>Name</span>
          <input value={form.name} required maxLength={64} onChange={(e) => set('name', e.target.value)} placeholder="e.g. aggressive" /></label>
        <label className="field" style={{ gridColumn: 'span 2' }}><span>Description (optional)</span>
          <input value={form.description || ''} onChange={(e) => set('description', e.target.value)} /></label>
      </div>

      {GROUPS.map((g) => (
        <div key={g.title} style={{ marginTop: 14 }}>
          <div className="faint" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>{g.title}</div>
          <div className="form-grid">
            {g.keys.map((key) => {
              const k = KNOBS.find((x) => x.key === key);
              if (k.type === 'bool') {
                return (
                  <label className="field-check" key={key} title={k.help} style={{ alignItems: 'flex-end', paddingBottom: 8 }}>
                    <input type="checkbox" checked={!!form[key]} onChange={(e) => set(key, e.target.checked)} />
                    <span>{k.label} <span className="faint" title={k.help}>ⓘ</span></span>
                  </label>
                );
              }
              return (
                <label className="field" key={key} title={k.help}>
                  <span>{k.label}{k.unit ? ` (${k.unit})` : ''} <span className="faint">ⓘ</span></span>
                  <input type="number" value={form[key]} min={k.min} max={k.max} step={k.step} onChange={(e) => set(key, e.target.value)} />
                </label>
              );
            })}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn--primary" type="submit">{submitLabel}</button>
        {onCancel && <button className="btn" type="button" onClick={onCancel}>Cancel</button>}
        <span className="faint" style={{ alignSelf: 'center' }}>Hover any field for what it does.</span>
      </div>
    </form>
  );
}
