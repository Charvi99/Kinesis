// Green/red pill for the market regime (BULL when market >= 200d MA, BEAR below).
export default function RegimeBadge({ regime }) {
  const bull = regime === 'bull';
  return <span className={`badge ${bull ? 'badge--bull' : 'badge--bear'}`}>{bull ? 'Bull' : 'Bear'}</span>;
}
