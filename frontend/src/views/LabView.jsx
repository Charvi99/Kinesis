import { useEffect, useMemo, useState } from 'react';
import { getConfig, listEngines, runBacktest, runCompare, runSweep } from '../api';
import { useQuery } from '../hooks/useQuery';
import MetricTile from '../components/MetricTile';
import EquityChart from '../components/EquityChart';
import SweepChart from '../components/SweepChart';
import CompareScorecard from '../components/CompareScorecard';
import { ErrorState, Spinner } from '../components/States';
import { KNOBS, KNOB_BY_KEY, SWEEPABLE } from '../knobs';
import { fmtNum, fmtPct, fmtPctSigned } from '../format';

const MODES = [
  { id: 'single', label: 'Single run' },
  { id: 'sweep', label: 'Sweep a knob' },
  { id: 'compare', label: 'Compare' },
];

// Fields a backtest accepts (everything but starting_cash).
const BT_KNOBS = KNOBS.filter((k) => k.key !== 'starting_cash');

// Build a backtest payload from any engine-like / config-like object.
function snapshot(src) {
  return {
    lookback: +src.lookback, top_n: +src.top_n, target_vol: +src.target_vol,
    max_weight: +src.max_weight, regime_gate: !!src.regime_gate, defended: !!src.defended,
    target_port_vol: +src.target_port_vol, dd_threshold: +src.dd_threshold,
    de_gross: +src.de_gross, leverage_cap: +src.leverage_cap, cost_bps: +src.cost_bps,
    start_date: '', end_date: '',
  };
}

function linspace(from, to, count, asInt) {
  const n = Math.max(2, Math.min(12, Math.round(count)));
  const step = (to - from) / (n - 1);
  const vals = Array.from({ length: n }, (_, i) => from + step * i);
  return asInt ? Array.from(new Set(vals.map((v) => Math.round(v)))) : vals.map((v) => +v.toFixed(4));
}

export default function LabView() {
  const [mode, setMode] = useState('single');
  const { data: engines } = useQuery(listEngines, []);
  const [baseId, setBaseId] = useState(null);   // null = deployed

  return (
    <div className="view">
      <div className="view-head">
        <h2>Lab</h2>
        <p>Explore how the knobs move the result. Single = one run; Sweep = one knob across a range; Compare = two engines side by side.</p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {MODES.map((m) => (
          <button key={m.id} className={`btn ${mode === m.id ? 'btn--primary' : ''}`} onClick={() => setMode(m.id)}>{m.label}</button>
        ))}
      </div>

      {mode === 'single' && <SingleRun engines={engines} baseId={baseId} setBaseId={setBaseId} />}
      {mode === 'sweep' && <SweepRun engines={engines} baseId={baseId} setBaseId={setBaseId} />}
      {mode === 'compare' && <CompareRun engines={engines} />}
    </div>
  );
}

// ── shared base-engine selector ──────────────────────────────────────────────
function BaseSelect({ engines, baseId, setBaseId }) {
  return (
    <label className="field" style={{ maxWidth: 280 }}>
      <span>Base engine</span>
      <select value={baseId ?? ''} onChange={(e) => setBaseId(e.target.value ? +e.target.value : null)}>
        <option value="">Deployed (prod)</option>
        {(engines || []).filter((e) => !e.is_deployed).map((e) => (
          <option key={e.id} value={e.id}>{e.name}</option>
        ))}
      </select>
    </label>
  );
}

