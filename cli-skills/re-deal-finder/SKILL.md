# re-deal-finder

Real estate deal finder and analyzer for investors, wholesalers, and fix-and-flip buyers.
Pulls county assessor data, runs Redfin comps, calculates equity, scores deals, and outputs
Max Allowable Offer (MAO) using the 70% rule.

## Trigger phrases
- "find deals in [city]"
- "analyze [address] for a deal"
- "check equity on [address]"
- "what's my max offer for [address]"
- "run the 70% rule on [address]"
- "scan [city] for motivated sellers"
- "deal score for [address]"

## Script
`~/.openclaw/workspace/scripts/pp_deal_finder.py`

## Commands

### Full deal analysis
```
python3 ~/.openclaw/workspace/scripts/pp_deal_finder.py analyze "<address>" [--repairs N] [--arv N]
```
Output: assessor data, ARV estimate, equity, MAO, deal score, flags, next steps.

### Quick equity check
```
python3 ~/.openclaw/workspace/scripts/pp_deal_finder.py equity "<address>"
```
Fast equity snapshot: assessed value vs ARV estimate, equity % and signal.

### Max Allowable Offer (70% rule)
```
python3 ~/.openclaw/workspace/scripts/pp_deal_finder.py mao <arv> <repairs>
```
Example: `mao 385000 35000` → MAO = $234,500

### Scan a city for deals
```
python3 ~/.openclaw/workspace/scripts/pp_deal_finder.py scan "<city>" [--limit N] [--min-equity N] [--min-dom N]
```
Queries assessor data for high-equity properties. Returns ranked deal list with scores.

### List supported counties
```
python3 ~/.openclaw/workspace/scripts/pp_deal_finder.py counties
```

## Deal Scoring (0–100)
| Signal | Max Points |
|--------|-----------|
| Equity ≥ 60% | 40 pts |
| Days on Market ≥ 180 | 30 pts |
| Price drops ≥ 3 | 20 pts |
| Owner held ≥ 10 years | 10 pts |

Ratings: 🔴 SKIP (<30) | 🟡 WATCH (<55) | 🟢 DEAL (<75) | 🔥 HOT DEAL (75+)

## Data Sources
- **King County:** ArcGIS REST API — live, no key required
  - Parcels: `KingCo_PropertyInfo/MapServer/2`
  - Sales: `KingCo_PropertyInfo/MapServer/3`
- **Pierce County:** ArcGIS API offline — fallback: piercecountywa.gov/assessor
- **Snohomish County:** ArcGIS API offline — fallback: snoco.org
- **Redfin comps:** pp-redfin CLI (optional — provides live ARV estimate)

## Requirements
- Python 3.8+
- `requests` library (optional — falls back to urllib)
- `pp-redfin` CLI (optional — for live ARV comps)

## Setup
No API keys required. Uses public county ArcGIS REST APIs via HTTP POST.

Address must include city name for county auto-detection.
Example: `"1234 Oak Ave Seattle WA"` — not just `"1234 Oak Ave"`

## Notes for AI
- When user says "analyze [address]", run `analyze` command
- When user says "max offer" or "70% rule", run `mao` command  
- When user says "scan [city]", run `scan` command
- Assessor scan (King County) does NOT include DOM or price-drop data — always note this
- Suggest `pp-redfin` comps for full picture when ARV is estimated
- MAO assumes standard 70% rule — some markets use 65–75%, adjust with --arv override

## Published by
Kapowsin Business Solutions — kapowsincompany.com
