import MetricTile from './MetricTile';
import { fmtNum, fmtPct, fmtPctSigned } from '../format';

const FIELDS = [
  { k: 'sharpe', label: 'Sharpe', fmt: fmtNum },
  { k: 'max_drawdown', label: 'Max drawdown', fmt: fmtPct, tone: 'neg' },
  { k: 'total_return', label: 'Total return', fmt: fmtPctSigned },
  { k: 'ann_return', label: 'Ann return', fmt: fmtPctSigned },
  { k: 'ann_vol', label: 'Ann vol', fmt: fmtPct },
  { k: 'psr0', label: 'PSR0', fmt: fmtNum },
];

// Side-by-side metric tiles for two compare sides + the a−b delta.
export default function CompareScorecard({ a, b, delta }) {
  const sides = [a, b];
  return (
    <div>
      <div className="grid grid-2">
        {sides.map((side) => (
          <div className="card" key={side.name}>
            <div className="card-title">{side.name}</div>
            <div className="grid grid-tiles">
              {FIELDS.map((f) => {
                const v = side.metrics[f.k];
                const tone = f.tone || (v >= 0 ? 'pos' : 'neg');
                return <MetricTile key={f.k} label={f.label} value={f.fmt(v)} tone={tone} />;
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">Difference (a − b)</div>
        <div className="grid grid-tiles">
          <MetricTile label="Δ Sharpe" value={fmtNum(delta.sharpe)} tone={delta.sharpe >= 0 ? 'pos' : 'neg'} />
          <MetricTile label="Δ Max drawdown" value={fmtPct(delta.max_drawdown)} tone={delta.max_drawdown >= 0 ? 'pos' : 'neg'} />
          <MetricTile label="Δ Total return" value={fmtPctSigned(delta.total_return)} tone={delta.total_return >= 0 ? 'pos' : 'neg'} />
        </div>
        <p className="note">
          Δ Max drawdown <strong>positive</strong> = side a draws down <em>less</em> than b (shallower = better).
          Δ Sharpe / Δ Total return positive = a is better.
        </p>
      </div>
    </div>
  );
}
