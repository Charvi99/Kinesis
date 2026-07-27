// Plain-language explainers for the concepts behind every knob and number.
// Section ids match the knob GROUPS `learn` anchors (selection/defense/cost) so the
// "?" chip on a knob group jumps to the right section.
export const LEARN = [
  {
    id: 'momentum',
    title: 'What is momentum?',
    body: [
      'Momentum is the boring observation that things going up tend to keep going up (for a while). engine_3 ranks the whole universe by the last 252 days of return and holds the strongest names.',
      'It is not a fundamentals call or a gut feeling — it is a rules-based trend-following filter. The edge comes from being systematically invested in the names that are already winning, rather than trying to predict which ones will.',
    ],
    tip: 'Momentum works best in calm, trending markets and gets chopped in sharp reversals — exactly what the regime gate and bear defense try to protect against.',
  },
  {
    id: 'selection',
    title: 'Selection knobs',
    body: [
      'lookback = how much history the momentum rank uses (longer = smoother and slower; shorter = noisier and faster). top_n = how many names you hold (fewer = more concentrated, bigger swings both ways).',
      'target_vol + max_weight size each name for equal risk so one stock cannot dominate the book. regime_gate flips the whole book to cash when the broad market is below its 200-day average — a simple "sit out bears" switch.',
    ],
    tip: 'Concentration (low top_n) raises both return AND drawdown. There is no free lunch — you are choosing where on that trade-off to sit.',
  },
  {
    id: 'defense',
    title: 'Bear defense (the risk overlay)',
    body: [
      'target_port_vol scales total exposure so the portfolio targets a fixed volatility: when realized vol spikes, the engine holds less. dd_threshold + de_gross are a drawdown backstop — once the book falls more than the threshold from its high, exposure gets cut.',
      'defended on/off decides whether this overlay runs at all. Off = raw selection (more return in bull markets, the full drawdown in crashes).',
    ],
    tip: 'Higher target_port_vol = more gross exposure = more return AND deeper drawdowns. The validated setting (~0.22) is the dial that trades a hair of Sharpe for roughly half the drawdown.',
  },
  {
    id: 'cost',
    title: 'Cost & capital',
    body: [
      'cost_bps is the round-trip trading cost per unit of turnover — it penalizes frequent rebalancing. starting_cash is just the equity the chart is scaled to; it does not change returns measured in percent.',
    ],
    tip: 'If a config only looks good at cost_bps = 0, it is not real — turnover eats the edge.',
  },
  {
    id: 'sharpe',
    title: 'Reading the numbers',
    body: [
      'Sharpe is risk-adjusted return: return per unit of volatility. About 0.7 is what buy-and-hold SPY delivers; above 1.0 is genuinely good; above 1.5 is excellent. max drawdown is the worst peak-to-trough loss — how much pain you sit through to get the return.',
      'PSR0 is the probability the "true" Sharpe is above zero given the sample size: 0.95+ is statistically significant, 0.80–0.95 is suggestive, below that is inconclusive.',
    ],
    tip: 'Always read Sharpe AND drawdown together. A high-Sharpe path that draws down 40% is a different animal than the same Sharpe with a 15% drawdown.',
  },
  {
    id: 'lab',
    title: 'How to use the Lab',
    body: [
      'Single = run one config end-to-end. Sweep = vary ONE knob across a range and watch the equity paths fan out — click a Focus pill (or a line, or a table row) to pin one value and read its numbers.',
      'Compare = put two engines side by side as a table; the ▲ marks whoever is better on each row. Create variants on the Engines tab, compare them here, and only then deploy one.',
    ],
    tip: 'Turn ONE knob at a time. If you change five things and the result moves, you will not know which one caused it.',
  },
];
