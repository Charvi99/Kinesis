export const Spinner = ({ label = 'Loading…' }) => (
  <div className="state"><div className="spinner" /><div>{label}</div></div>
);

export const ErrorState = ({ message, onRetry }) => (
  <div className="state error">
    <div>⚠ {message || 'Something went wrong'}</div>
    {onRetry && <button className="btn" style={{ marginTop: 12 }} onClick={onRetry}>Retry</button>}
  </div>
);

export const EmptyState = ({ children }) => (
  <div className="state faint">{children || 'No data'}</div>
);
