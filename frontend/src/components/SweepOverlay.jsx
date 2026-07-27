import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { fmtMoney } from '../format';

// Color each swept value teal(170°)->red(0°) across the range, so the legend/curve
// order is intuitive (cool = low value, warm = high value).
function colorFor(t) {
  const hue = 170 - Math.max(0, Math.min(1, t)) * 170;
  return `hsl(${hue.toFixed(0)}, 70%, 45%)`;
}

// Overlay EVERY swept value's equity curve so you can see how the wealth path
// changes as you turn the knob — far more legible than two statistics. `focused`
// (a value) draws that one curve thick and dims the rest.
export default function SweepOverlay({ points, focused, onPick }) {
  if (!points?.length) return null;
  const sorted = [...points].sort((a, b) => a.value - b.value);
  const rank = new Map(sorted.map((p, i) => [p.value, i]));
  const denom = Math.max(1, sorted.length - 1);

  // Merge all curves into one dataset keyed by date.
  const byDate = new Map();
  points.forEach((p) => {
    const key = String(p.value);
    p.equity_curve.forEach((pt) => {
      const row = byDate.get(pt.date) || { date: pt.date };
      row[key] = pt.equity;
      byDate.set(pt.date, row);
    });
  });
  const data = [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1));

  return (
    <div className="chart-card">
      <div className="chart-legend" style={{ flexWrap: 'wrap' }}>
        {sorted.map((p) => (
          <button key={p.value} type="button" className="legend-pick" title="Focus this value"
                  style={{ opacity: focused != null && focused !== p.value ? 0.45 : 1, fontWeight: focused === p.value ? 700 : 500 }}
                  onClick={() => onPick && onPick(p.value)}>
            <span className="swatch" style={{ background: colorFor(rank.get(p.value) / denom) }} />
            {p.value}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={data} margin={{ top: 6, right: 10, left: 4, bottom: 0 }}>
          <CartesianGrid stroke="#eef2f6" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} minTickGap={48} />
          <YAxis tickFormatter={(v) => (v >= 1e3 ? `$${(v / 1e3).toFixed(0)}k` : `$${v}`)} tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} width={48} domain={['auto', 'auto']} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid var(--border)' }} formatter={(v) => fmtMoney(v)} />
          {points.map((p) => {
            const t = rank.get(p.value) / denom;
            const isF = focused === p.value;
            return (
              <Line key={p.value} type="monotone" dataKey={String(p.value)} name={String(p.value)}
                    stroke={colorFor(t)} strokeWidth={isF ? 3.5 : 1.5} dot={false} connectNulls
                    opacity={focused != null && !isF ? 0.3 : 1} />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
