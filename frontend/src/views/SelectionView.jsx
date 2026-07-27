import { useMemo, useState } from 'react';
import { getSelection } from '../api';
import { useQuery } from '../hooks/useQuery';
import { useDebounce } from '../hooks/useDebounce';
import { Spinner, ErrorState, EmptyState } from '../components/States';
import { fmtPct } from '../format';

const COLUMNS = [
  { key: 'rank', label: '#', type: 'num' },
  { key: 'symbol', label: 'Symbol' },
  { key: 'name', label: 'Name' },
  { key: 'momentum_score', label: '252d momentum', type: 'pct', sortable: true },
  { key: 'weight', label: 'Weight', type: 'pct', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
];

function StatusBadge({ row }) {
  if (row.changed === 'add') return <span className="badge badge--add">Add</span>;
  if (row.changed === 'drop') return <span className="badge badge--drop">Drop</span>;
  if (row.held) return <span className="badge badge--held">Held</span>;
  return <span className="faint">—</span>;
}

export default function SelectionView() {
  const { data, error, loading, refetch } = useQuery(() => getSelection(100), []);
  const [q, setQ] = useState('');
  const [sort, setSort] = useState({ key: 'rank', dir: 'asc' });
  const dq = useDebounce(q, 150).toUpperCase();

  const rows = useMemo(() => {
    if (!data) return [];
    let r = data;
    if (dq) r = r.filter((x) => (x.symbol || '').toUpperCase().includes(dq) || (x.name || '').toUpperCase().includes(dq));
    const { key, dir } = sort;
    const mul = dir === 'asc' ? 1 : -1;
    return [...r].sort((a, b) => {
      if (key === 'status') {
        const av = a.changed || (a.held ? 'held' : 'zzz'), bv = b.changed || (b.held ? 'held' : 'zzz');
        return mul * av.localeCompare(bv);
      }
      const av = a[key], bv = b[key];
      if (typeof av === 'number') return mul * (av - bv);
      return mul * String(av).localeCompare(String(bv));
    });
  }, [data, dq, sort]);

  const toggleSort = (key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'rank' ? 'asc' : 'desc' }));

  return (
    <div className="view">
      <div className="view-head row between">
        <div>
          <h2>Selection ranking <span className="badge badge--model">model</span></h2>
          <p className="tag-asof">Universe ranked by 252-day momentum; top-{data?.filter((x) => x.held).length || '?'} held, vol-scaled. Current target portfolio, as-of now.</p>
        </div>
        <span className="faint" style={{ maxWidth: 280, textAlign: 'right', fontSize: 12 }}>
          Backtest-derived target book — not a live position list until the ledger goes live.
        </span>
      </div>
      <div className="card">
        <div className="row between" style={{ marginBottom: 12 }}>
          <div className="card-title" style={{ marginBottom: 0 }}>Current target book</div>
          <input className="search-input" style={{ maxWidth: 240 }} placeholder="Search symbol / name…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={refetch} /> : !rows.length ? <EmptyState>No matching names.</EmptyState> : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  {COLUMNS.map((c) => (
                    <th key={c.key} className={`${c.type === 'pct' ? 'right' : ''} ${c.sortable ? 'sortable' : ''}`}
                      onClick={c.sortable ? () => toggleSort(c.key) : undefined}>
                      {c.label}
                      {c.sortable && sort.key === c.key && <span className="arrow"> {sort.dir === 'asc' ? '▲' : '▼'}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.symbol} className={r.held ? 'held' : ''}>
                    <td className="num">{r.rank}</td>
                    <td className="sym">{r.symbol}</td>
                    <td className="muted">{r.name || '—'}</td>
                    <td className="num right">{fmtPct(r.momentum_score)}</td>
                    <td className="num right">{r.held ? fmtPct(r.weight, 1) : '—'}</td>
                    <td><StatusBadge row={r} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
