import { useEffect, useState } from 'react';
import { checkHealth } from './api';
import DashboardView from './views/DashboardView';
import LabView from './views/LabView';
import EnginesView from './views/EnginesView';
import LearnView from './views/LearnView';
import SelectionView from './views/SelectionView';
import TradesView from './views/TradesView';

// Primary tabs = what you actually use. Selection/Trades are demoted (model-tagged):
// they show backtest-derived data until the live ledger lands, then they become live.
const PRIMARY = [
  { id: 'dashboard', label: 'Dashboard', el: DashboardView },
  { id: 'lab', label: 'Lab', el: LabView },
  { id: 'engines', label: 'Engines', el: EnginesView },
  { id: 'learn', label: 'Learn', el: LearnView },
];
const MODEL = [
  { id: 'selection', label: 'Selection', el: SelectionView },
  { id: 'trades', label: 'Trades', el: TradesView },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [health, setHealth] = useState(null);
  const [learnAnchor, setLearnAnchor] = useState(null);

  useEffect(() => {
    let on = true;
    checkHealth()
      .then((h) => on && setHealth(h))
      .catch(() => on && setHealth({ status: 'error' }));
    return () => { on = false; };
  }, []);

  // Any deep "?" chip dispatches 'kinesis:learn' -> jump to the Learn tab + anchor.
  useEffect(() => {
    const h = (e) => { setLearnAnchor(e.detail || null); setTab('learn'); };
    window.addEventListener('kinesis:learn', h);
    return () => window.removeEventListener('kinesis:learn', h);
  }, []);

  const Active = [...PRIMARY, ...MODEL].find((t) => t.id === tab).el;
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
          {PRIMARY.map((t) => (
            <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
          <span className="tab-sep" />
          {MODEL.map((t) => (
            <button key={t.id} className={`tab tab--model ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label} <span className="tab-tag">model</span>
            </button>
          ))}
        </nav>
      </header>
      <main className="app">
        {tab === 'learn' ? <LearnView anchor={learnAnchor} /> : <Active />}
      </main>
    </>
  );
}
