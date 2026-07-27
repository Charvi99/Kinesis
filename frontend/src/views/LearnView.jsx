import { useEffect } from 'react';
import { LEARN } from '../content/learn';

// Plain-language explainers. `anchor` (a section id from a "?" chip) scrolls the
// matching section into view when the Learn tab opens.
export default function LearnView({ anchor }) {
  useEffect(() => {
    if (!anchor) return;
    const el = document.getElementById(`learn-${anchor}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [anchor]);

  return (
    <div className="view">
      <div className="view-head">
        <h2>Learn</h2>
        <p>Plain-language explainers for the concepts behind every knob and number.</p>
      </div>
      <div className="learn-grid">
        {LEARN.map((s) => (
          <section className="card learn-section" id={`learn-${s.id}`} key={s.id}>
            <h3>{s.title}</h3>
            {s.body.map((p, i) => <p key={i} className="learn-p">{p}</p>)}
            {s.tip && <p className="note">{s.tip}</p>}
          </section>
        ))}
      </div>
    </div>
  );
}
