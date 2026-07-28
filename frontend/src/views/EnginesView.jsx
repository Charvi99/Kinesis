import { useMemo, useState } from 'react';
import { createEngine, deleteEngine, deployEngine, disablePaperTrading, enablePaperTrading, getEngineCurves, listEngines, listPaperAccounts, updateEngine } from '../api';
import { useQuery } from '../hooks/useQuery';
import EngineForm from '../components/EngineForm';
import EngineDetail from '../components/EngineDetail';
import EquityChart from '../components/EquityChart';
import Skeleton from '../components/Skeleton';
import { ErrorState, EmptyState, Spinner } from '../components/States';
import { CHART } from '../chartTheme';
import { fmtNum, fmtPct, fmtPctSigned, fmtDate } from '../format';

const PALETTE = ['#0d9488', '#7c3aed', '#2563eb', '#d97706', '#db2777', '#0ea5e9', '#65a30d', '#9333ea'];
// distinct dash patterns so engines differ by line STYLE too, not color alone (colorblind)
const DASHES = [undefined, '6 3', '2 4', '8 3 2 3', '5 2', '1 3'];

function summary(e) {
  return `top${e.top_n} · ${e.lookback}d · pvol ${Number(e.target_port_vol).toFixed(2)}${e.defended ? '' : ' · no-def'}`;
}
function MetricMini({ label, value, tone }) {
  return (<div className="engine-metric"><span className="tile-label">{label}</span><span className={`engine-metric-v ${tone || ''}`}>{value}</span></div>);
}

