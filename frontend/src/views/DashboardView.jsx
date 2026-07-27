import { getPortfolioState } from '../api';
import { useQuery } from '../hooks/useQuery';
import MetricTile from '../components/MetricTile';
import RegimeBadge from '../components/RegimeBadge';
import DefenseGauge from '../components/DefenseGauge';
import EquityChart from '../components/EquityChart';
import { Spinner, ErrorState } from '../components/States';
import { tile } from '../metrics';
import { fmtMoney, fmtPct, fmtPctSigned, fmtNum } from '../format';

export default function DashboardView() {
  const { data, error, loading, refetch } = useQuery(getPortfolioState, []);
  if (loading) return <Spinner label="Running the strategy backtest…" />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  if (!data) return null;
  const m = data.metrics;
  const tot = tile('total_return', m.total_return, fmtPctSigned(m.total_return));
  const shp = tile('sharpe', m.sharpe, fmtNum(m.sharpe));
  const mdd = tile('max_drawdown', m.max_drawdown, fmtPct(m.max_drawdown));
  const psr = tile('psr0', m.psr0, fmtNum(m.psr0));

  return (
    <div className="view">
      <div className="bento">
        <section className="card bento--hero">
          <div className="row between">
            <span className="tile-label">Equity</span>
            <div className="pillrow">
              <RegimeBadge regime={data.regime} />
              <span className="badge badge--neutral">Exposure {fmtPct(data.exposure, 0)}</span>
            </div>
          </div>
          <div className="tile--hero">{fmtMoney(data.equity)}</div>
          <div className={`hero-return ${tot.tone}`}>
            {tot.value}<span className="hero-return-sub">{tot.sub}</span>
          </div>
          <p className="tag-asof">Model track record · as-of {data.as_of} · backtested, not live P&amp;L</p>
        </section>

        <section className="card bento--defense">
          <div className="card-title">Defense</div>
          <DefenseGauge drawdown={data.defense.drawdown} ddThreshold={data.defense.dd_threshold} volTargetFactor={data.defense.vol_target_factor} />
        </section>

        <section className="card bento--chart">
          <div className="card-title">Equity vs benchmark</div>
          <EquityChart data={data.equity_curve} height={300} />
        </section>

        <section className="bento--sec">
          <div className="grid grid-tiles">
            <MetricTile label="Sharpe" {...shp} />
            <MetricTile label="Max drawdown" {...mdd} />
            <MetricTile label="Ann return / vol" value={fmtPctSigned(m.ann_return)} sub={`vol ${fmtPct(m.ann_vol, 1)}`} />
            <MetricTile label="PSR0" {...psr} />
            <MetricTile label="Bull / bear Sharpe" value={fmtNum(m.bull_sharpe)} sub={`bear ${fmtNum(m.bear_sharpe)}`} />
            <MetricTile label="Avg turnover" value={fmtNum(m.avg_turnover, 3)} sub={`exposure ${fmtPct(m.avg_exposure, 0)}`} />
          </div>
        </section>
      </div>
    </div>
  );
}
