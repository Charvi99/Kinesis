// Single source of truth for engine_3's knobs — label, unit, range, and a
// plain-language hint (with DIRECTION) so every surface (Engines form, Lab tooltips,
// the sweep picker) describes a knob the same way. One place answers "what does this
// knob do?". Ranges mirror the backend Field constraints (schemas.py).

export const KNOBS = [
  {
    key: 'lookback', label: 'Momentum lookback', unit: 'days', type: 'int',
    min: 10, max: 504, step: 1, sweepable: true,
    help: 'How many days of history the momentum rank uses. Longer = smoother, slower ranks; shorter = noisier, faster.',
  },
  {
    key: 'top_n', label: 'Hold top-N', unit: 'names', type: 'int',
    min: 1, max: 100, step: 1, sweepable: true,
    help: 'Number of names held. Fewer = more concentrated → higher return AND higher vol / deeper drawdown.',
  },
  {
    key: 'target_vol', label: 'Per-name vol target', unit: '×', type: 'float',
    min: 0.01, max: 1.0, step: 0.01, sweepable: true,
    help: 'Equal-risk sizing target per name. Each name is scaled so its realized vol matches this.',
  },
  {
    key: 'max_weight', label: 'Single-name cap', unit: '×', type: 'float',
    min: 0.01, max: 1.0, step: 0.01, sweepable: true,
    help: 'Hard cap on any one name’s weight (concentration limit).',
  },
  {
    key: 'regime_gate', label: 'Regime gate', unit: '', type: 'bool',
    sweepable: false,
    help: 'Go flat when the market is below its 200-day MA (bear defense #1).',
  },
  {
    key: 'defended', label: 'Bear defense on', unit: '', type: 'bool',
    sweepable: false,
    help: 'Apply the portfolio vol-target + drawdown throttle. Off = raw v0 selection.',
  },
  {
    key: 'target_port_vol', label: 'Portfolio vol target', unit: '×', type: 'float',
    min: 0.01, max: 1.0, step: 0.01, sweepable: true,
    help: 'The defense’s main dial. Higher = more gross exposure → MORE return AND DEEPER drawdown. The validated setting is ~0.22.',
  },
  {
    key: 'dd_threshold', label: 'Drawdown backstop', unit: '×', type: 'float',
    min: 0.01, max: 1.0, step: 0.01, sweepable: true,
    help: 'Drawdown (vs equity high) that trips the throttle. Smaller = trips sooner (safer, may cut the bull).',
  },
  {
    key: 'de_gross', label: 'Throttle de-gross', unit: '×', type: 'float',
    min: 0.01, max: 1.0, step: 0.01, sweepable: true,
    help: 'Exposure multiplier once the drawdown backstop fires (0.5 = cut gross in half).',
  },
  {
    key: 'leverage_cap', label: 'Leverage cap', unit: '×', type: 'float',
    min: 0.01, max: 3.0, step: 0.1, sweepable: true,
    help: 'Max gross the vol-target can scale to (1.0 = never leverage up).',
  },
  {
    key: 'cost_bps', label: 'Round-trip cost', unit: 'bps', type: 'float',
    min: 0, max: 100, step: 0.5, sweepable: true,
    help: 'Round-trip cost per unit of turnover. Higher = penalizes frequent rebalancing.',
  },
  {
    key: 'starting_cash', label: 'Starting capital', unit: '$', type: 'float',
    min: 1000, max: 10_000_000, step: 1000, sweepable: false,
    help: 'Starting equity (also the chart scale).',
  },
];

export const KNOB_BY_KEY = Object.fromEntries(KNOBS.map((k) => [k.key, k]));

export const SWEEPABLE = KNOBS.filter((k) => k.sweepable);

// The 10 knobs the ConfigOut/dashboard surface shows (excludes defended + starting_cash).
export const CONFIG_KEYS = [
  'lookback', 'top_n', 'target_vol', 'max_weight', 'regime_gate',
  'target_port_vol', 'dd_threshold', 'de_gross', 'leverage_cap', 'cost_bps',
];

// A few built-in starting points for the Engines "Create" / Lab preset flow.
export const PRESETS = [
  { name: 'prod', note: 'validated (RESULTS.md)' },
  { name: 'v0-no-defense', note: 'raw selection, no defense' },
  { name: 'conservative', note: 'tighter defense, lower DD' },
  { name: 'aggressive', note: 'looser defense, more return' },
];

// Knob groups (visual grouping + a one-line "why this matters" + a Learn anchor).
// Single source of truth for KnobGroup, EngineForm, and the Learn deep-links.
export const GROUPS = [
  {
    title: 'Selection', learn: 'selection',
    why: 'How names get picked: rank the universe by momentum, hold the top-N, size each for equal risk.',
    keys: ['lookback', 'top_n', 'target_vol', 'max_weight', 'regime_gate'],
  },
  {
    title: 'Bear defense', learn: 'defense',
    why: 'Risk overlay: scale total exposure down when portfolio vol spikes or the book draws down.',
    keys: ['defended', 'target_port_vol', 'dd_threshold', 'de_gross', 'leverage_cap'],
  },
  {
    title: 'Cost & capital', learn: 'cost',
    why: 'Trading costs (penalize turnover) and starting equity (the chart scale).',
    keys: ['cost_bps', 'starting_cash'],
  },
];
