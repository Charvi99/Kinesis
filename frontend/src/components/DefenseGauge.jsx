import { fmtPct, fmtX } from '../format';

// The signature element: current portfolio drawdown vs the throttle threshold,
// plus the vol-target scale factor. Turns amber inside the throttle zone, red past it.
export default function DefenseGauge({ drawdown, ddThreshold = 0.12, volTargetFactor }) {
  const dd = Math.abs(drawdown || 0);                 // positive magnitude
  const max = Math.max(ddThreshold * 2, dd * 1.1, 0.2); // track scale (threshold near middle)
  const fillPct = Math.min(100, (dd / max) * 100);
  const thrPct = Math.min(100, (ddThreshold / max) * 100);
  const tone = dd >= ddThreshold ? 'bad' : dd >= ddThreshold * 0.6 ? 'warn' : 'ok';

  return (
    <div>
      <div className="row between" style={{ marginBottom: 4 }}>
        <span className="tile-label">Drawdown vs high</span>
        <span className={`num ${tone === 'bad' ? 'neg' : tone === 'warn' ? 'warn' : 'muted'}`} style={{ fontWeight: 600 }}>
          {fmtPct(drawdown)}
        </span>
      </div>
      <div className="gauge">
        <div className="gauge-track">
          <div className={`gauge-fill ${tone}`} style={{ width: `${fillPct}%` }} />
          <div className="gauge-thr" style={{ left: `${thrPct}%` }} title={`throttle @ ${fmtPct(ddThreshold, 0)}`} />
        </div>
        <div className="gauge-legend">
          <span>0%</span>
          <span>throttle {fmtPct(ddThreshold, 0)}</span>
          <span>{fmtPct(max, 0)}</span>
        </div>
      </div>
      <div className="row between" style={{ marginTop: 10 }}>
        <span className="tile-label">Vol-target scale</span>
        <span className="num" style={{ fontWeight: 600 }}>{fmtX(volTargetFactor)}</span>
      </div>
      <p className="note">
        Defense scales total exposure by vol-target ({fmtX(volTargetFactor)}) and halves it
        (×0.5) once drawdown breaches {fmtPct(ddThreshold, 0)}.
      </p>
    </div>
  );
}
