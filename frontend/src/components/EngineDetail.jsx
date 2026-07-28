import { useEffect, useRef, useState } from 'react';
import { runBacktest } from '../api';
import EquityChart from './EquityChart';
import MetricTile from './MetricTile';
import { Spinner, ErrorState } from './States';
import { tile } from '../metrics';
import { GROUPS, KNOB_BY_KEY } from '../knobs';
import { fmtNum, fmtPct, fmtPctSigned, fmtMoney } from '../format';

function snapshot(e) {
  return {
    lookback: +e.lookback, top_n: +e.top_n, target_vol: +e.target_vol, max_weight: +e.max_weight,
    regime_gate: !!e.regime_gate, defended: !!e.defended, target_port_vol: +e.target_port_vol,
    dd_threshold: +e.dd_threshold, de_gross: +e.de_gross, leverage_cap: +e.leverage_cap,
    cost_bps: +e.cost_bps, start_date: '', end_date: '',
  };
}

function configValue(k, raw) {
  const meta = KNOB_BY_KEY[k];
  if (meta?.type === 'bool') return raw ? 'on' : 'off';
  if (k === 'starting_cash') return fmtMoney(raw);
  return String(raw);
}

export default function EngineDetail({ engine, onClose, onAction }) {
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [leaving, setLeaving] = useState(false);
  const close = () => { if (leaving) return; setLeaving(true); setTimeout(onClose, 140); };
  const closeRef = useRef(close); closeRef.current = close;

  useEffect(() => {
    let on = true;
    setLoading(true); setError(null); setRes(null);
    runBacktest(snapshot(engine))
      .then((r) => on && setRes(r))
      .catch((e) => on && setError(e.response?.data?.detail || e.message || 'backtest failed'))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [engine]);

  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') closeRef.current(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  const m = res?.metrics || engine.metrics || {};

  return (
    <div className={`modal-overlay${leaving ? ' modal-overlay--leaving' : ''}`} onClick={close}>
      <div className={`modal${leaving ? ' modal--leaving' : ''}`} role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head row between">
          <div>
            <h3>{engine.name} {engine.is_deployed && <span className="badge badge--held" style={{ marginLeft: 8 }}>deployed</span>}</h3>
            {engine.description && <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>{engine.description}</p>}
          </div>
          <button className="modal-close" onClick={close} aria-label="Close">✕</button>
        </div>

        <div className="modal-body">
          {loading && !res ? <Spinner label="Backtesting this engine…" /> : error ? <ErrorState message={error} /> : (
            <>
              <div className="card-title">Risk &amp; return</div>
              <div className="grid grid-tiles">
                <MetricTile label="Sharpe" {...tile('sharpe', m.sharpe, fmtNum(m.sharpe))} />
                <MetricTile label="Max drawdown" {...tile('max_drawdown', m.max_drawdown, fmtPct(m.max_drawdown))} />
                <MetricTile label="Total return" {...tile('total_return', m.total_return, fmtPctSigned(m.total_return))} />
                <MetricTile label="Ann return" {...tile('ann_return', m.ann_return, fmtPctSigned(m.ann_return))} />
                <MetricTile label="Ann vol" value={fmtPct(m.ann_vol)} />
                <MetricTile label="PSR0" {...tile('psr0', m.psr0, fmtNum(m.psr0))} />
                <MetricTile label="Bull Sharpe" value={fmtNum(m.bull_sharpe)} />
                <MetricTile label="Bear Sharpe" value={fmtNum(m.bear_sharpe)} tone={m.bear_sharpe < 0 ? 'neg' : ''} />
              </div>
              {res && <div style={{ marginTop: 16 }}><EquityChart data={res.equity_curve} height={240} /></div>}
            </>
          )}

          <div className="card-title" style={{ marginTop: 20 }}>Config</div>
          <div className="engine-config-groups">
            {GROUPS.map((g) => (
              <div key={g.title} className="knob-group">
                <div className="knob-group-head"><span className="knob-group-title">{g.title}</span></div>
                <div className="grid grid-tiles">
                  {g.keys.map((k) => {
                    const meta = KNOB_BY_KEY[k];
                    return (
                      <div className="tile" key={k} title={meta?.help}>
                        <span className="tile-label">{meta?.label || k}</span>
                        <span className="tile-value" style={{ fontSize: 17 }}>{configValue(k, engine[k])}<span className="faint" style={{ fontSize: 12, marginLeft: 4 }}>{meta?.unit}</span></span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          {!engine.is_deployed && <button className="btn btn--primary" onClick={() => onAction('deploy')}>Deploy</button>}
          <button className="btn" onClick={() => onAction('edit')}>Edit</button>
          <button className="btn" onClick={() => onAction('clone')}>Clone</button>
          {!engine.is_deployed && <button className="btn btn--danger" onClick={() => onAction('delete')}>Delete</button>}
        </div>
      </div>
    </div>
  );
}
