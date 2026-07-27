import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { fmtMoney } from '../format';
import { CHART, tickStyle, axisLineProps, gridProps } from '../chartTheme';

// Equity vs benchmark (both scaled to the same starting capital).
// Pass `series=[{key,name,color,width?}]` to overlay N curves (Lab Compare);
// without it, defaults to the Kinesis-vs-benchmark two-line view.
function fmtAxis(n) {
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}k`;
  return `$${n}`;
}

function Tip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card" style={{ padding: '8px 10px', boxShadow: 'var(--shadow-md)' }}>
      <div className="faint" style={{ fontSize: 11, marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="num" style={{ color: p.color, fontSize: 12 }}>
          {p.name}: {fmtMoney(p.value)}
        </div>
      ))}
    </div>
  );
}

const DEFAULT_SERIES = [
  { key: 'spy', name: 'Benchmark', color: CHART.bench, width: 1.5 },
  { key: 'equity', name: 'Kinesis', color: CHART.equity, width: 2.5 },
];

export default function EquityChart({ data, height = 300, series, legend }) {
  if (!data?.length) return null;
  const useSeries = series?.length ? series : DEFAULT_SERIES;
  const legendItems = legend ?? useSeries.map((s) => ({ name: s.name, color: s.color }));
  return (
    <div className="chart-card">
      <div className="chart-legend">
        {legendItems.map((l, i) => (
          <span key={i}><span className="swatch" style={{ background: l.color }} /> {l.name}</span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 6, right: 8, left: 8, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="date" tick={tickStyle} tickLine={false} axisLine={axisLineProps} minTickGap={48} />
          <YAxis tickFormatter={fmtAxis} tick={tickStyle} tickLine={false} axisLine={false} width={48} domain={['auto', 'auto']} />
          <Tooltip content={<Tip />} />
          {useSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color}
                  strokeWidth={s.width || 2.5} strokeDasharray={s.dash} dot={false} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
