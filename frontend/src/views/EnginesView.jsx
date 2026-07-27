import { useState } from 'react';
import { createEngine, deleteEngine, deployEngine, listEngines, updateEngine } from '../api';
import { useQuery } from '../hooks/useQuery';
import EngineForm from '../components/EngineForm';
import { ErrorState, EmptyState, Spinner } from '../components/States';
import { CONFIG_KEYS, KNOB_BY_KEY } from '../knobs';
import { fmtDate } from '../format';

function summary(e) {
  return `top${e.top_n} · ${e.lookback}d · pvol ${Number(e.target_port_vol).toFixed(2)}${e.defended ? '' : ' · no-def'}`;
}

export default function EnginesView() {
  const { data, error, loading, refetch } = useQuery(listEngines, []);
  const [editing, setEditing] = useState(null);  // {mode, initial}
  const [busy, setBusy] = useState(false);
  const [actErr, setActErr] = useState(null);

  const deployed = data?.find((e) => e.is_deployed);

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
        <button className="btn btn--primary" onClick={() => setEditing({ mode: 'new', initial: null })} disabled={busy}>
          + New engine
        </button>
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
        <>
          {deployed && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-title">
                Deployed · {deployed.name}
                <span className="badge badge--held" style={{ marginLeft: 8 }}>deployed</span>
              </div>
              <div className="grid grid-tiles">
                {CONFIG_KEYS.map((k) => {
                  const meta = KNOB_BY_KEY[k];
                  return (
                    <div className="tile" key={k} title={meta?.help}>
                      <span className="tile-label">{meta?.label || k}</span>
                      <span className="tile-value">{String(deployed[k])}<span className="faint" style={{ fontSize: 13, marginLeft: 4 }}>{meta?.unit}</span></span>
                    </div>
                  );
                })}
              </div>
              {deployed.description && <p className="note">{deployed.description}</p>}
            </div>
          )}

          <div className="card">
            <div className="card-title">All engines</div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Name</th><th>Config</th><th>Updated</th><th className="right">Actions</th></tr>
                </thead>
                <tbody>
                  {data.map((e) => (
                    <tr key={e.id} className={e.is_deployed ? 'held' : ''}>
                      <td>
                        <strong>{e.name}</strong>
                        {e.is_deployed && <span className="badge badge--held" style={{ marginLeft: 8 }}>deployed</span>}
                        {e.description && <div className="faint" style={{ fontSize: 12 }}>{e.description}</div>}
                      </td>
                      <td className="muted">{summary(e)}</td>
                      <td className="muted num">{fmtDate((e.updated_at || '').slice(0, 10))}</td>
                      <td className="right">
                        {!e.is_deployed && (
                          <button className="btn" disabled={busy} onClick={() => act(() => deployEngine(e.id))}>Deploy</button>
                        )}{' '}
                        <button className="btn" disabled={busy} onClick={() => setEditing({ mode: 'edit', initial: e })}>Edit</button>{' '}
                        <button className="btn" disabled={busy} onClick={() => setEditing({ mode: 'clone', initial: { ...e, name: `${e.name}-copy` } })}>Clone</button>{' '}
                        {!e.is_deployed && (
                          <button className="btn" disabled={busy} onClick={() => window.confirm(`Delete engine “${e.name}”?`) && act(() => deleteEngine(e.id))}>Delete</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="note">Clone = “create from” an existing engine. Deploying busts the Dashboard cache so it follows immediately.</p>
          </div>
        </>
      )}
    </div>
  );
}
