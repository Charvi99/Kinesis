import { KNOB_BY_KEY } from '../knobs';
import { openLearn } from '../learn-nav';

// One knob input, rendered by type from knobs.js. Bools -> a toggle (NOT a number
// input — that was the Single-run bug). Number knobs carry min/max/step + the help
// tooltip. `value` is the raw form string/bool; onChange returns the raw new value.
function KnobField({ knobKey, value, onChange }) {
  const k = KNOB_BY_KEY[knobKey];
  if (!k) return null;
  if (k.type === 'bool') {
    return (
      <label className="field-check toggle" title={k.help}>
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        <span className="toggle-track" aria-hidden="true"><span className="toggle-thumb" /></span>
        <span>{k.label} <span className="faint">ⓘ</span></span>
      </label>
    );
  }
  return (
    <label className="field" title={k.help}>
      <span>{k.label}{k.unit ? ` (${k.unit})` : ''} <span className="faint">ⓘ</span></span>
      <input type="number" value={value} min={k.min} max={k.max} step={k.step} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

// A titled sub-card of related knobs with a one-line "why this matters" + an optional
// '?' that deep-links to the Learn page. Only renders keys present in `values`, so the
// same component serves the full EngineForm (incl. starting_cash) and the backtest
// form (which omits starting_cash).
export default function KnobGroup({ group, values, onChange, onHelp }) {
  const keys = group.keys.filter((k) => values && (k in values));
  if (!keys.length) return null;
  return (
    <div className="knob-group">
      <div className="knob-group-head">
        <span className="knob-group-title">{group.title}</span>
        {group.learn && (
          <button className="help-chip" type="button" onClick={() => (onHelp ? onHelp(group.learn) : openLearn(group.learn))} title={`Learn: ${group.title}`}>?</button>
        )}
      </div>
      <p className="knob-group-why">{group.why}</p>
      <div className="form-grid">
        {keys.map((key) => (
          <KnobField key={key} knobKey={key} value={values[key]} onChange={(v) => onChange(key, v)} />
        ))}
      </div>
    </div>
  );
}
