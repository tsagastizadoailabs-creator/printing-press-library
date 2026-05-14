---
name: re-mls-wa
description: 'WA State MLS listing search via SimplyRETS API. Search active/pending/sold listings by city, zip, price, beds, baths. Pull comps, market stats, and listing detail. Requires SimplyRETS API credentials (simplyrets.com) with NWMLS access. Demo mode available without credentials. Trigger phrases: search MLS listings in [city], find homes for sale in [zip], pull comps for [address], MLS stats for [city], active listings [city], sold homes [city]'
author: kapowsin-business-solutions
license: Apache-2.0
argument-hint: search <city> | detail <mls_id> | comps <address> | stats <city> | setup | counties
allowed-tools: Read Bash
---

# re-mls-wa — WA State MLS Search (NWMLS via SimplyRETS)

CLI scaffold for searching Washington State MLS listings. Wraps the SimplyRETS
API (simplyrets.com), which provides hosted access to NWMLS and other regional
MLS feeds. Direct NWMLS access requires a licensed WA broker sponsor;
SimplyRETS handles the licensing layer in exchange for a subscription.

## Status

**Demo mode by default.** Until SimplyRETS credentials are added to the config
file, every call uses the public demo creds (`simplyrets/simplyrets`) and returns
sample data — useful for testing the CLI shape, not real listings. A warning
prints on every command in demo mode.

Run `setup` for instructions on adding live credentials.

## Script

`~/.openclaw/workspace/scripts/pp_mls_wa.py`

## Config

`~/.openclaw/workspace/knowledge-vault/mls_config.json`

```json
{
  "simplyrets_user": null,
  "simplyrets_pass": null,
  "mode": "demo"
}
```

## Commands

### search

```bash
python3 ~/.openclaw/workspace/scripts/pp_mls_wa.py search Seattle --limit 5
python3 ~/.openclaw/workspace/scripts/pp_mls_wa.py search 98101 --status Active --max-price 800000
python3 ~/.openclaw/workspace/scripts/pp_mls_wa.py search Tacoma --beds 3 --baths 2 --min-price 400000
```

Flags: `--status Active|Closed|Pending`, `--limit N` (default 25),
`--min-price N`, `--max-price N`, `--beds N`, `--baths N`.

5-digit numeric args are treated as ZIP/postal codes; everything else goes
through the SimplyRETS `q` parameter (city/text search).

### detail

```bash
python3 ~/.openclaw/workspace/scripts/pp_mls_wa.py detail 1005243
```

Full listing detail by MLS ID — price, beds/baths, year built, type, lot size,
status, days on market, listing agent + office, public remarks.

### comps

```bash
python3 ~/.openclaw/workspace/scripts/pp_mls_wa.py comps "123 Main St Seattle"
python3 ~/.openclaw/workspace/scripts/pp_mls_wa.py comps 1005243 --radius-miles 0.5
```

Pulls up to 10 recently-closed comparable listings in the subject's ZIP or city.
The `--radius-miles` flag is reserved for future GIS filtering — current
implementation uses postal-code + city scope.

### stats

```bash
python3 ~/.openclaw/workspace/scripts/pp_mls_wa.py stats Seattle
```

Aggregates up to 100 closed listings in the city, computes median sold price,
average days-on-market, average list-to-sale ratio, and price range.

### setup

Prints credential setup instructions for SimplyRETS subscription.

### counties

Lists all 39 WA counties. Calls out which are NWMLS-primary vs other boards.

## Output Format

Matches the `pp-deal-finder` style — Unicode header bar, emoji prefix, numbered
listings with address / price / beds-baths-sqft / DOM / MLS# / agent on
separate lines for readability.

## Pitfalls

- **Demo data is shared.** Demo listings are mostly mid-Atlantic / Midwest
  sample properties — searching "Seattle" against demo creds will return zero
  matches. Use generic queries or omit filters to see demo data. Real WA
  results require live credentials.
- **Credentials live in JSON, not env.** The config file should be git-ignored;
  do not commit `mls_config.json` with live creds.
- **SimplyRETS doesn't expose a radius parameter natively.** Comps fall back
  to postal-code + city filtering. Real radius search requires geocoding the
  subject address and passing lat/lng bounds — TODO for a future revision.
- **NWMLS subscription is non-trivial.** Sign-up requires WA broker license
  verification. Allow several business days for activation.
- **Status values are case-sensitive.** Use exactly `Active`, `Closed`, or
  `Pending`.

## Why this exists

NWMLS doesn't sell direct API access to non-brokers. SimplyRETS is the
standard workaround — they hold the broker relationships, you pay them for
clean REST/JSON access. This skill is the CLI we'll wire credentials into
when the SimplyRETS subscription is active.
