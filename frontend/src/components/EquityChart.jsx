import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { fmtMoney } from '../format';

// Equity vs benchmark (both scaled to the same starting capital). Borrowed pattern
// from StockAnalyzer's PaperTradingLedger equity+benchmark overlay.
//
// Pass `series=[{key,name,color,width?}]` (and data points carrying those keys) to
// overlay N curves — used by the Lab's Compare mode. Without it, defaults to the
// two-line Kinesis-vs-benchmark view.
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
  { key: 'spy', name: 'Benchmark', color: '#94a3b8', width: 1.5 },
  { key: 'equity', name: 'Kinesis', color: '#0d9488', width: 2 },
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
          <CartesianGrid stroke="#eef2f6" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} minTickGap={48} />
          <YAxis tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} width={48} domain={['auto', 'auto']} />
          <Tooltip content={<Tip />} />
          {useSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color}
                  strokeWidth={s.width || 2} dot={false} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
