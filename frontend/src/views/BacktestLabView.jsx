import { useEffect, useState } from 'react';
import { getConfig, runBacktest } from '../api';
import { useQuery } from '../hooks/useQuery';
import MetricTile from '../components/MetricTile';
import EquityChart from '../components/EquityChart';
import { Spinner, ErrorState } from '../components/States';
import { fmtPct, fmtPctSigned, fmtNum } from '../format';

const DEFAULTS = { lookback: 252, top_n: 10, target_vol: 0.10, max_weight: 0.10,
  target_port_vol: 0.15, dd_threshold: 0.12, de_gross: 0.5, cost_bps: 5,
  defended: true, start_date: '', end_date: '' };

export default function BacktestLabView() {
  const { data: cfg } = useQuery(getConfig, []);
  const [form, setForm] = useState(DEFAULTS);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (cfg) setForm((f) => ({ ...f, lookback: cfg.lookback, top_n: cfg.top_n,
      target_vol: cfg.target_vol, max_weight: cfg.max_weight,
      target_port_vol: cfg.target_port_vol, dd_threshold: cfg.dd_threshold,
      de_gross: cfg.de_gross, cost_bps: cfg.cost_bps }));
  }, [cfg]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError(null); setResult(null);
    try {
      const payload = { ...form };
      if (!payload.start_date) delete payload.start_date;
      if (!payload.end_date) delete payload.end_date;
      setResult(await runBacktest(payload));
    } catch (err) { setError(err.response?.data?.detail || err.message || 'Backtest failed'); }
    finally { setLoading(false); }
  };

  const m = result?.metrics;
  return (
    <div className="view">
      <div className="view-head">
        <h2>Backtest lab</h2>
        <p>Dial the risk knobs and rerun engine_3 over the full price history (correct warmup), then window the result. <strong>{form.defended ? 'Defended' : 'v0 (no defense)'}</strong>.</p>
      </div>

      <form className="card" onSubmit={submit} style={{ marginBottom: 16 }}>
        <div className="card-title">Parameters</div>
        <div className="form-grid">
          <label className="field"><span>lookback</span>
            <input type="number" value={form.lookback} onChange={(e) => set('lookback', +e.target.value)} /></label>
          <label className="field"><span>top_n</span>
            <input type="number" value={form.top_n} onChange={(e) => set('top_n', +e.target.value)} /></label>
          <label className="field"><span>target_vol</span>
            <input type="number" step="0.01" value={form.target_vol} onChange={(e) => set('target_vol', +e.target.value)} /></label>
          <label className="field"><span>max_weight</span>
            <input type="number" step="0.01" value={form.max_weight} onChange={(e) => set('max_weight', +e.target.value)} /></label>
          <label className="field"><span>target_port_vol</span>
            <input type="number" step="0.01" value={form.target_port_vol} onChange={(e) => set('target_port_vol', +e.target.value)} /></label>
          <label className="field"><span>dd_threshold</span>
            <input type="number" step="0.01" value={form.dd_threshold} onChange={(e) => set('dd_threshold', +e.target.value)} /></label>
          <label className="field"><span>de_gross</span>
            <input type="number" step="0.01" value={form.de_gross} onChange={(e) => set('de_gross', +e.target.value)} /></label>
          <label className="field"><span>cost_bps</span>
            <input type="number" step="0.5" value={form.cost_bps} onChange={(e) => set('cost_bps', +e.target.value)} /></label>
          <label className="field"><span>start date (opt)</span>
            <input type="date" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} /></label>
          <label className="field"><span>end date (opt)</span>
            <input type="date" value={form.end_date} onChange={(e) => set('end_date', e.target.value)} /></label>
          <label className="field-check" style={{ alignItems: 'flex-end' }}>
            <input type="checkbox" checked={form.defended} onChange={(e) => set('defended', e.target.checked)} />
            <span>Defended (vol-target + DD throttle)</span>
          </label>
        </div>
        <div style={{ marginTop: 14 }}>
          <button className="btn btn--primary" disabled={loading}>{loading ? 'Running…' : 'Run backtest'}</button>
        </div>
      </form>

      {error && <ErrorState message={error} />}
      {loading && <Spinner label="Backtesting over 5y of prices…" />}
      {m && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">Result {result.start_date || result.end_date ? `· ${result.start_date || '…'} → ${result.end_date || '…'}` : '· full history'} · {result.trades_count} entries</div>
            <div className="grid grid-tiles">
              <MetricTile label="Total return" value={fmtPctSigned(m.total_return)} tone={m.total_return >= 0 ? 'pos' : 'neg'} />
              <MetricTile label="Sharpe" value={fmtNum(m.sharpe)} />
              <MetricTile label="Max drawdown" value={fmtPct(m.max_drawdown)} tone="neg" />
              <MetricTile label="Ann return" value={fmtPctSigned(m.ann_return)} />
              <MetricTile label="Ann vol" value={fmtPct(m.ann_vol)} />
              <MetricTile label="PSR0" value={fmtNum(m.psr0)} sub="P(true Sharpe > 0)" />
              <MetricTile label="Bull Sharpe" value={fmtNum(m.bull_sharpe)} />
              <MetricTile label="Bear Sharpe" value={fmtNum(m.bear_sharpe)} tone={m.bear_sharpe < 0 ? 'neg' : ''} />
              <MetricTile label="Avg exposure" value={fmtPct(m.avg_exposure)} />
              <MetricTile label="Avg turnover" value={fmtNum(m.avg_turnover, 3)} />
            </div>
          </div>
          <div className="card chart-card">
            <div className="card-title">Equity vs benchmark</div>
            <EquityChart data={result.equity_curve} height={340} />
          </div>
        </>
      )}
    </div>
  );
}