// ── Single run ───────────────────────────────────────────────────────────────
function SingleRun({ engines, baseId, setBaseId }) {
  const { data: cfg } = useQuery(getConfig, []);
  const base = baseId ? engines?.find((e) => e.id === baseId) : cfg;
  const [form, setForm] = useState(null);
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => { if (base) setForm(snapshot(base)); }, [base]);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const run = async (e) => {
    e.preventDefault();
    setLoading(true); setError(null); setRes(null);
    const payload = { ...form };
    if (!payload.start_date) delete payload.start_date;
    if (!payload.end_date) delete payload.end_date;
    try { setRes(await runBacktest(payload)); }
    catch (err) { setError(err.response?.data?.detail || err.message || 'backtest failed'); }
    finally { setLoading(false); }
  };

  if (!form) return <Spinner />;
  const m = res?.metrics;
  return (
    <form className="card" onSubmit={run} style={{ marginBottom: 16 }}>
      <div className="card-title">Single run</div>
      <div style={{ marginBottom: 12 }}><BaseSelect engines={engines} baseId={baseId} setBaseId={setBaseId} /></div>
      <div className="form-grid">
        {BT_KNOBS.map((k) => (
          <label className="field" key={k.key} title={k.help}>
            <span>{k.label}{k.unit ? ` (${k.unit})` : ''} <span className="faint">ⓘ</span></span>
            <input type="number" value={form[k.key]} min={k.min} max={k.max} step={k.step} onChange={(e) => set(k.key, e.target.value)} />
          </label>
        ))}
        <label className="field"><span>Start date (opt)</span>
          <input type="date" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} /></label>
        <label className="field"><span>End date (opt)</span>
          <input type="date" value={form.end_date} onChange={(e) => set('end_date', e.target.value)} /></label>
      </div>
      <div style={{ marginTop: 12 }}>
        <button className="btn btn--primary" disabled={loading}>{loading ? 'Running…' : 'Run backtest'}</button>
      </div>

      {error && <div style={{ marginTop: 12 }}><ErrorState message={error} /></div>}
      {loading && <Spinner label="Backtesting over 5y of prices…" />}
      {m && (
        <>
          <div className="grid grid-tiles" style={{ marginTop: 16 }}>
            <MetricTile label="Total return" value={fmtPctSigned(m.total_return)} tone={m.total_return >= 0 ? 'pos' : 'neg'} />
            <MetricTile label="Sharpe" value={fmtNum(m.sharpe)} />
            <MetricTile label="Max drawdown" value={fmtPct(m.max_drawdown)} tone="neg" />
            <MetricTile label="Ann return" value={fmtPctSigned(m.ann_return)} />
            <MetricTile label="Ann vol" value={fmtPct(m.ann_vol)} />
            <MetricTile label="PSR0" value={fmtNum(m.psr0)} sub="P(edge>0)" />
            <MetricTile label="Bull Sharpe" value={fmtNum(m.bull_sharpe)} />
            <MetricTile label="Bear Sharpe" value={fmtNum(m.bear_sharpe)} tone={m.bear_sharpe < 0 ? 'neg' : ''} />
          </div>
          <div style={{ marginTop: 16 }}><EquityChart data={res.equity_curve} height={320} /></div>
        </>
      )}
    </form>
  );
}

