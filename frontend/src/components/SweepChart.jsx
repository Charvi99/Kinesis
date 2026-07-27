import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

// The "what does this knob do?" chart: Sharpe (left axis) and max drawdown (right
// axis) vs the swept knob's value. Reading both lines together shows the return/risk
// trade-off as you turn the dial.
export default function SweepChart({ points, knobLabel }) {
  if (!points?.length) return null;
  const data = points.map((p) => ({
    value: p.value,
    sharpe: p.metrics.sharpe,
    maxDD: p.metrics.max_drawdown,
    ret: p.metrics.total_return,
  }));
  const tipStyle = { padding: '8px 10px', background: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 };
  return (
    <div className="chart-card">
      <div className="chart-legend">
        <span><span className="swatch" style={{ background: '#0d9488' }} /> Sharpe (left)</span>
        <span><span className="swatch" style={{ background: '#dc2626' }} /> Max drawdown (right)</span>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 6, right: 10, left: 4, bottom: 18 }}>
          <CartesianGrid stroke="#eef2f6" vertical={false} />
          <XAxis dataKey="value" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }}
                 label={{ value: knobLabel, position: 'insideBottom', offset: -8, fontSize: 11, fill: '#94a3b8' }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11, fill: '#0d9488' }} tickLine={false} axisLine={false} width={40} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#dc2626' }} tickLine={false} axisLine={false}
                 width={44} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip contentStyle={tipStyle} formatter={(v, n) => (n === 'Max drawdown' ? `${(v * 100).toFixed(1)}%` : Number(v).toFixed(2))} />
          <Line yAxisId="left" type="monotone" dataKey="sharpe" name="Sharpe" stroke="#0d9488" strokeWidth={2} dot={{ r: 3 }} />
          <Line yAxisId="right" type="monotone" dataKey="maxDD" name="Max drawdown" stroke="#dc2626" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
