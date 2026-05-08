# TRADING_SYSTEM.md — Operator Playbook

This document encodes the Operator's *trading style* and house rules. Agents read it
right after `VAULT.md` and treat it as the next-tier source of truth. Edit it as your
style evolves; agents will pick up changes on the next run.

## Mandate

- **Universe**: US large/mid-cap equities, liquid ETFs (SPY/QQQ/IWM/sector), majors FX,
  front-month CME futures (ES/NQ/CL/GC), top-15 crypto by market cap.
- **Out of scope**: penny stocks (<$300M mkt cap), single-stock options >30d to expiry
  unless flagged as "event-driven", structured products.
- **Time horizons**: Swing (3–20 sessions) primary; tactical day trades (<1 session)
  only on pre-defined catalysts; long-term (>3 months) only when tagged `#thesis/macro`.

## House Rules

| Rule                                | Limit                                              |
|-------------------------------------|----------------------------------------------------|
| Max single-name notional            | 2% of book                                         |
| Max thematic basket notional        | 5% of book                                         |
| Max gross exposure                  | 100%                                               |
| Max net exposure                    | 50% (long-bias) / -25% (short-bias)                |
| Per-position stop                   | -7% from entry, or 1.5× ATR(20), whichever tighter |
| Daily portfolio loss limit          | -2% (then "cool-off": no new ideas next session)   |
| Min reward:risk to enter            | 2.0                                                |
| Required confidence to size at full | 75                                                 |
| Required confidence to half-size    | 60                                                 |
| Below confidence 60                 | Watch-list only                                    |

## Edge Hypothesis (your testable belief)

> "Markets repeatedly mis-price the *speed* of regime changes. Slow-moving institutional
> flows lag quickly-changing narrative inflection points by 3–10 sessions. Our edge is
> to identify narrative shifts in primary sources (filings, central-bank speeches,
> earnings calls) **before** they propagate into sell-side notes."

If a candidate idea cannot be expressed as an instance of this hypothesis, downgrade
its confidence by 10.

## Pre-Trade Checklist (Trader agent must answer all)

1. What is the catalyst, and on what date is it expected?
2. What price action invalidates the thesis (set the alert)?
3. What is the implied probability vs. our posterior?
4. What is the worst-case scenario? Have we sized for it?
5. Is this idea correlated with another active position? (cap basket exposure)
6. Is there a cheaper way to express the view (ETF vs. single name, futures vs. spot)?
7. Has the Critic logged at least one disconfirming source?

## Post-Trade Review (every closed thesis)

- File `Theses/<id>-postmortem.md` within 48h of close.
- Tag `#thesis/closed` (winner) or `#thesis/invalidated` (loser).
- Score the original confidence vs. realized outcome (-1.0 .. +1.0) for calibration.

## Macro Regime Tags

Agents must classify each session into one of: `regime/risk-on`, `regime/risk-off`,
`regime/range`, `regime/dispersion`, `regime/event-week`. Tag is set by the Researcher
in the daily brief and consulted by the Critic when sizing.

## Data Sources of Record

- Prices: yfinance (default), Polygon (if `POLYGON_API_KEY` set)
- Macro: FRED (no key required for series), BLS, Treasury Direct
- Filings: SEC EDGAR full-text
- Calendar: investing.com economic calendar (manually curated weekly)
- Voice/Notes: local Whisper → `Inbox/`

## Style Notes for Agents

- Prefer charts described in words (e.g. "20DMA crossing 50DMA from below on rising
  volume") over images. The vault stores text; agents reason over text.
- When uncertain between two interpretations, write both, score each, and let the
  Critic prune.
- Default to **smaller size**, **longer horizon**, **wider stops** when regime is
  `event-week` or `dispersion`.
