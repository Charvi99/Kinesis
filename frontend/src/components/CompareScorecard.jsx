import { fmtNum, fmtPct, fmtPctSigned } from '../format';

// Each row: which side is "better". For max_drawdown, higher (less negative) = better.
// For ann_vol, lower = better. Everything else: higher = better.
const ROWS = [
  { key: 'sharpe', label: 'Sharpe', fmt: fmtNum, better: 'high' },
  { key: 'max_drawdown', label: 'Max drawdown', fmt: fmtPct, better: 'high' },
  { key: 'total_return', label: 'Total return', fmt: fmtPctSigned, better: 'high' },
  { key: 'ann_return', label: 'Ann return', fmt: fmtPctSigned, better: 'high' },
  { key: 'ann_vol', label: 'Ann vol', fmt: fmtPct, better: 'low' },
  { key: 'psr0', label: 'PSR0', fmt: fmtNum, better: 'high' },
];

function betterSide(row, av, bv) {
  if (av == null || bv == null || Number.isNaN(av) || Number.isNaN(bv)) return null;
  if (row.better === 'high') return av > bv ? 'a' : bv > av ? 'b' : null;
  return av < bv ? 'a' : bv < av ? 'b' : null;
}

const cell = (row, v) => (v == null || Number.isNaN(v) ? '—' : row.fmt(v));

export default function CompareScorecard({ a, b, delta }) {
  // delta = a − b. Positive sharpe/return delta => a better; positive max_drawdown
  // delta => a is shallower (better).
  const aWins = [];
  const bWins = [];
  if (delta.sharpe > 0) aWins.push('Sharpe'); else if (delta.sharpe < 0) bWins.push('Sharpe');
  if (delta.total_return > 0) aWins.push('return'); else if (delta.total_return < 0) bWins.push('return');
  if (delta.max_drawdown > 0) aWins.push('shallower drawdown'); else if (delta.max_drawdown < 0) bWins.push('shallower drawdown');

  return (
    <div className="card">
      <div className="card-title">Head to head</div>
      <div className="compare-verdict">
        <strong>{a.name}</strong> wins on {aWins.join(', ') || 'nothing'};&nbsp;
        <strong>{b.name}</strong> wins on {bWins.join(', ') || 'nothing'}.
      </div>

      <div className="table-wrap">
        <table className="table compare-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th className="right">{a.name}</th>
              <th className="right">{b.name}</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const av = a.metrics[row.key];
              const bv = b.metrics[row.key];
              const side = betterSide(row, av, bv);
              return (
                <tr key={row.key}>
                  <td>{row.label}</td>
                  <td className={`num right ${side === 'a' ? 'pos' : 'muted'}`}>
                    {cell(row, av)}{side === 'a' && <span className="better"> ▲</span>}
                  </td>
                  <td className={`num right ${side === 'b' ? 'pos' : 'muted'}`}>
                    {cell(row, bv)}{side === 'b' && <span className="better"> ▲</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note">▲ marks the better side on each row. For drawdown, “better” = shallower (closer to 0); for vol, lower.</p>
    </div>
  );
}
