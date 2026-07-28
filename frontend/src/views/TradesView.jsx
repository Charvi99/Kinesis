import { useMemo, useState } from 'react';
import { getPortfolioState, getTrades } from '../api';
import { useQuery } from '../hooks/useQuery';
import { Spinner, ErrorState, EmptyState } from '../components/States';
import Pagination from '../components/Pagination';
import { fmtMoney2, fmtPctSigned, fmtDate } from '../format';

const PAGE = 25;
const REASONS = [{ k: 'all', l: 'All' }, { k: 'open', l: 'Open' }, { k: 'rank_drop', l: 'Rank drop' }, { k: 'defense', l: 'Defense' }];

function holdDays(e, x) { return Math.round((new Date(x) - new Date(e)) / 86400000); }

export default function TradesView() {
  const { data, error, loading, refetch } = useQuery(() => getTrades(1000), []);
  const { data: st } = useQuery(getPortfolioState, []);
  const live = !!st?.live;          // flip the badge/caption when the deployed engine is live
  const [reason, setReason] = useState('all');
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    const all = data || [];
    return reason === 'all' ? all : all.filter((t) => t.reason === reason);
  }, [data, reason]);
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE));
  const cur = Math.min(page, pageCount);
  const slice = rows.slice((cur - 1) * PAGE, cur * PAGE);
  const setReasonBoth = (r) => { setReason(r); setPage(1); };

  return (
    <div className="view">
      <div className="view-head row between">
        <div>
          <h2>Trades log {live
            ? <span className="badge badge--live"><span className="live-dot" /> live</span>
            : <span className="badge badge--model">model</span>}</h2>
          <p className="tag-asof">{live
            ? <>Real paper fills from the ledger. Reason <em>open</em> = a position still held; <em>defense</em> = a regime flatten; <em>rank_drop</em> = fell out of the top-N.</>
            : <>Closed round-trips derived from the selection's weight history. Reason <em>defense</em> = a regime flatten; <em>rank_drop</em> = fell out of the top-N.</>} Most recent first.</p>
        </div>
        <span className="faint" style={{ maxWidth: 280, textAlign: 'right', fontSize: 12 }}>{live ? 'Live paper fills — real executions from the ledger.' : 'Derived from weight history — not live fills until the ledger goes live.'}</span>
      </div>
      <div className="card">
        <div className="row between" style={{ marginBottom: 12 }}>
          <div className="subtabs">
            {REASONS.map((r) => (
              <button key={r.k} className={`subtab ${reason === r.k ? 'active' : ''}`} onClick={() => setReasonBoth(r.k)}>{r.l}</button>
            ))}
          </div>
          <span className="faint num">{rows.length} trade{rows.length === 1 ? '' : 's'}</span>
        </div>
        {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={refetch} /> : !rows.length ? (
          <EmptyState>No trades{reason !== 'all' ? ` (${reason})` : ''}.</EmptyState>
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Symbol</th><th>Entry</th><th>Exit</th>
                    <th className="right">Entry px</th><th className="right">Exit px</th>
                    <th className="right">Hold</th><th className="right">Return</th><th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {slice.map((t, i) => (
                    <tr key={`${t.symbol}-${t.exit_date}-${i}`}>
                      <td className="sym">{t.symbol}</td>
                      <td className="muted num">{fmtDate(t.entry_date)}</td>
                      <td className="muted num">{fmtDate(t.exit_date)}</td>
                      <td className="num right">{fmtMoney2(t.entry)}</td>
                      <td className="num right">{fmtMoney2(t.exit)}</td>
                      <td className="num right muted">{t.exit_date ? `${holdDays(t.entry_date, t.exit_date)}d` : '—'}</td>
                      <td className={`num right ${t.ret > 0 ? 'pos' : 'neg'}`}>{fmtPctSigned(t.ret)}</td>
                      <td><span className={`badge badge--reason-${t.reason}`}>{({ defense: 'Defense', rank_drop: 'Rank drop', open: 'Open' })[t.reason] || t.reason}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={cur} pageCount={pageCount} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
