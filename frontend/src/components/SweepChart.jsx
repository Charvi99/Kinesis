import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { CHART, gridProps, axisLineProps } from '../chartTheme';

// Sharpe (left axis) and max drawdown (right axis) vs the swept knob value.
export default function SweepChart({ points, knobLabel }) {
  if (!points?.length) return null;
  const data = points.map((p) => ({ value: p.value, sharpe: p.metrics.sharpe, maxDD: p.metrics.max_drawdown }));
  const tipStyle = { padding: '8px 10px', background: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 };
  return (
    <div className="chart-card">
      <div className="chart-legend">
        <span><span className="swatch" style={{ background: CHART.equity }} /> Sharpe (left)</span>
        <span><span className="swatch" style={{ background: CHART.neg }} /> Max drawdown (right)</span>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 6, right: 10, left: 4, bottom: 18 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="value" tick={{ fontSize: 12, fill: CHART.axisInk }} tickLine={false} axisLine={axisLineProps}
                 label={{ value: knobLabel, position: 'insideBottom', offset: -8, fontSize: 12, fill: CHART.axisInk }} />
          <YAxis yAxisId="left" tick={{ fontSize: 12, fill: CHART.equity }} tickLine={false} axisLine={false} width={40} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12, fill: CHART.neg }} tickLine={false} axisLine={false}
                 width={44} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip contentStyle={tipStyle} formatter={(v, n) => (n === 'Max drawdown' ? `${(v * 100).toFixed(1)}%` : Number(v).toFixed(2))} />
          <Line yAxisId="left" type="monotone" dataKey="sharpe" name="Sharpe" stroke={CHART.equity} strokeWidth={2.5} dot={{ r: 3 }} />
          <Line yAxisId="right" type="monotone" dataKey="maxDD" name="Max drawdown" stroke={CHART.neg} strokeWidth={2.5} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
