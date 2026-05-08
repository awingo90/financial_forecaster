---
id: <% tp.date.now("YYYY-MM-DD") %>-<%* tR += await tp.system.prompt("ticker-or-theme") %>-v1
created: <% tp.date.now("YYYY-MM-DDTHH:mm") %>
updated: <% tp.date.now("YYYY-MM-DDTHH:mm") %>
ticker: ""
theme: ""
side: long  # long|short|neutral
horizon_days: 10
confidence: 0
status: draft  # draft|active|closed|invalidated
catalyst_date: ""
entry_zone: ""
stop: ""
target: ""
reward_risk: 0.0
position_size_pct: 0.0
regime: ""
tags: [thesis/draft]
sources: []
critic_signoff: false
backtest_run: false
---

# Thesis: <% tp.file.title %>

## TL;DR (≤280 chars)


## The Setup
*What is happening in the world that creates this opportunity? Cite primary sources.*


## The Edge (per `TRADING_SYSTEM.md`)
*Why is this mis-priced? What does the market not yet see?*


## Key Claims (Bayesian)
| # | Claim | Prior | Evidence | Posterior | Falsifier |
|---|-------|-------|----------|-----------|-----------|
| 1 |       | 0.5   |          | 0.5       |           |

## Risk
- **Stop**:
- **Invalidation conditions**:
  - [ ]
- **Worst-case loss**:
- **Correlated exposures**:

## Backtest
- Sample size:
- Sharpe:
- Max DD:
- Regimes covered:
- Notebook: `[[<thesis-id>-backtest]]`

## Critic Review
*Filled by Critic agent. Must include ≥1 disconfirming source.*


## Trade Plan (SIMULATED — NOT FOR EXECUTION)
- Entry:
- Size:
- Stop:
- Target:
- Time stop:

## Disclaimer
This thesis is a research artifact, not investment advice. See `VAULT.md §9`.
