import { getPortfolioState } from '../api';
import { useQuery } from '../hooks/useQuery';
import MetricTile from '../components/MetricTile';
import RegimeBadge from '../components/RegimeBadge';
import DefenseGauge from '../components/DefenseGauge';
import EquityChart from '../components/EquityChart';
import { Spinner, ErrorState } from '../components/States';
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
          <RegimeBadge regime={data.regime} />
          <span className="badge badge--neutral">Exposure {fmtPct(data.exposure, 0)}</span>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="grid grid-tiles">
          <MetricTile label="Equity" value={fmtMoney(data.equity)} sub={`from ${fmtMoney(data.starting_cash)}`} />
          <MetricTile label="Total return" value={fmtPctSigned(m.total_return)} tone={m.total_return >= 0 ? 'pos' : 'neg'} />
          <MetricTile label="Sharpe" value={fmtNum(m.sharpe)} sub="vs SPY ~0.69" />
          <MetricTile label="Max drawdown" value={fmtPct(m.max_drawdown)} tone="neg" sub="vs SPY ~−25%" />
          <MetricTile label="Ann return / vol" value={`${fmtPct(m.ann_return, 1)}`} sub={`vol ${fmtPct(m.ann_vol, 1)}`} />
          <MetricTile label="PSR0" value={fmtNum(m.psr0)} sub="P(edge > 0)" />
          <MetricTile label="Bull / bear Sharpe" value={fmtNum(m.bull_sharpe)} sub={`bear ${fmtNum(m.bear_sharpe)}`} />
          <MetricTile label="Avg turnover" value={fmtNum(m.avg_turnover, 3)} sub={`exposure ${fmtPct(m.avg_exposure, 0)}`} />
        </div>
        <p className="note">Track record is engine_3 <strong>backtested</strong> at production config — there is no live ledger yet, so this is the strategy's modeled equity, not realized paper-trading P&amp;L. (See FRONTEND_DESIGN §4.)</p>
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
