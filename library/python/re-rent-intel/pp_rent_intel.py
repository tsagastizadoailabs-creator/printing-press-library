#!/usr/bin/env python3
"""
pp-rent-intel — Rent Intelligence CLI for RE Investors
Kapowsin Business Solutions LLC
Data: Zillow ZORI (public) + HUD FMR (API or WA fallback)
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
CONFIG_PATH = Path("/home/openclaw/.openclaw/workspace/knowledge-vault/rent_intel_config.json")

ZORI_URLS = {
    "metro": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
    "city":  "https://files.zillowstatic.com/research/public_csvs/zori/City_zori_uc_sfrcondomfr_sm_month.csv",
    "zip":   "https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv",
}

HUD_BASE = "https://www.huduser.gov/hudapi/public"

# ──────────────────────────────────────────────
# WA STATE FMR 2025 FALLBACK
# ──────────────────────────────────────────────
WA_FMR_2025 = {
    "King County":      {"0br": 1687, "1br": 1887, "2br": 2263, "3br": 3118, "4br": 3583},
    "Pierce County":    {"0br": 1089, "1br": 1263, "2br": 1614, "3br": 2275, "4br": 2712},
    "Snohomish County": {"0br": 1513, "1br": 1712, "2br": 2113, "3br": 2896, "4br": 3250},
    "Thurston County":  {"0br": 1050, "1br": 1213, "2br": 1513, "3br": 2075, "4br": 2338},
    "Clark County":     {"0br": 1100, "1br": 1275, "2br": 1600, "3br": 2200, "4br": 2500},
    "Spokane County":   {"0br":  763, "1br":  900, "2br": 1138, "3br": 1575, "4br": 1775},
    "Kitsap County":    {"0br": 1163, "1br": 1350, "2br": 1688, "3br": 2363, "4br": 2650},
}

# City → County mapping for WA cities
WA_CITY_COUNTY = {
    # King
    "seattle": "King County", "bellevue": "King County", "renton": "King County",
    "kent": "King County", "auburn": "King County", "federal way": "King County",
    "redmond": "King County", "kirkland": "King County", "burien": "King County",
    "shoreline": "King County", "bothell": "King County",
    # Pierce
    "tacoma": "Pierce County", "lakewood": "Pierce County", "puyallup": "Pierce County",
    "gig harbor": "Pierce County", "bonney lake": "Pierce County",
    "sumner": "Pierce County", "fife": "Pierce County", "milton": "Pierce County",
    "edgewood": "Pierce County", "university place": "Pierce County",
    # Snohomish
    "everett": "Snohomish County", "marysville": "Snohomish County",
    "lynnwood": "Snohomish County", "edmonds": "Snohomish County",
    "mukilteo": "Snohomish County", "mountlake terrace": "Snohomish County",
    "mill creek": "Snohomish County", "monroe": "Snohomish County",
    # Thurston
    "olympia": "Thurston County", "lacey": "Thurston County", "tumwater": "Thurston County",
    "yelm": "Thurston County",
    # Clark
    "vancouver": "Clark County", "battle ground": "Clark County",
    "camas": "Clark County", "washougal": "Clark County", "ridgefield": "Clark County",
    # Spokane
    "spokane": "Spokane County", "spokane valley": "Spokane County",
    "cheney": "Spokane County",
    # Kitsap
    "bremerton": "Kitsap County", "bainbridge island": "Kitsap County",
    "poulsbo": "Kitsap County", "port orchard": "Kitsap County",
    "silverdale": "Kitsap County",
}

# Zip → County for common WA zips
WA_ZIP_COUNTY = {
    # Pierce
    "98498": "Pierce County", "98499": "Pierce County", "98444": "Pierce County",
    "98408": "Pierce County", "98409": "Pierce County", "98404": "Pierce County",
    "98405": "Pierce County", "98406": "Pierce County", "98407": "Pierce County",
    "98402": "Pierce County", "98403": "Pierce County", "98465": "Pierce County",
    "98467": "Pierce County", "98466": "Pierce County", "98433": "Pierce County",
    "98439": "Pierce County", "98443": "Pierce County", "98445": "Pierce County",
    "98446": "Pierce County", "98447": "Pierce County",
    # King
    "98101": "King County", "98102": "King County", "98103": "King County",
    "98104": "King County", "98105": "King County", "98106": "King County",
    "98107": "King County", "98108": "King County", "98109": "King County",
    "98112": "King County", "98115": "King County", "98116": "King County",
    "98117": "King County", "98118": "King County", "98119": "King County",
    "98122": "King County", "98125": "King County", "98126": "King County",
    "98133": "King County", "98144": "King County", "98146": "King County",
    "98154": "King County", "98155": "King County", "98178": "King County",
    "98188": "King County", "98198": "King County", "98004": "King County",
    "98005": "King County", "98006": "King County", "98007": "King County",
    "98008": "King County", "98033": "King County", "98034": "King County",
    "98052": "King County", "98055": "King County", "98056": "King County",
    "98058": "King County", "98003": "King County", "98023": "King County",
    "98031": "King County", "98032": "King County", "98042": "King County",
    "98047": "King County", "98148": "King County",
    # Snohomish
    "98201": "Snohomish County", "98203": "Snohomish County", "98204": "Snohomish County",
    "98208": "Snohomish County", "98270": "Snohomish County", "98271": "Snohomish County",
    "98036": "Snohomish County", "98037": "Snohomish County", "98043": "Snohomish County",
    # Thurston
    "98501": "Thurston County", "98502": "Thurston County", "98503": "Thurston County",
    "98506": "Thurston County", "98512": "Thurston County",
    # Clark
    "98660": "Clark County", "98661": "Clark County", "98662": "Clark County",
    "98663": "Clark County", "98664": "Clark County", "98665": "Clark County",
    "98671": "Clark County", "98607": "Clark County",
    # Spokane
    "99201": "Spokane County", "99202": "Spokane County", "99203": "Spokane County",
    "99204": "Spokane County", "99205": "Spokane County", "99206": "Spokane County",
    "99207": "Spokane County", "99208": "Spokane County", "99216": "Spokane County",
    # Kitsap
    "98310": "Kitsap County", "98311": "Kitsap County", "98312": "Kitsap County",
    "98337": "Kitsap County", "98366": "Kitsap County", "98367": "Kitsap County",
    "98370": "Kitsap County",
}

BAR = "━" * 51


# ──────────────────────────────────────────────
# CONFIG HELPERS
# ──────────────────────────────────────────────
def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"hud_token": None, "zori_cache_dir": str(CONFIG_PATH.parent / "zori_cache"), "last_sync": None}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_cache_dir():
    cfg = load_config()
    d = Path(cfg.get("zori_cache_dir", CONFIG_PATH.parent / "zori_cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d


# ──────────────────────────────────────────────
# ZORI DATA HELPERS
# ──────────────────────────────────────────────
def cache_file_path(level):
    return get_cache_dir() / f"zori_{level}.csv"


def cache_is_fresh(level, days=7):
    p = cache_file_path(level)
    if not p.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    return age < timedelta(days=days)


def download_zori(level):
    url = ZORI_URLS[level]
    dest = cache_file_path(level)
    req = urllib.request.Request(url, headers={"User-Agent": "pp-rent-intel/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(dest, "wb") as f:
            f.write(data)
        # Count rows
        lines = data.decode("utf-8", errors="replace").count("\n")
        return lines - 1  # subtract header
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error downloading {level} ZORI: {e}")


def load_zori_csv(level):
    """Load ZORI CSV, auto-sync if missing."""
    p = cache_file_path(level)
    if not p.exists():
        print(f"  → No cache found. Auto-syncing {level} ZORI...")
        download_zori(level)
    rows = []
    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def get_date_columns(rows):
    """Return sorted list of date columns (YYYY-MM-DD format)."""
    if not rows:
        return []
    skip = {"RegionID", "SizeRank", "RegionName", "RegionType", "StateName",
            "State", "City", "Metro", "CountyName", "RegionID"}
    cols = [k for k in rows[0].keys() if k not in skip and "-" in k]
    return sorted(cols)


def get_latest_value(row, date_cols):
    """Get most recent non-empty value from ZORI row."""
    for col in reversed(date_cols):
        val = row.get(col, "").strip()
        if val:
            try:
                return float(val), col
            except ValueError:
                continue
    return None, None


def get_trend(row, date_cols, months_back):
    """Get value N months ago."""
    latest_val, latest_col = get_latest_value(row, date_cols)
    if not latest_col:
        return None, None
    idx = date_cols.index(latest_col)
    back_idx = max(0, idx - months_back)
    for i in range(back_idx, min(back_idx + 3, len(date_cols))):
        val = row.get(date_cols[i], "").strip()
        if val:
            try:
                return float(val), date_cols[i]
            except ValueError:
                continue
    return None, None


def fuzzy_match(query, candidates, key_fn=None, threshold=0.6):
    """Simple fuzzy match — return best candidate or None."""
    q = query.lower().strip()
    best = None
    best_score = 0.0
    for c in candidates:
        name = (key_fn(c) if key_fn else c).lower()
        # Exact contains
        if q in name or name in q:
            score = len(q) / max(len(name), 1)
            if score > best_score:
                best_score = score
                best = c
        # Word overlap
        q_words = set(q.split())
        n_words = set(name.split())
        overlap = len(q_words & n_words)
        if overlap > 0:
            score = overlap / max(len(q_words), len(n_words))
            if score > best_score:
                best_score = score
                best = c
    if best_score >= threshold:
        return best
    return None


# ──────────────────────────────────────────────
# FMR HELPERS
# ──────────────────────────────────────────────
def resolve_county(query):
    """Resolve city/county/zip query to WA county name."""
    q = query.strip().lower()

    # Direct zip lookup
    if q.isdigit() and len(q) == 5:
        return WA_ZIP_COUNTY.get(q)

    # City lookup
    if q in WA_CITY_COUNTY:
        return WA_CITY_COUNTY[q]

    # County direct match
    for county in WA_FMR_2025:
        if county.lower() == q or county.lower().replace(" county", "") == q:
            return county
        if q == county.lower():
            return county

    # Fuzzy county match
    county_names = list(WA_FMR_2025.keys())
    match = fuzzy_match(q, county_names)
    if match:
        return match

    # Fuzzy city match
    city_match = fuzzy_match(q, list(WA_CITY_COUNTY.keys()))
    if city_match:
        return WA_CITY_COUNTY[city_match]

    return None


def get_fmr_data(query, cfg):
    """Return (county_name, fmr_dict, source_label, is_live)."""
    county = resolve_county(query)
    hud_token = cfg.get("hud_token")

    if hud_token and county:
        # Try HUD API
        try:
            url = f"{HUD_BASE}/fmr/statedata/WA?year=2025"
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {hud_token}", "User-Agent": "pp-rent-intel/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            # Parse HUD response
            for item in data.get("data", {}).get("basicdata", []):
                if county and county.lower() in item.get("county_name", "").lower():
                    fmr = {
                        "0br": int(item.get("Efficiency", 0)),
                        "1br": int(item.get("One-Bedroom", 0)),
                        "2br": int(item.get("Two-Bedroom", 0)),
                        "3br": int(item.get("Three-Bedroom", 0)),
                        "4br": int(item.get("Four-Bedroom", 0)),
                    }
                    return county, fmr, "HUD FY2025 FMR (live)", True
        except Exception:
            pass  # Fall through to hardcoded

    # Hardcoded fallback
    if county and county in WA_FMR_2025:
        return county, WA_FMR_2025[county], "HUD FY2025 FMR (cached)", False

    return None, None, None, False


def format_fmr_table(county, fmr, source, is_live):
    lines = [
        BAR,
        f"🏛️  HUD FAIR MARKET RENTS — {county} (2025)",
        BAR,
        f"   Studio (0BR):    ${fmr['0br']:,}/mo",
        f"   1 Bedroom:       ${fmr['1br']:,}/mo",
        f"   2 Bedroom:       ${fmr['2br']:,}/mo",
        f"   3 Bedroom:       ${fmr['3br']:,}/mo",
        f"   4 Bedroom:       ${fmr['4br']:,}/mo",
        "",
        f"   Source: {source} | {county}",
    ]
    if not is_live:
        lines += [
            "   ⚠️  Using cached values. Add HUD token for live data:",
            "   pp-rent-intel token set <your-token>",
        ]
    lines.append(BAR)
    return "\n".join(lines)


# ──────────────────────────────────────────────
# MARKET RENT HELPERS
# ──────────────────────────────────────────────
def find_city_row(query, rows, date_cols):
    """Find best matching city row in ZORI city CSV."""
    q = query.lower().strip()
    # Exact match on RegionName (city)
    for row in rows:
        rn = row.get("RegionName", "").lower()
        st = row.get("StateName", "").lower()
        if rn == q:
            return row
    # Contains match
    for row in rows:
        rn = row.get("RegionName", "").lower()
        if q in rn:
            return row
    # Fuzzy
    match = fuzzy_match(q, rows, key_fn=lambda r: r.get("RegionName", ""))
    return match


def find_metro_row(query, rows, date_cols):
    """Find best matching metro row in ZORI metro CSV."""
    q = query.lower().strip()
    for row in rows:
        rn = row.get("RegionName", "").lower()
        if q in rn or rn in q:
            return row
    # Try city → metro mapping: look for city name in metro names
    for row in rows:
        rn = row.get("RegionName", "").lower()
        if any(word in rn for word in q.split() if len(word) > 3):
            return row
    return None


def find_zip_row(zipcode, rows, date_cols):
    """Find zip row in ZORI zip CSV."""
    for row in rows:
        if row.get("RegionName", "").strip() == str(zipcode).strip():
            return row
    return None


def format_market_output(query, city_row, metro_row, date_cols):
    """Format the market rents output block."""
    label = query
    state = ""
    if city_row:
        label = city_row.get("RegionName", query)
        state = city_row.get("StateName", "")

    city_val, city_col = get_latest_value(city_row, date_cols) if city_row else (None, None)
    metro_val, metro_col = get_latest_value(metro_row, date_cols) if metro_row else (None, None)

    col_label = city_col or metro_col or ""
    try:
        month_label = datetime.strptime(col_label, "%Y-%m-%d").strftime("%b %Y") if col_label else ""
    except ValueError:
        month_label = col_label

    header = f"{label}, {state}".strip(", ")
    lines = [
        BAR,
        f"📊 MARKET RENTS — {header} (Zillow ZORI)",
        BAR,
    ]

    if city_val:
        lines.append(f"   City ({label}, {state}):".ljust(36) + f"${city_val:,.0f}/mo")
    if metro_row:
        metro_name = metro_row.get("RegionName", "Metro")
        lines.append(f"   Metro ({metro_name[:30]}):".ljust(36) + f"${metro_val:,.0f}/mo" if metro_val else f"   Metro: N/A")

    if city_val and city_row:
        val_6m, col_6m = get_trend(city_row, date_cols, 6)
        val_12m, col_12m = get_trend(city_row, date_cols, 12)
        lines.append("")
        if val_6m:
            chg = ((city_val - val_6m) / val_6m * 100)
            sign = "+" if chg >= 0 else ""
            lines.append(f"   6-month trend:  ${val_6m:,.0f} → ${city_val:,.0f} ({sign}{chg:.1f}%)")
        if val_12m:
            chg = ((city_val - val_12m) / val_12m * 100)
            sign = "+" if chg >= 0 else ""
            lines.append(f"   12-month trend: ${val_12m:,.0f} → ${city_val:,.0f} ({sign}{chg:.1f}%)")
    elif metro_val and metro_row:
        val_6m, _ = get_trend(metro_row, date_cols, 6)
        val_12m, _ = get_trend(metro_row, date_cols, 12)
        lines.append("")
        if val_6m:
            chg = ((metro_val - val_6m) / val_6m * 100)
            sign = "+" if chg >= 0 else ""
            lines.append(f"   6-month trend:  ${val_6m:,.0f} → ${metro_val:,.0f} ({sign}{chg:.1f}%)")
        if val_12m:
            chg = ((metro_val - val_12m) / val_12m * 100)
            sign = "+" if chg >= 0 else ""
            lines.append(f"   12-month trend: ${val_12m:,.0f} → ${metro_val:,.0f} ({sign}{chg:.1f}%)")

    if month_label:
        lines.append(f"\n   Data as of: {month_label}")
    lines.append(BAR)
    return "\n".join(lines)


# ──────────────────────────────────────────────
# COMMANDS
# ──────────────────────────────────────────────
def cmd_sync(args):
    """Download/refresh all ZORI CSVs."""
    cfg = load_config()
    print(f"Syncing Zillow ZORI data...\n")
    for level in ["metro", "city", "zip"]:
        print(f"  → Downloading {level.capitalize()} ZORI...", end=" ", flush=True)
        try:
            count = download_zori(level)
            print(f"{count:,} records ✅")
        except RuntimeError as e:
            print(f"❌ {e}")
    cfg["last_sync"] = datetime.now().strftime("%Y-%m-%d")
    save_config(cfg)
    print(f"\n  → Cache updated: {cfg['last_sync']}")


def cmd_market(args):
    """Look up Zillow market rent for a city, zip, or metro."""
    query = args.query.strip()
    cfg = load_config()

    # Check if it's a zip code
    is_zip = query.isdigit() and len(query) == 5

    # Ensure cache
    for level in ["city", "metro"]:
        if not cache_is_fresh(level):
            if not cache_file_path(level).exists():
                print(f"  Auto-syncing {level} ZORI data...")
                try:
                    download_zori(level)
                except RuntimeError as e:
                    print(f"  ⚠️  {e}")

    if is_zip:
        if not cache_file_path("zip").exists():
            print("  Auto-syncing zip ZORI data...")
            try:
                download_zori("zip")
            except RuntimeError as e:
                print(f"  ⚠️  {e}")
        zip_rows = load_zori_csv("zip")
        zip_date_cols = get_date_columns(zip_rows)
        zip_row = find_zip_row(query, zip_rows, zip_date_cols)
        if zip_row:
            city_name = zip_row.get("City", query)
            state_name = zip_row.get("State", "")
            val, col = get_latest_value(zip_row, zip_date_cols)
            month_label = datetime.strptime(col, "%Y-%m-%d").strftime("%b %Y") if col else ""
            print(f"\n{BAR}")
            print(f"📊 MARKET RENTS — ZIP {query} ({city_name}, {state_name}) (Zillow ZORI)")
            print(BAR)
            print(f"   ZIP {query} avg rent:".ljust(36) + f"${val:,.0f}/mo")
            val_6m, _ = get_trend(zip_row, zip_date_cols, 6)
            val_12m, _ = get_trend(zip_row, zip_date_cols, 12)
            if val_6m:
                chg = ((val - val_6m) / val_6m * 100)
                sign = "+" if chg >= 0 else ""
                print(f"   6-month trend:  ${val_6m:,.0f} → ${val:,.0f} ({sign}{chg:.1f}%)")
            if val_12m:
                chg = ((val - val_12m) / val_12m * 100)
                sign = "+" if chg >= 0 else ""
                print(f"   12-month trend: ${val_12m:,.0f} → ${val:,.0f} ({sign}{chg:.1f}%)")
            if month_label:
                print(f"\n   Data as of: {month_label}")
            print(BAR)
        else:
            print(f"  ❌ ZIP {query} not found in Zillow ZORI data.")
        return

    city_rows = load_zori_csv("city")
    metro_rows = load_zori_csv("metro")
    date_cols = get_date_columns(city_rows)
    metro_date_cols = get_date_columns(metro_rows)

    city_row = find_city_row(query, city_rows, date_cols)
    metro_row = find_metro_row(query, metro_rows, metro_date_cols)

    if not city_row and not metro_row:
        # Suggest fuzzy matches
        suggestions = []
        for row in city_rows[:5000]:
            rn = row.get("RegionName", "")
            if query.lower()[:3] in rn.lower():
                suggestions.append(rn)
        if suggestions:
            print(f"  ❌ '{query}' not found. Did you mean: {', '.join(suggestions[:5])}?")
        else:
            print(f"  ❌ '{query}' not found in Zillow ZORI data. Try 'sync' first.")
        return

    print(format_market_output(query, city_row, metro_row, date_cols))


def cmd_fmr(args):
    """Show HUD Fair Market Rents."""
    cfg = load_config()
    query = args.query.strip()
    county, fmr, source, is_live = get_fmr_data(query, cfg)

    if not county:
        # Suggest closest match
        q = query.lower()
        suggestions = [c for c in WA_FMR_2025 if any(w in c.lower() for w in q.split())]
        if suggestions:
            print(f"\n  ❌ County not found for '{query}'. Did you mean: {', '.join(suggestions[:3])}?")
        else:
            print(f"\n  ❌ '{query}' not recognized. Covered counties: {', '.join(WA_FMR_2025.keys())}")
        print("  ℹ️  Add HUD token for full coverage: pp-rent-intel token set <token>")
        return

    print(f"\n{format_fmr_table(county, fmr, source, is_live)}")


def cmd_compare(args):
    """Side-by-side FMR vs market rent with gap analysis."""
    query = args.query.strip()
    cfg = load_config()

    # Get FMR data
    county, fmr, fmr_source, is_live = get_fmr_data(query, cfg)

    # Get market data
    is_zip = query.isdigit() and len(query) == 5

    city_val = None
    metro_val = None
    metro_name = ""
    city_label = query
    month_label = ""

    for level in ["city", "metro"]:
        if not cache_file_path(level).exists():
            try:
                print(f"  Auto-syncing {level} ZORI...")
                download_zori(level)
            except RuntimeError as e:
                print(f"  ⚠️  {e}")

    if is_zip:
        if not cache_file_path("zip").exists():
            try:
                download_zori("zip")
            except RuntimeError as e:
                print(f"  ⚠️  {e}")
        zip_rows = load_zori_csv("zip")
        zip_date_cols = get_date_columns(zip_rows)
        zip_row = find_zip_row(query, zip_rows, zip_date_cols)
        if zip_row:
            city_val, col = get_latest_value(zip_row, zip_date_cols)
            city_label = f"ZIP {query} ({zip_row.get('City', '')})"
            month_label = datetime.strptime(col, "%Y-%m-%d").strftime("%b %Y") if col else ""
    else:
        city_rows = load_zori_csv("city")
        metro_rows = load_zori_csv("metro")
        date_cols = get_date_columns(city_rows)
        metro_date_cols = get_date_columns(metro_rows)
        city_row = find_city_row(query, city_rows, date_cols)
        metro_row = find_metro_row(query, metro_rows, metro_date_cols)
        if city_row:
            city_val, col = get_latest_value(city_row, date_cols)
            city_label = f"{city_row.get('RegionName', query)}, {city_row.get('StateName', '')}"
            month_label = datetime.strptime(col, "%Y-%m-%d").strftime("%b %Y") if col else ""
        if metro_row:
            metro_val, _ = get_latest_value(metro_row, metro_date_cols)
            metro_name = metro_row.get("RegionName", "")

    market_avg = city_val or metro_val

    print(f"\n{'━'*53}")
    print(f"🏘️  RENT INTEL — {query.title()} / {county or 'WA State'}")
    print(f"{'━'*53}")

    print(f"\n📊 MARKET RENTS (Zillow ZORI{' — ' + month_label if month_label else ''})")
    if city_val:
        print(f"   City average:          ${city_val:,.0f}/mo")
    if metro_val and metro_name:
        print(f"   Metro ({metro_name[:25]}):  ${metro_val:,.0f}/mo")
    if not city_val and not metro_val:
        print("   ⚠️  No market data found. Run 'sync' to download ZORI data.")

    if fmr and county:
        print(f"\n🏛️  FAIR MARKET RENTS ({fmr_source} — {county})")
        print(f"   Studio (0BR):  ${fmr['0br']:,}/mo")
        print(f"   1 Bedroom:     ${fmr['1br']:,}/mo")
        print(f"   2 Bedroom:     ${fmr['2br']:,}/mo")
        print(f"   3 Bedroom:     ${fmr['3br']:,}/mo")
        print(f"   4 Bedroom:     ${fmr['4br']:,}/mo")

        if market_avg:
            fmr_2br = fmr["2br"]
            pct = fmr_2br / market_avg * 100
            gap = market_avg - fmr_2br
            sign = "+" if gap >= 0 else ""

            print(f"\n📐 GAP ANALYSIS")
            print(f"   Market avg vs 2BR FMR: ${market_avg:,.0f} vs ${fmr_2br:,}")
            print(f"   FMR is {pct:.1f}% of market average")

            if gap > 0:
                print(f"   → Section 8 tenants likely accepted at 2BR rate")
                print(f"   → Market premium: {sign}${gap:,.0f}/mo above 2BR voucher max")
            else:
                print(f"   → 2BR FMR exceeds market avg — Section 8 competitive!")

            # Check each bedroom size against market
            for br_key, br_label in [("3br", "3BR"), ("4br", "4BR")]:
                fmr_val = fmr[br_key]
                if fmr_val > market_avg:
                    print(f"   → {br_label} FMR (${fmr_val:,}) EXCEEDS market avg — favorable for larger units")

            # Section 8 quick check at market avg
            sample_low = int(fmr_2br * 0.99)
            sample_high = int(market_avg * 1.05) if market_avg > fmr_2br else int(fmr_2br * 1.10)
            print(f"\n🏷️  SECTION 8 QUICK CHECK")
            if sample_low <= fmr_2br:
                print(f"   2BR asking ${sample_low:,}: ✅ QUALIFIES (≤ FMR ${fmr_2br:,})")
            if sample_high > fmr_2br:
                over = sample_high - fmr_2br
                print(f"   2BR asking ${sample_high:,}: ❌ OVER FMR (FMR ${fmr_2br:,} — ${over:,} over limit)")

    if not is_live and fmr:
        print(f"\n   ⚠️  Using cached FMR. Add HUD token for live data:")
        print(f"   pp-rent-intel token set <your-token>")

    print(f"{'━'*53}")


def cmd_section8(args):
    """Quick Section 8 eligibility check."""
    cfg = load_config()
    city = args.city.strip()
    bedrooms = args.bedrooms
    rent = args.rent

    br_key = f"{bedrooms}br" if bedrooms <= 4 else "4br"
    county, fmr, _, _ = get_fmr_data(city, cfg)

    if not county or not fmr:
        print(f"\n  ❌ County not found for '{city}'.")
        print(f"  Covered: {', '.join(WA_FMR_2025.keys())}")
        return

    fmr_val = fmr.get(br_key, fmr["2br"])
    br_label = f"{bedrooms}BR" if bedrooms > 0 else "Studio"

    print(f"\n{BAR}")
    print(f"🏷️  SECTION 8 CHECK — {city.title()} / {county} / {br_label}")
    print(BAR)

    if rent <= fmr_val:
        print(f"  ✅ QUALIFIES — ${rent:,} ≤ {county} FMR ${fmr_val:,} for {br_label}")
    else:
        over = rent - fmr_val
        print(f"  ❌ OVER FMR — ${rent:,} > {county} FMR ${fmr_val:,} by ${over:,}")
        print(f"     Reduce asking rent to ${fmr_val:,} to qualify,")
        print(f"     or apply for exception payment standard.")

    print(BAR)


def cmd_trends(args):
    """Show rent trend table from ZORI data."""
    query = args.query.strip()
    months = args.months

    is_zip = query.isdigit() and len(query) == 5

    if is_zip:
        if not cache_file_path("zip").exists():
            try:
                print("  Auto-syncing zip ZORI...")
                download_zori("zip")
            except RuntimeError as e:
                print(f"  ⚠️  {e}")
                return
        rows = load_zori_csv("zip")
        date_cols = get_date_columns(rows)
        row = find_zip_row(query, rows, date_cols)
        label = f"ZIP {query}"
    else:
        if not cache_file_path("city").exists():
            try:
                print("  Auto-syncing city ZORI...")
                download_zori("city")
            except RuntimeError as e:
                print(f"  ⚠️  {e}")
                return
        rows = load_zori_csv("city")
        date_cols = get_date_columns(rows)
        row = find_city_row(query, rows, date_cols)
        label = query.title()

    if not row:
        print(f"\n  ❌ '{query}' not found. Try 'sync' to refresh data.")
        return

    # Get last N months with data
    data_points = []
    for col in reversed(date_cols):
        val = row.get(col, "").strip()
        if val:
            try:
                data_points.append((col, float(val)))
            except ValueError:
                pass
        if len(data_points) >= months:
            break
    data_points.reverse()

    if not data_points:
        print(f"\n  ❌ No rent data found for '{query}'.")
        return

    print(f"\n{BAR}")
    print(f"📈 RENT TRENDS — {label} (Last {len(data_points)} months)")
    print(BAR)
    print(f"   {'Month':<12} {'Rent':>10}  {'Change':>8}")
    print(f"   {'─'*12} {'─'*10}  {'─'*8}")

    prev_val = None
    for date_str, val in data_points:
        try:
            month_str = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %Y")
        except ValueError:
            month_str = date_str
        if prev_val is not None:
            chg = val - prev_val
            sign = "+" if chg >= 0 else ""
            chg_str = f"{sign}${chg:,.0f}"
        else:
            chg_str = "—"
        print(f"   {month_str:<12} ${val:>9,.0f}  {chg_str:>8}")
        prev_val = val

    if len(data_points) >= 2:
        first_val = data_points[0][1]
        last_val = data_points[-1][1]
        total_chg = last_val - first_val
        total_pct = (total_chg / first_val) * 100
        sign = "+" if total_chg >= 0 else ""
        print(f"   {'─'*12} {'─'*10}  {'─'*8}")
        print(f"   {'Total change':<12}  {'':>9}  {sign}${total_chg:,.0f} ({sign}{total_pct:.1f}%)")

    print(BAR)


def cmd_token(args):
    """Save HUD API token."""
    cfg = load_config()
    if args.token_action == "set":
        cfg["hud_token"] = args.token_value
        save_config(cfg)
        print(f"\n  ✅ HUD token saved.")
        print(f"  Run 'pp-rent-intel fmr \"Pierce County\"' to test.")
    elif args.token_action == "clear":
        cfg["hud_token"] = None
        save_config(cfg)
        print(f"\n  ✅ HUD token cleared. Using hardcoded WA FMR fallback.")
    elif args.token_action == "status":
        token = cfg.get("hud_token")
        if token:
            print(f"\n  ✅ HUD token configured ({token[:8]}...)")
        else:
            print(f"\n  ⚠️  No HUD token set. Using hardcoded WA FMR fallback.")
            print(f"  Get free token at: https://www.huduser.gov/hudapi/public/login")


def cmd_zip(args):
    """Full zip-level lookup: ZORI + nearest county FMR."""
    zipcode = args.zipcode.strip()
    cfg = load_config()

    if not cache_file_path("zip").exists():
        print("  Auto-syncing zip ZORI data...")
        try:
            download_zori("zip")
        except RuntimeError as e:
            print(f"  ⚠️  {e}")

    zip_rows = load_zori_csv("zip")
    zip_date_cols = get_date_columns(zip_rows)
    zip_row = find_zip_row(zipcode, zip_rows, zip_date_cols)

    county = WA_ZIP_COUNTY.get(zipcode)
    county_data, fmr, fmr_source, is_live = get_fmr_data(zipcode, cfg)

    print(f"\n{BAR}")
    print(f"🔍 ZIP CODE LOOKUP — {zipcode}")
    print(BAR)

    if zip_row:
        city_name = zip_row.get("City", "Unknown")
        state_name = zip_row.get("State", "WA")
        val, col = get_latest_value(zip_row, zip_date_cols)
        month_label = datetime.strptime(col, "%Y-%m-%d").strftime("%b %Y") if col else ""
        print(f"\n📊 ZILLOW ZORI{' — ' + month_label if month_label else ''}")
        print(f"   ZIP {zipcode} ({city_name}, {state_name}): ${val:,.0f}/mo")
        val_6m, _ = get_trend(zip_row, zip_date_cols, 6)
        val_12m, _ = get_trend(zip_row, zip_date_cols, 12)
        if val_6m:
            chg = ((val - val_6m) / val_6m * 100)
            sign = "+" if chg >= 0 else ""
            print(f"   6-month trend: ${val_6m:,.0f} → ${val:,.0f} ({sign}{chg:.1f}%)")
    else:
        print(f"\n  ⚠️  ZIP {zipcode} not found in ZORI data.")

    if county_data and fmr:
        print(f"\n🏛️  HUD FAIR MARKET RENTS — {county_data}")
        print(f"   Studio: ${fmr['0br']:,}/mo  |  1BR: ${fmr['1br']:,}/mo  |  2BR: ${fmr['2br']:,}/mo")
        print(f"   3BR: ${fmr['3br']:,}/mo  |  4BR: ${fmr['4br']:,}/mo")
        if not is_live:
            print(f"   ⚠️  Using cached FMR values.")
    else:
        if county:
            print(f"\n  County: {county} (FMR data not available in hardcoded set)")
        else:
            print(f"\n  ⚠️  ZIP {zipcode} not in WA county map. Add HUD token for full coverage.")

    print(BAR)


# ──────────────────────────────────────────────
# MAIN / ARGPARSE
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="pp-rent-intel",
        description="Rent intelligence for RE investors — Zillow ZORI + HUD FMR"
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # sync
    sub.add_parser("sync", help="Download/refresh all ZORI CSVs")

    # market
    p_market = sub.add_parser("market", help="Look up Zillow market rent")
    p_market.add_argument("query", help="City name, zip code, or metro name")

    # fmr
    p_fmr = sub.add_parser("fmr", help="HUD Fair Market Rents")
    p_fmr.add_argument("query", help="City, county, or zip code")

    # compare
    p_compare = sub.add_parser("compare", help="FMR vs market rent side-by-side + gap analysis")
    p_compare.add_argument("query", help="City, county, or zip code")

    # section8
    p_s8 = sub.add_parser("section8", help="Section 8 eligibility check")
    p_s8.add_argument("city", help="City name")
    p_s8.add_argument("bedrooms", type=int, help="Number of bedrooms (0-4)")
    p_s8.add_argument("rent", type=int, help="Monthly asking rent in dollars")

    # trends
    p_trends = sub.add_parser("trends", help="Rent trend from ZORI data")
    p_trends.add_argument("query", help="City name or zip code")
    p_trends.add_argument("--months", type=int, default=12, help="Number of months (default: 12)")

    # token
    p_token = sub.add_parser("token", help="Manage HUD API token")
    p_token.add_argument("token_action", choices=["set", "clear", "status"], metavar="action",
                         help="set <token> | clear | status")
    p_token.add_argument("token_value", nargs="?", default=None, help="HUD API token")

    # zip
    p_zip = sub.add_parser("zip", help="Full zip-level lookup (ZORI + county FMR)")
    p_zip.add_argument("zipcode", help="5-digit zip code")

    args = parser.parse_args()

    dispatch = {
        "sync":     cmd_sync,
        "market":   cmd_market,
        "fmr":      cmd_fmr,
        "compare":  cmd_compare,
        "section8": cmd_section8,
        "trends":   cmd_trends,
        "token":    cmd_token,
        "zip":      cmd_zip,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
