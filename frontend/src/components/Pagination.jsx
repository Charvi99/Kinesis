export default function Pagination({ page, pageCount, onChange }) {
  if (pageCount <= 1) return null;
  return (
    <div className="pagination">
      <button className="btn" disabled={page <= 1} onClick={() => onChange(page - 1)}>‹ Prev</button>
      <span className="muted num">Page {page} of {pageCount}</span>
      <button className="btn" disabled={page >= pageCount} onClick={() => onChange(page + 1)}>Next ›</button>
    </div>
  );
}
