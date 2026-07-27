import { useState } from 'react';
import { createEngine, deleteEngine, deployEngine, listEngines, updateEngine } from '../api';
import { useQuery } from '../hooks/useQuery';
import EngineForm from '../components/EngineForm';
import { ErrorState, EmptyState, Spinner } from '../components/States';
import { fmtNum, fmtPct, fmtPctSigned, fmtDate } from '../format';

function summary(e) {
  return `top${e.top_n} · ${e.lookback}d · pvol ${Number(e.target_port_vol).toFixed(2)}${e.defended ? '' : ' · no-def'}`;
}

function MetricMini({ label, value, tone }) {
  return (
    <div className="engine-metric">
      <span className="tile-label">{label}</span>
      <span className={`engine-metric-v ${tone || ''}`}>{value}</span>
    </div>
  );
}

export default function EnginesView() {
  const { data, error, loading, refetch } = useQuery(listEngines, []);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actErr, setActErr] = useState(null);

  const act = async (fn) => {
    setBusy(true); setActErr(null);
    try { await fn(); await refetch(); }
    catch (e) { setActErr(e.response?.data?.detail || e.message || 'action failed'); }
    finally { setBusy(false); }
  };
  const onSave = (payload) => act(async () => {
    if (editing.mode === 'edit') await updateEngine(editing.initial.id, payload);
    else await createEngine(payload);
    setEditing(null);
  });

  return (
    <div className="view">
      <div className="view-head row between">
        <div>
          <h2>Engines</h2>
          <p className="tag-asof">Named engine_3 configs. The <strong>deployed</strong> one drives the Dashboard, Selection &amp; Trades.</p>
        </div>
        <button className="btn btn--primary" onClick={() => setEditing({ mode: 'new', initial: null })} disabled={busy}>+ New engine</button>
      </div>

      {actErr && <ErrorState message={actErr} />}
      {editing && (
        <EngineForm
          initial={editing.mode === 'new' ? null : editing.initial}
          submitLabel={editing.mode === 'edit' ? 'Save changes' : 'Create engine'}
          onSave={onSave}
          onCancel={() => setEditing(null)}
        />
      )}

      {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={refetch} /> : !data?.length ? <EmptyState>No engines yet.</EmptyState> : (
        <div className="engine-grid">
          {data.map((e) => {
            const m = e.metrics || {};
            return (
              <div key={e.id} className={`card engine-card${e.is_deployed ? ' engine-card--deployed' : ''}`}>
                <div className="row between engine-card-head">
                  <strong className="engine-name">{e.name}</strong>
                  {e.is_deployed && <span className="badge badge--held">deployed</span>}
                </div>
                {e.description && <p className="engine-desc">{e.description}</p>}
                <div className="engine-metrics">
                  <MetricMini label="Sharpe" value={fmtNum(m.sharpe)} tone="pos" />
                  <MetricMini label="Max DD" value={fmtPct(m.max_drawdown)} tone="neg" />
                  <MetricMini label="Total" value={fmtPctSigned(m.total_return)} />
                </div>
                <p className="engine-config muted num">{summary(e)}</p>
                <p className="faint" style={{ fontSize: 11 }}>updated {fmtDate((e.updated_at || '').slice(0, 10))}</p>
                <div className="engine-actions">
                  {!e.is_deployed && <button className="btn btn--primary" disabled={busy} onClick={() => act(() => deployEngine(e.id))}>Deploy</button>}
                  <button className="btn" disabled={busy} onClick={() => setEditing({ mode: 'edit', initial: e })}>Edit</button>
                  <button className="btn" disabled={busy} onClick={() => setEditing({ mode: 'clone', initial: { ...e, name: `${e.name}-copy` } })}>Clone</button>
                  {!e.is_deployed && <button className="btn btn--danger" disabled={busy} onClick={() => window.confirm(`Delete engine “${e.name}”?`) && act(() => deleteEngine(e.id))}>Delete</button>}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="note">Clone = “create from” an existing engine. Deploying busts the Dashboard cache so it follows immediately. Metrics are cached on save; <code>POST /engines/&#123;id&#125;/refresh</code> recomputes after a data refresh.</p>
    </div>
  );
}
