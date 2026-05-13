---
name: re-rehab-pricer
description: "Real estate rehab cost estimator for WA State investors, fix-and-flip buyers, and construction contractors. Queries a local materials database seeded with WA state pricing, generates scope-based project estimates (cosmetic/partial/full gut), calculates MAO with contingency + tax, and optionally populates a Google Sheets rehab budget template. Trigger phrases: 'estimate rehab cost for [address]', 'how much to renovate [sqft] sqft', 'rehab estimate [scope]', 'lookup [material] cost', 'fill in my rehab sheet', 'what does LVP cost in WA', 'materials cost for [item]'."
author: "kapowsin-business-solutions"
license: "Apache-2.0"
allowed-tools: "Read Bash"
---

# re-rehab-pricer — Rehab Cost Estimator (WA State)

Real estate rehab cost estimator for Kapowsin Business Solutions LLC.
Seeded from real Seattle/Tacoma fix-and-flip project data.

## Script Location

```
~/.openclaw/workspace/scripts/pp_rehab_pricer.py
```

Alias: `pp-rehab-pricer` → `python3 ~/.openclaw/workspace/scripts/pp_rehab_pricer.py`

## Commands

### estimate — Full Project Estimate
```bash
python3 scripts/pp_rehab_pricer.py estimate "<address>" <sqft> [--scope cosmetic|partial|full_gut] [--quality low|mid|high]
```

**Scope options:**
- `cosmetic` — Paint, flooring, fixtures, landscaping only ($12–38/sqft)
- `partial` — Cosmetic + kitchen/bath refresh + some systems ($25–75/sqft) ← **default**
- `full_gut` — Full renovation: systems, structural, finishes ($50–130/sqft)

**Quality tiers:**
- `low` — Budget/investor grade
- `mid` — Mid-market flip ← **default**
- `high` — Luxury/premium finish

### lookup — Materials Search
```bash
python3 scripts/pp_rehab_pricer.py lookup <item_name>
```
Returns low/mid/high pricing + labor split for any material in the DB.

### category — List Category Items
```bash
python3 scripts/pp_rehab_pricer.py category <category_name>
```
Examples: `category Kitchen`, `category Baths`, `category Systems`

### categories — List All Categories
```bash
python3 scripts/pp_rehab_pricer.py categories
```

### mao — Maximum Allowable Offer
```bash
python3 scripts/pp_rehab_pricer.py mao <arv> <repairs> [--contingency 15] [--tax 10.25]
```
Calculates MAO at 65%/70%/75% ARV rules with WA state tax on materials + contingency.

### sheet — Google Sheets Integration
```bash
python3 scripts/pp_rehab_pricer.py sheet <spreadsheet_id> [--populate]
```
Read a rehab budget Google Sheet and match line items to DB pricing.
With `--populate`: write prices back to the Materials column.

### update — Update a Material Price
```bash
python3 scripts/pp_rehab_pricer.py update "<item name>" <new_mid_price>
```
Updates mid-tier price in the DB and saves old price to price_history.

## Database

- **Location:** `~/.openclaw/workspace/knowledge-vault/rehab_materials.db`
- **Tables:** `materials`, `price_history`, `project_estimates`
- **Seeded:** 64 items across 8 categories
- **Source:** Jan Wanot flip template + Seattle full gut project example
- **Updated:** 2026-05-12

## Categories

| Category | Subcategories |
|----------|--------------|
| Soft Costs | Permits, Design, Staging |
| Yard | Landscaping, Fence, Concrete, Deck |
| Exterior | Roof, Siding, Windows, Doors, Gutters, Paint, Garage Door |
| Systems | Electrical, HVAC, Plumbing |
| Interior | Demo, Framing, Insulation, Drywall, Paint, Trim |
| Kitchen | Cabinets, Countertops, Backsplash, Appliances, Sink |
| Baths | Vanity, Shower, Tub, Tile, Fixtures |
| Surfaces | LVP, Carpet, Tile, Hardwood, Subfloor |

## Example Output

```
pp-rehab-pricer estimate "5102 S J St Tacoma WA" 1200 --scope partial --quality mid
pp-rehab-pricer mao 385000 55000
pp-rehab-pricer lookup "quartz countertops"
pp-rehab-pricer category Kitchen
```

## WA State Notes

- Sales tax default: **10.25%** (applies to materials only, ~40% of job)
- Contingency default: **15%** standard rehab buffer
- Pricing reflects Pierce/King County markets
- Labor rates PNW union-adjacent (non-union general contractor)