// ── Sweep ────────────────────────────────────────────────────────────────────
function SweepRun({ engines, baseId, setBaseId }) {
  const [knobKey, setKnobKey] = useState('target_port_vol');
  const [from, setFrom] = useState(0.12);
  const [to, setTo] = useState(0.30);
  const [count, setCount] = useState(7);
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const meta = KNOB_BY_KEY[knobKey];
  useEffect(() => {
    if (!meta) return;
    setFrom(meta.min); setTo(Math.min(meta.max, meta.min * 3));
  }, [knobKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (e) => {
    e.preventDefault();
    setLoading(true); setError(null); setRes(null);
    const values = linspace(+from, +to, +count, meta.type === 'int');
    try {
      setRes(await runSweep({ engine_id: baseId ?? undefined, knob: knobKey, values }));
    } catch (err) { setError(err.response?.data?.detail || err.message || 'sweep failed'); }
    finally { setLoading(false); }
  };

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">Sweep a knob</div>
      <p className="note">Hold everything else fixed; vary one knob and watch Sharpe (green) and max drawdown (red) move. <strong>This is how you learn what a knob does.</strong></p>
      <form onSubmit={run}>
        <div style={{ marginBottom: 12 }}><BaseSelect engines={engines} baseId={baseId} setBaseId={setBaseId} /></div>
        <div className="form-grid">
          <label className="field"><span>Knob</span>
            <select value={knobKey} onChange={(e) => setKnobKey(e.target.value)}>
              {SWEEPABLE.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}
            </select></label>
          <label className="field" title={meta?.help}><span>From <span className="faint">ⓘ</span></span>
            <input type="number" value={from} step={meta?.step || 0.01} onChange={(e) => setFrom(e.target.value)} /></label>
          <label className="field" title={meta?.help}><span>To <span className="faint">ⓘ</span></span>
            <input type="number" value={to} step={meta?.step || 0.01} onChange={(e) => setTo(e.target.value)} /></label>
          <label className="field"><span>Points (≤12)</span>
            <input type="number" value={count} min={2} max={12} onChange={(e) => setCount(e.target.value)} /></label>
        </div>
        {meta && <p className="faint" style={{ fontSize: 12, marginTop: 8 }}>{meta.help}</p>}
        <div style={{ marginTop: 12 }}>
          <button className="btn btn--primary" disabled={loading}>{loading ? 'Sweeping…' : 'Run sweep'}</button>
        </div>
      </form>

      {error && <div style={{ marginTop: 12 }}><ErrorState message={error} /></div>}
      {loading && <Spinner label="Running a backtest per value…" />}
      {res?.points?.length > 0 && (
        <>
          <div style={{ marginTop: 16 }}><SweepChart points={res.points} knobLabel={`${meta?.label} (${res.knob})`} /></div>
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="table">
              <thead><tr><th>{meta?.label}</th><th className="right">Sharpe</th><th className="right">Max DD</th><th className="right">Total ret</th><th className="right">Ann vol</th></tr></thead>
              <tbody>
                {res.points.map((p, i) => {
                  const mm = p.metrics;
                  return (
                    <tr key={i}>
                      <td className="num">{p.value}</td>
                      <td className="num right">{fmtNum(mm.sharpe)}</td>
                      <td className="num right neg">{fmtPct(mm.max_drawdown)}</td>
                      <td className={`num right ${mm.total_return >= 0 ? 'pos' : 'neg'}`}>{fmtPctSigned(mm.total_return)}</td>
                      <td className="num right">{fmtPct(mm.ann_vol)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ── Compare ──────────────────────────────────────────────────────────────────
function CompareRun({ engines }) {
  const list = engines || [];
  const deployed = list.find((e) => e.is_deployed);
  const [aId, setAId] = useState(null);
  const [bId, setBId] = useState(null);
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async (e) => {
    e.preventDefault();
    setLoading(true); setError(null); setRes(null);
    try { setRes(await runCompare({ a_engine_id: aId ?? undefined, b_engine_id: bId ?? undefined })); }
    catch (err) { setError(err.response?.data?.detail || err.message || 'compare failed'); }
    finally { setLoading(false); }
  };

  // Merge the two equity curves (+ SPY) into one dataset for the overlay.
  const merged = useMemo(() => {
    if (!res) return [];
    const a = Object.fromEntries(res.a.equity_curve.map((p) => [p.date, p.equity]));
    const b = Object.fromEntries(res.b.equity_curve.map((p) => [p.date, p.equity]));
    const spy = Object.fromEntries(res.a.equity_curve.map((p) => [p.date, p.spy]));
    return Object.keys(a).sort().map((d) => ({ date: d, a: a[d] ?? null, b: b[d] ?? null, spy: spy[d] ?? null }));
  }, [res]);

  const series = res && [
    { key: 'a', name: res.a.name, color: '#0d9488', width: 2 },
    { key: 'b', name: res.b.name, color: '#7c3aed', width: 2 },
    { key: 'spy', name: 'SPY', color: '#94a3b8', width: 1.5 },
  ];

  return (
    <div className="card">
      <div className="card-title">Compare two engines</div>
      <form onSubmit={run}>
        <div className="form-grid">
          <label className="field"><span>Engine A</span>
            <select value={aId ?? ''} onChange={(e) => setAId(e.target.value ? +e.target.value : null)}>
              <option value="">{deployed ? `${deployed.name} (deployed)` : 'Deployed'}</option>
              {list.map((e) => <option key={e.id} value={e.id}>{e.name}{e.is_deployed ? ' · deployed' : ''}</option>)}
            </select></label>
          <label className="field"><span>Engine B</span>
            <select value={bId ?? ''} onChange={(e) => setBId(e.target.value ? +e.target.value : null)}>
              <option value="">{deployed ? `${deployed.name} (deployed)` : 'Deployed'}</option>
              {list.map((e) => <option key={e.id} value={e.id}>{e.name}{e.is_deployed ? ' · deployed' : ''}</option>)}
            </select></label>
        </div>
        <div style={{ marginTop: 12 }}>
          <button className="btn btn--primary" disabled={loading}>{loading ? 'Comparing…' : 'Run compare'}</button>
        </div>
      </form>

      {error && <div style={{ marginTop: 12 }}><ErrorState message={error} /></div>}
      {loading && <Spinner label="Running both backtests…" />}
      {res && (
        <>
          <div style={{ marginTop: 16 }}><CompareScorecard a={res.a} b={res.b} delta={res.delta} /></div>
          <div className="card-title" style={{ marginTop: 16 }}>Equity overlay</div>
          <EquityChart data={merged} series={series} height={340} />
        </>
      )}
    </div>
  );
}
