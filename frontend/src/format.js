export const fmtMoney = (n) =>
  n == null ? '—'
  : Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

export const fmtMoney2 = (n) =>
  n == null ? '—'
  : Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });

export const fmtPct = (n, digits = 1) =>
  n == null ? '—' : `${(Number(n) * 100).toFixed(digits)}%`;

export const fmtPctSigned = (n, digits = 1) => {
  if (n == null) return '—';
  const v = Number(n) * 100;
  const s = `${Math.abs(v).toFixed(digits)}%`;
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : `${s}`;
};

export const fmtNum = (n, digits = 2) => (n == null ? '—' : Number(n).toFixed(digits));

export const fmtX = (n, digits = 2) => (n == null ? '—' : `${Number(n).toFixed(digits)}×`);

export const pnlClass = (n) => (n == null ? '' : Number(n) > 0 ? 'pos' : Number(n) < 0 ? 'neg' : '');

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
