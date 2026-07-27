// Shared chart palette + axis styling. Hex values mirror the --c-*/--axis-ink CSS
// tokens in index.css — recharts renders SVG attributes (fill/stroke) which do not
// resolve CSS var(), so we keep the concrete colors here.
export const CHART = {
  equity: '#0d9488',
  bench: '#94a3b8',
  compare: '#7c3aed',
  neg: '#dc2626',
  grid: '#eef2f6',
  axisLine: '#e2e8f0',
  axisInk: '#475569',   // darker than the old #94a3b8 — legible axes
};
export const tickStyle = { fontSize: 12, fill: CHART.axisInk };
export const axisLineProps = { stroke: CHART.axisLine };
export const gridProps = { stroke: CHART.grid, vertical: false };
