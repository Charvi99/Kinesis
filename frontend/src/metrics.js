// Turn raw backtest numbers into a verdict a non-quant can read.
// verdict(key, value) -> { label, tone }; benchmark(key) -> str;
// tile(key, value, formatted) -> { value, sub, tone } for <MetricTile/>.

const NEG = '−';  // proper minus glyph, matches fmtPct

export function verdict(key, v) {
  if (v == null || Number.isNaN(v)) return { label: '', tone: '' };
  switch (key) {
    case 'sharpe':
      if (v < 0) return { label: 'losing', tone: 'neg' };
      if (v < 0.5) return { label: 'weak', tone: 'neg' };
      if (v < 1.0) return { label: 'ok', tone: 'muted' };
      if (v < 1.5) return { label: 'strong', tone: 'pos' };
      return { label: 'excellent', tone: 'pos' };
    case 'max_drawdown':
      // drawdown is negative; closer to 0 is better.
      if (v > -0.10) return { label: 'shallow', tone: 'pos' };
      if (v > -0.20) return { label: 'moderate', tone: 'warn' };
      return { label: 'deep', tone: 'neg' };
    case 'psr0':
      if (v >= 0.95) return { label: 'significant', tone: 'pos' };
      if (v >= 0.80) return { label: 'suggestive', tone: 'warn' };
      return { label: 'inconclusive', tone: 'neg' };
    case 'total_return':
    case 'ann_return':
      if (v <= 0) return { label: 'losing', tone: 'neg' };
      if (key === 'ann_return') return { label: v >= 0.20 ? 'strong' : 'positive', tone: 'pos' };
      return { label: v >= 0.5 ? 'strong' : 'positive', tone: 'pos' };
    default:
      return { label: '', tone: '' };
  }
}

export function benchmark(key) {
  switch (key) {
    case 'sharpe': return 'SPY ≈ 0.69';
    case 'max_drawdown': return `SPY ≈ ${NEG}25%`;
    case 'total_return': return 'SPY ≈ +68% / 5y';
    default: return '';
  }
}

// Build a MetricTile-friendly object from a raw metric value + its formatted string.
export function tile(key, value, formatted) {
  const v = verdict(key, value);
  const b = benchmark(key);
  const sub = [v.label, b].filter(Boolean).join(' · ');  // ·
  return { value: formatted, sub: sub || undefined, tone: v.tone };
}
