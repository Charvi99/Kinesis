import { getTrades } from '../api';
import { useQuery } from '../hooks/useQuery';
import { Spinner, ErrorState, EmptyState } from '../components/States';
import { fmtMoney2, fmtPctSigned, fmtDate } from '../format';

function holdDays(entry, exit) {
  const d = Math.round((new Date(exit) - new Date(entry)) / 86400000);
  return d;
}

export default function TradesView() {
  const { data, error, loading, refetch } = useQuery(() => getTrades(200), []);
  return (
    <div className="view">
      <div className="view-head">
        <h2>Trades log</h2>
        <p className="tag-asof">Closed round-trips derived from the selection's weight history. Reason <em>defense</em> = a regime flatten; <em>rank_drop</em> = fell out of the top-N. Most recent first.</p>
      </div>
      <div className="card">
        {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={refetch} /> : !data?.length ? <EmptyState>No trades yet.</EmptyState> : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Symbol</th><th>Entry</th><th>Exit</th>
                  <th className="right">Entry px</th><th className="right">Exit px</th>
                  <th className="right">Hold</th><th className="right">Return</th><th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {data.map((t, i) => (
                  <tr key={`${t.symbol}-${t.exit_date}-${i}`}>
                    <td className="sym">{t.symbol}</td>
                    <td className="muted num">{fmtDate(t.entry_date)}</td>
                    <td className="muted num">{fmtDate(t.exit_date)}</td>
                    <td className="num right">{fmtMoney2(t.entry)}</td>
                    <td className="num right">{fmtMoney2(t.exit)}</td>
                    <td className="num right muted">{holdDays(t.entry_date, t.exit_date)}d</td>
                    <td className={`num right ${t.ret > 0 ? 'pos' : 'neg'}`}>{fmtPctSigned(t.ret)}</td>
                    <td><span className={`badge badge--reason-${t.reason}`}>{t.reason === 'defense' ? 'Defense' : 'Rank drop'}</span></td>
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
