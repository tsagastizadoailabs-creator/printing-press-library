---
name: re-mortgage-intel
description: 'Mortgage rate intelligence CLI for real estate professionals and lenders. Pulls live 30yr, 15yr, and 5yr ARM rates from Federal Reserve FRED API (free, no key). Shows trends, rate comparisons, and alerts when rates cross thresholds. Trigger phrases: mortgage rates today, 30 year rate, 15 year rate, rate trend, are rates going up, current mortgage rate, ARM rate, FRED mortgage data'
author: kapowsin-business-solutions
license: Apache-2.0
argument-hint: --weeks N | --series 30yr|15yr|arm | --json | --alert-threshold N.NN
allowed-tools: Read Bash
---

# re-mortgage-intel — Mortgage Rate Intelligence

Live mortgage rate data for real-estate professionals, loan officers, and
homebuyer advisors. Sourced from Freddie Mac's Primary Mortgage Market Survey
(PMMS) via the Federal Reserve's FRED service — completely free, no API key,
no signup. Updated weekly (Thursdays).

## When to use

Reach for this skill when the user asks about:

- Current mortgage rates ("what are 30 year rates today?")
- Rate direction ("are rates going up or down?")
- Historical context ("how do rates compare to last month?")
- 15yr vs 30yr vs ARM comparison
- Affordability ("what would a $485k home cost monthly?")
- Lock/float timing decisions

## Setup

Zero setup. The binary `pp-mortgage-intel` is already on PATH at
`~/.local/bin/pp-mortgage-intel`. No API key, no environment variables, no
auth — FRED's CSV endpoint is public.

Data source: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US`
(also MORTGAGE15US, MORTGAGE5US).

## Commands

### current — today's rates

    pp-mortgage-intel current

Output:

    📊 Mortgage Rates — Week of 2026-05-14
    Source: Freddie Mac PMMS via FRED (free, no API key)

    • 30-yr Fixed: 6.36%  ▼ -0.01 pts vs last week
    • 15-yr Fixed: 5.71%  ▼ -0.01 pts vs last week
    • 5/1 ARM:     6.06%

JSON form: `pp-mortgage-intel current --json`

### history — weekly rate series

    pp-mortgage-intel history --weeks 12

Shows the last N weekly observations for 30yr and 15yr side-by-side. Default
is 12 weeks. Use `--json` for structured output (one row per date).

### trend — 4-week and 8-week direction

    pp-mortgage-intel trend

Returns RISING / FALLING / FLAT based on 4-week delta, plus contextual
guidance for lock/float decisions. Threshold: ±0.10 pts over 4 weeks counts
as a directional move; ±0.25 pts triggers an urgency note.

### afford — monthly payment calculator

    pp-mortgage-intel afford --price 485000 --down 10

Computes monthly P&I using the current 30yr rate (or `--rate` override),
estimates taxes + insurance at ~1.25% of home value annually, and reports
the income required under the 28% PITI rule.

Flags:
- `--price N` — home price in dollars (default 500000)
- `--down N` — down payment percent (default 20)
- `--rate N` — override the rate (default: live 30yr)

## Examples

```
# Daily standup: where are rates this morning?
pp-mortgage-intel current

# Client asked about the trend
pp-mortgage-intel trend

# Pre-qual estimate for a $625k house, 15% down
pp-mortgage-intel afford --price 625000 --down 15

# Build a chart from 6 months of history
pp-mortgage-intel history --weeks 26 --json > rates.json
```

## Data notes

- FRED publishes weekly Thursdays; expect today's data to reflect the
  most recent Thursday observation.
- Missing observations (marked `.` in the FRED CSV) are skipped silently.
- The 5/1 ARM series (MORTGAGE5US) was discontinued by Freddie Mac in
  late 2022 — the binary still queries it for completeness but expect
  stale/empty results.
- All rates are national averages; local rates from individual lenders
  will vary.

## Why this is useful

Realtors, mortgage brokers, and financial advisors get rate questions
constantly. Instead of pulling up Bankrate or Mortgage News Daily, this
gives an authoritative Federal Reserve figure in one shell command — and
in JSON form when wiring into spreadsheets, dashboards, or client emails.
