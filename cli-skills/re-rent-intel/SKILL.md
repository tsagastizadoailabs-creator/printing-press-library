---
name: re-rent-intel
description: "Real estate rent intelligence tool for investors, landlords, and Section 8 property owners. Pulls Zillow ZORI market rents (Metro/City/Zip level, updated monthly) and HUD Fair Market Rents (FMR) for Section 8 qualification checks. Covers all WA State counties with hardcoded FMR fallback. Trigger phrases: 'what are rents in [city]', 'fair market rent [city]', 'does [rent] qualify for Section 8 in [city]', 'HUD FMR [county]', 'rent trends in [city]', 'compare FMR to market rent', 'rent intel [zip]', 'Zillow rent [city]'."
author: "kapowsin-business-solutions"
license: "Apache-2.0"
argument-hint: "market <city> | fmr <county> | compare <city> | section8 <city> <br> <rent> | zip <zipcode> | trends <city> | sync | token set <token>"
allowed-tools: "Read Bash"
---

# re-rent-intel — Rent Intelligence CLI

## Overview

`pp-rent-intel` is a command-line rent intelligence tool for Washington State real estate investors. It combines **Zillow ZORI** public market rent data with **HUD Fair Market Rents** (FMR) to power Section 8 eligibility checks, gap analysis, and trend reporting.

## Script Location

```
/home/openclaw/.openclaw/workspace/scripts/pp_rent_intel.py
```

Run as: `python3 scripts/pp_rent_intel.py <command>`

## Data Sources

- **Zillow ZORI**: Public CSV feeds (Metro/City/Zip) — no API key required. Updated 16th of each month.
  - Cached in: `knowledge-vault/zori_cache/`
  - Auto-refreshes if >7 days old
- **HUD FMR**: Fair Market Rents via HUD API (free token) or hardcoded WA State fallback (7 counties).

## Config

```
knowledge-vault/rent_intel_config.json
```

```json
{"hud_token": null, "zori_cache_dir": "...", "last_sync": null}
```

## Commands

| Command | Description |
|---------|-------------|
| `sync` | Download/refresh all 3 ZORI CSVs |
| `market <city_or_zip>` | Zillow market rent + 6/12-month trend |
| `fmr <county>` | HUD Fair Market Rents (0-4BR) |
| `compare <city_or_zip>` | FMR vs market side-by-side + gap analysis |
| `section8 <city> <bedrooms> <rent>` | Section 8 eligibility check |
| `zip <zipcode>` | Full zip-level rent lookup |
| `trends <city> [--months N]` | Monthly rent trend table |
| `token set <hud_token>` | Store free HUD API token |
| `token status` | Check if HUD token is configured |

## Examples

```bash
# Sync data (first time or refresh)
python3 scripts/pp_rent_intel.py sync

# Market rent lookup
python3 scripts/pp_rent_intel.py market "Tacoma"
python3 scripts/pp_rent_intel.py market "98498"

# Fair Market Rents
python3 scripts/pp_rent_intel.py fmr "Pierce County"
python3 scripts/pp_rent_intel.py fmr "Tacoma"

# Full comparison + gap analysis
python3 scripts/pp_rent_intel.py compare "Tacoma"

# Section 8 eligibility
python3 scripts/pp_rent_intel.py section8 "Tacoma" 2 1600
python3 scripts/pp_rent_intel.py section8 "Tacoma" 2 1750

# Zip code lookup
python3 scripts/pp_rent_intel.py zip 98498

# Trends (last 12 months)
python3 scripts/pp_rent_intel.py trends "Tacoma" --months 12

# Add HUD token for live FMR data
python3 scripts/pp_rent_intel.py token set eyJhbG...
```

## WA State FMR Coverage (built-in fallback)

King, Pierce, Snohomish, Thurston, Clark, Spokane, Kitsap counties — hardcoded FY2025 values.

## Agent Instructions

When user asks about rents, FMR, or Section 8 in WA State:

1. **Market rent question** → `market <city>` or `market <zip>`
2. **Section 8 eligibility** → `section8 <city> <bedrooms> <rent>`
3. **Fair Market Rents** → `fmr <county>`
4. **Full analysis** → `compare <city>`
5. **Zip-level** → `zip <zipcode>`

If ZORI data is missing (first run), `sync` is auto-triggered. The tool uses hardcoded WA FMR if no HUD token is set — always works for the 7 main WA counties.

## Setup

No API key required for Zillow data.

Optional — free HUD token for live FMR data beyond WA state:
1. Go to: https://www.huduser.gov/hudapi/public/login
2. Register (free)
3. Run: `python3 scripts/pp_rent_intel.py token set <your-token>`

## Published by

Kapowsin Business Solutions — [kapowsincompany.com](https://kapowsincompany.com)
