import { useEffect, useState } from 'react';
import { checkHealth } from './api';
import DashboardView from './views/DashboardView';
import SelectionView from './views/SelectionView';
import TradesView from './views/TradesView';
import BacktestLabView from './views/BacktestLabView';
import ConfigView from './views/ConfigView';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', el: DashboardView },
  { id: 'selection', label: 'Selection', el: SelectionView },
  { id: 'trades', label: 'Trades', el: TradesView },
  { id: 'backtest', label: 'Backtest lab', el: BacktestLabView },
  { id: 'config', label: 'Config', el: ConfigView },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let on = true;
    checkHealth()
      .then((h) => on && setHealth(h))
      .catch(() => on && setHealth({ status: 'error' }));
    return () => { on = false; };
  }, []);

  const Active = TABS.find((t) => t.id === tab).el;
  const ok = health?.status === 'ok';

  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <span className="brand-mark">Kinesis</span>
            <span className="brand-sub">momentum portfolio</span>
          </div>
          <div className="header-right">
            <span className="health">
              <span className={`health-dot ${ok ? 'ok' : health ? 'bad' : ''}`} />
              {ok ? 'API live' : health ? 'API offline' : 'connecting…'}
            </span>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="app"><Active /></main>
    </>
  );
}
