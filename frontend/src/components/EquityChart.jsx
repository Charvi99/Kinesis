import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { fmtMoney } from '../format';

// Equity vs SPY (both scaled to the same starting capital). Borrowed pattern from
// StockAnalyzer's PaperTradingLedger equity+benchmark overlay.
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

export default function EquityChart({ data, height = 300 }) {
  if (!data?.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-legend">
        <span><span className="swatch" style={{ background: '#0d9488' }} /> Kinesis</span>
        <span><span className="swatch" style={{ background: '#94a3b8' }} /> Benchmark (SPY / eq-wt market)</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 6, right: 8, left: 8, bottom: 0 }}>
          <CartesianGrid stroke="#eef2f6" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} minTickGap={48} />
          <YAxis tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} width={48} domain={['auto', 'auto']} />
          <Tooltip content={<Tip />} />
          <Line type="monotone" dataKey="spy" name="Benchmark" stroke="#94a3b8" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="equity" name="Kinesis" stroke="#0d9488" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