export default function EnginesView() {
  const { data, error, loading, refetch } = useQuery(listEngines, []);
  const { data: curves, loading: curvesLoading } = useQuery(getEngineCurves, []);
  const { data: accts, refetch: refetchAccts } = useQuery(listPaperAccounts, []);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actErr, setActErr] = useState(null);

  const act = async (fn) => { setBusy(true); setActErr(null); try { await fn(); await refetch(); await refetchAccts(); } catch (e) { setActErr(e.response?.data?.detail || e.message || 'action failed'); } finally { setBusy(false); } };
  const onSave = (payload) => act(async () => { if (editing.mode === 'edit') await updateEngine(editing.initial.id, payload); else await createEngine(payload); setEditing(null); });
  const onDetailAction = (kind) => { const e = detail; setDetail(null); if (kind === 'edit') setEditing({ mode: 'edit', initial: e }); else if (kind === 'clone') setEditing({ mode: 'clone', initial: { ...e, name: `${e.name}-copy` } }); else if (kind === 'deploy') act(() => deployEngine(e.id)); else if (kind === 'delete') { if (window.confirm(`Delete engine “${e.name}”?`)) act(() => deleteEngine(e.id)); } };

  // stable color per engine (by list position) — ties card accent to chart line
  const colorByName = useMemo(() => { const m = new Map(); (data || []).forEach((e, i) => m.set(e.name, PALETTE[i % PALETTE.length])); return m; }, [data]);

  // live paper accounts keyed by engine_id, so each card can show + toggle its paper-trade state.
  const acctByEng = useMemo(() => { const m = new Map(); (accts || []).forEach((a) => m.set(a.engine_id, a)); return m; }, [accts]);

  const onPaper = (e) => {
    const acct = acctByEng.get(e.id);
    if (acct && acct.is_live) { act(async () => { await disablePaperTrading(e.id); }); return; }   // live -> pause (positions frozen)
    if (!acct && !window.confirm(`Paper-trade engine “${e.name}”? This bridges it from its backtest and books the first live cycle.`)) return;
    act(async () => { await enablePaperTrading(e.id); });                                          // none -> enable, or paused -> resume
  };

  const merged = useMemo(() => {
    if (!curves?.length) return [];
    const byDate = new Map();
    curves.forEach((c) => c.curve.forEach((p) => { const row = byDate.get(p.date) || { date: p.date }; row[c.is_benchmark ? '_benchmark' : c.name] = p.equity; byDate.set(p.date, row); }));
    return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
  }, [curves]);
  const series = useMemo(() => {
    if (!curves) return [];
    let ei = 0;
    return curves.map((c) => c.is_benchmark
      ? { key: '_benchmark', name: 'Benchmark (S&P 500 ≈ eq-wt market)', color: CHART.bench, width: 1.5, dash: '5 3' }
      : { key: c.name, name: c.name + (c.is_deployed ? ' · deployed' : ''),
          color: colorByName.get(c.name) || CHART.equity, width: c.is_deployed ? 2.5 : 1.8,
          dash: DASHES[(ei++) % DASHES.length] });
  }, [curves, colorByName]);

  return (
    <div className="view">
      <div className="view-head row between">
        <div><h2>Engines</h2><p className="tag-asof">Named engine_3 configs. The <strong>deployed</strong> one drives the Dashboard, Selection &amp; Trades. Click a card for details.</p></div>
        <button className="btn btn--primary" onClick={() => setEditing({ mode: 'new', initial: null })} disabled={busy}>+ New engine</button>
      </div>

      {curvesLoading ? (<div className="card" style={{ marginBottom: 16 }}><Skeleton height={300} /></div>) : merged.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title">Equity comparison · all engines vs benchmark</div>
          <EquityChart data={merged} series={series} height={300} />
          <p className="note">Each line is one engine's backtested equity from $100k. Card colors match the lines; the dashed gray line is the market benchmark. Curves share a common date axis, so the hover tooltip shows every series.</p>
        </div>
      )}

      {actErr && <ErrorState message={actErr} />}
      {editing && (<EngineForm initial={editing.mode === 'new' ? null : editing.initial} submitLabel={editing.mode === 'edit' ? 'Save changes' : 'Create engine'} onSave={onSave} onCancel={() => setEditing(null)} />)}

      {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={refetch} /> : !data?.length ? <EmptyState>No engines yet.</EmptyState> : (
        <div className="engine-grid">
          {data.map((e) => {
            const m = e.metrics || {};
            const color = colorByName.get(e.name) || '#94a3b8';
            const acct = acctByEng.get(e.id);
            return (
              <div key={e.id} className={`card engine-card${e.is_deployed ? ' engine-card--deployed' : ''}`}
                   onClick={() => setDetail(e)} role="button" tabIndex={0} onKeyDown={(ev) => { if (ev.key === 'Enter') setDetail(e); }}
                   style={{ borderLeftColor: color, ...(e.is_deployed ? { boxShadow: `0 0 0 1px ${color}, var(--shadow-md)` } : {}) }}>
                <div className="row between engine-card-head">
                  <span className="row" style={{ gap: 8, alignItems: 'center' }}>
                    <span className="engine-dot" style={{ background: color }} />
                    <strong className="engine-name">{e.name}</strong>
                  </span>
                  {e.is_deployed && <span className="badge badge--held">deployed</span>}
                  {acct?.is_live && <span className="badge badge--live"><span className="live-dot" /> live</span>}
                  {acct && !acct.is_live && <span className="badge badge--neutral">paused</span>}
                </div>
                {e.description && <p className="engine-desc">{e.description}</p>}
                <div className="engine-metrics">
                  <MetricMini label="Sharpe" value={fmtNum(m.sharpe)} tone="pos" />
                  <MetricMini label="Max DD" value={fmtPct(m.max_drawdown)} tone="neg" />
                  <MetricMini label="Total" value={fmtPctSigned(m.total_return)} />
                </div>
                <p className="engine-config muted num">{summary(e)}</p>
                <p className="faint" style={{ fontSize: 11 }}>updated {fmtDate((e.updated_at || '').slice(0, 10))}</p>
                <div className="engine-actions" onClick={(ev) => ev.stopPropagation()}>
                  {!e.is_deployed && <button className="btn btn--primary" disabled={busy} onClick={() => act(() => deployEngine(e.id))}>Deploy</button>}
                  <button className={`btn ${acct && acct.is_live ? '' : 'btn--primary'}`} disabled={busy} onClick={() => onPaper(e)}>{!acct ? 'Paper-trade' : acct.is_live ? 'Pause' : 'Resume'}</button>
                  <button className="btn" disabled={busy} onClick={() => setEditing({ mode: 'edit', initial: e })}>Edit</button>
                  <button className="btn" disabled={busy} onClick={() => setEditing({ mode: 'clone', initial: { ...e, name: `${e.name}-copy` } })}>Clone</button>
                  {!e.is_deployed && <button className="btn btn--danger" disabled={busy} onClick={() => window.confirm(`Delete engine “${e.name}”?`) && act(() => deleteEngine(e.id))}>Delete</button>}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {detail && <EngineDetail engine={detail} onClose={() => setDetail(null)} onAction={onDetailAction} />}
    </div>
  );
}
