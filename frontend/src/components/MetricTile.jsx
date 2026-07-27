export default function MetricTile({ label, value, sub, tone }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className={`tile-value ${tone || ''}`}>{value}</span>
      {sub != null && <span className="tile-sub">{sub}</span>}
    </div>
  );
}
