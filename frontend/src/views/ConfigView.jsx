import { getConfig } from '../api';
import { useQuery } from '../hooks/useQuery';
import { Spinner, ErrorState } from '../components/States';

const FIELDS = [
  { key: 'lookback', label: 'Momentum lookback', unit: 'days' },
  { key: 'top_n', label: 'Hold top-N', unit: 'names' },
  { key: 'target_vol', label: 'Per-name vol target', unit: '×' },
  { key: 'max_weight', label: 'Single-name cap', unit: '×' },
  { key: 'target_port_vol', label: 'Portfolio vol target', unit: '×' },
  { key: 'dd_threshold', label: 'Drawdown throttle', unit: '×' },
  { key: 'de_gross', label: 'Throttle de-gross', unit: '×' },
  { key: 'cost_bps', label: 'Round-trip cost', unit: 'bps' },
];

export default function ConfigView() {
  const { data, error, loading, refetch } = useQuery(getConfig, []);
  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  return (
    <div className="view">
      <div className="view-head">
        <h2>Engine configuration</h2>
        <p>Read-only. Edit <code>backend/app/services/momentum/defaults.py</code> and redeploy to change — knobs are not driven from the UI.</p>
      </div>
      <div className="card">
        <div className="card-title">Selection + defense knobs</div>
        <div className="grid grid-tiles">
          {FIELDS.map((f) => (
            <div className="tile" key={f.key}>
              <span className="tile-label">{f.label}</span>
              <span className="tile-value">{String(data[f.key])}<span className="faint" style={{ fontSize: 13, marginLeft: 4 }}>{f.unit}</span></span>
            </div>
          ))}
        </div>
        <div className="note">
          <strong>regime_gate</strong> = {String(data.regime_gate)} — go flat when the market &lt; its 200-day MA.
          &nbsp;<strong>leverage_cap</strong> = {data.leverage_cap} — the vol-target never scales gross above this.
        </div>
      </div>
    </div>
  );
}
