export default function Skeleton({ height = 200, className = '', style }) {
  return <div className={`skeleton-block ${className}`} style={{ height, ...style }} aria-hidden="true" />;
}
