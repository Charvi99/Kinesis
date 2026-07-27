import { getPortfolioState } from '../api';
import { useQuery } from '../hooks/useQuery';
import MetricTile from '../components/MetricTile';
import RegimeBadge from '../components/RegimeBadge';
import DefenseGauge from '../components/DefenseGauge';
import EquityChart from '../components/EquityChart';
import { Spinner, ErrorState } from '../components/States';
import { tile, verdict } from '../metrics';
import { fmtMoney, fmtPct, fmtPctSigned, fmtNum } from '../format';

export default function DashboardView() {
  const { data, error, loading, refetch } = useQuery(getPortfolioState, []);
  if (loading) return <Spinner label="Running the strategy backtest…" />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  if (!data) return null;
  const m = data.metrics;

  return (
    <div className="view">
      <div className="view-head row between">
        <div>
          <h2>Portfolio dashboard</h2>
          <p className="tag-asof">Model track record · as-of {data.as_of}</p>
        </div>
        <div className="pillrow">
          <span className="badge badge--model">modeled · not live</span>
          <RegimeBadge regime={data.regime} />
          <span className="badge badge--neutral">Exposure {fmtPct(data.exposure, 0)}</span>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="grid grid-tiles">
          <MetricTile label="Equity" value={fmtMoney(data.equity)} sub={`from ${fmtMoney(data.starting_cash)}`} />
          <MetricTile label="Total return" {...tile('total_return', m.total_return, fmtPctSigned(m.total_return))} />
          <MetricTile label="Sharpe" {...tile('sharpe', m.sharpe, fmtNum(m.sharpe))} />
          <MetricTile label="Max drawdown" {...tile('max_drawdown', m.max_drawdown, fmtPct(m.max_drawdown))} />
          <MetricTile label="Ann return" value={fmtPctSigned(m.ann_return)} sub={`${verdict('ann_return', m.ann_return).label} · vol ${fmtPct(m.ann_vol, 1)}`} tone={verdict('ann_return', m.ann_return).tone} />
          <MetricTile label="PSR0" {...tile('psr0', m.psr0, fmtNum(m.psr0))} />
          <MetricTile label="Bull Sharpe" value={fmtNum(m.bull_sharpe)} sub="bull regimes" />
          <MetricTile label="Bear Sharpe" value={fmtNum(m.bear_sharpe)} sub="bear regimes" tone={m.bear_sharpe < 0 ? 'neg' : ''} />
        </div>
        <p className="note">Track record is engine_3 <strong>backtested</strong> at the deployed config — there is no live ledger yet, so this is the strategy's modeled equity, not realized paper-trading P&amp;L. The badge above flags it; it flips to <em>live</em> when the ledger ships.</p>
      </div>

      <div className="grid grid-2">
        <div className="card chart-card">
          <div className="card-title">Equity vs benchmark</div>
          <EquityChart data={data.equity_curve} height={320} />
        </div>
        <div className="card">
          <div className="card-title">Defense status</div>
          <DefenseGauge drawdown={data.defense.drawdown} ddThreshold={data.defense.dd_threshold} volTargetFactor={data.defense.vol_target_factor} />
        </div>
      </div>
    </div>
  );
}
