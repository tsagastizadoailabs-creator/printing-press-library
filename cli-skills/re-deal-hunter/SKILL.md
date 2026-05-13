---
name: re-deal-hunter
description: "Off-market deal finder for real estate investors, wholesalers, and agents. Searches King County WA public records for long-term property owners, calculates ownership tenure using county sales layer absence as the signal, scores motivated seller probability, exports leads for skip tracing. Trigger phrases: 'find off-market deals in [zip]', 'who owns [address]', 'how long has this property been held', 'find motivated sellers in [zip]', 'run my buy box in [zip]', 'export leads for [zip]', 'skip trace [owner] at [address]'."
author: "kapowsin-business-solutions"
license: "Apache-2.0"
argument-hint: "search <zip> [--min-years 5] | owner <address> | tenure <address> | buybox save/list/run | export | skiprtrace | counties"
allowed-tools: "Read Bash"
---

# re-deal-hunter — Off-Market Deal Finder (King County WA)

## How It Works
King County ArcGIS REST API (public, no key). Properties absent from the last-3-years sales layer = long-term holders = motivated seller candidates.

## Commands
- `search <zip> [--min-years 5] [--limit 25]` — Find 5+ year owners in a zip (431 results in 98122)
- `owner <address>` — Full owner intel: tenure, assessed value, sale history
- `tenure <address>` — Quick ownership duration check
- `buybox save/list/run` — Save and run buy box criteria
- `export <results> --csv <file>` — Export for BatchSkipTracing or Skip Sherpa
- `skiprtrace <name> <address>` — Contact lookup (requires Skip Sherpa key)
- `token set skip-sherpa <key>` — Store key
- `counties` — Supported counties + API status

## Data Source
King County ArcGIS REST API — no API key required.
Pierce + Snohomish: stubbed, endpoints pending.

## Setup
```bash
pip install requests
python3 pp_deal_hunter.py counties
```

## Published by
Kapowsin Business Solutions — kapowsincompany.com
