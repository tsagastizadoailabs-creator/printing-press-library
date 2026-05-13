#!/usr/bin/env python3
"""
pp_deal_finder.py — Real Estate Deal Analyzer
Kapowsin Business Solutions | kapowsincompany.com

Commands:
  analyze <address> [--repairs N] [--arv N]
  equity <address>
  mao <arv> <repairs>
  scan <city> [--limit N] [--min-equity N] [--min-dom N]
  counties
"""

import argparse
import json
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ─────────────────────────────────────────────────────────────────────────────
# COUNTY CONFIGS
# ─────────────────────────────────────────────────────────────────────────────

COUNTIES = {
    "king": {
        "name": "King County",
        "status": "live",
        "parcel_url": "https://gismaps.kingcounty.gov/arcgis/rest/services/Property/KingCo_PropertyInfo/MapServer/2/query",
        "sales_url": "https://gismaps.kingcounty.gov/arcgis/rest/services/Property/KingCo_PropertyInfo/MapServer/3/query",
        "method": "POST",
        "parcel_fields": "PIN,ADDR_FULL,APPRLNDVAL,APPR_IMPR,PROPTYPE,KCA_ACRES,PREUSE_DESC",
        "sales_fields": "PIN,SaleDate,SalePrice,Property_Type,Principal_Use",
        "address_field": "ADDR_FULL",
        "parcel_id_field": "PIN",
        "assessed_land_field": "APPRLNDVAL",
        "assessed_impr_field": "APPR_IMPR",
        "prop_type_field": "PREUSE_DESC",
        "note": None,
    },
    "pierce": {
        "name": "Pierce County",
        "status": "beta",
        "parcel_url": None,
        "sales_url": None,
        "method": None,
        "note": "Pierce County ArcGIS API unavailable — manual lookup at piercecountywa.gov/assessor",
    },
    "snohomish": {
        "name": "Snohomish County",
        "status": "beta",
        "parcel_url": None,
        "sales_url": None,
        "method": None,
        "note": "Snohomish County ArcGIS API unavailable — manual lookup at snoco.org",
    },
}

CITY_TO_COUNTY = {
    # King County cities
    "seattle": "king", "bellevue": "king", "kent": "king", "renton": "king",
    "auburn": "king", "redmond": "king", "kirkland": "king", "sammamish": "king",
    "federal way": "king", "burien": "king", "shoreline": "king", "des moines": "king",
    "tukwila": "king", "covington": "king", "maple valley": "king", "black diamond": "king",
    "enumclaw": "king", "issaquah": "king", "mercer island": "king", "newcastle": "king",
    "kenmore": "king", "lake forest park": "king", "bothell": "king", "woodinville": "king",
    "duvall": "king", "snoqualmie": "king", "north bend": "king", "fall city": "king",
    "skykomish": "king", "carnation": "king",
    # Pierce County cities
    "tacoma": "pierce", "lakewood": "pierce", "puyallup": "pierce", "bonney lake": "pierce",
    "sumner": "pierce", "orting": "pierce", "eatonville": "pierce", "graham": "pierce",
    "spanaway": "pierce", "parkland": "pierce", "university place": "pierce",
    "gig harbor": "pierce", "fife": "pierce", "edgewood": "pierce", "milton": "pierce",
    "roy": "pierce", "steilacoom": "pierce", "dupont": "pierce", "ruston": "pierce",
    "kapowsin": "pierce",
    # Snohomish County cities
    "everett": "snohomish", "marysville": "snohomish", "lynnwood": "snohomish",
    "edmonds": "snohomish", "mukilteo": "snohomish", "snohomish": "snohomish",
    "monroe": "snohomish", "sultan": "snohomish", "gold bar": "snohomish",
    "stanwood": "snohomish", "arlington": "snohomish", "granite falls": "snohomish",
    "index": "snohomish", "lake stevens": "snohomish", "mill creek": "snohomish",
    "mountlake terrace": "snohomish", "brier": "snohomish", "woodway": "snohomish",
}


# ─────────────────────────────────────────────────────────────────────────────
# CORE CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────

def mao_70(arv: float, repairs: float) -> float:
    """Max Allowable Offer — 70% rule"""
    return (arv * 0.70) - repairs


def equity_pct(estimated_value: float, assessed_value: float) -> float:
    """Estimated equity percentage"""
    if estimated_value <= 0:
        return 0.0
    return ((estimated_value - assessed_value) / estimated_value) * 100


def deal_score(eq_pct: float, dom: int, price_drops: int, last_sale_years: float) -> dict:
    """Score a deal 0–100 based on equity, DOM, price drops, and ownership tenure."""
    score = 0
    flags = []

    # Equity score (40 pts max)
    if eq_pct >= 60:
        score += 40
        flags.append("HIGH EQUITY")
    elif eq_pct >= 40:
        score += 30
        flags.append("GOOD EQUITY")
    elif eq_pct >= 20:
        score += 15
    else:
        flags.append("LOW EQUITY")

    # DOM score (30 pts max)
    if dom >= 180:
        score += 30
        flags.append("VERY STALE LISTING")
    elif dom >= 90:
        score += 20
        flags.append("STALE LISTING")
    elif dom >= 45:
        score += 10

    # Price drops (20 pts max)
    if price_drops >= 3:
        score += 20
        flags.append("MULTIPLE PRICE DROPS")
    elif price_drops >= 1:
        score += 10
        flags.append("PRICE REDUCED")

    # Ownership tenure (10 pts max)
    if last_sale_years >= 10:
        score += 10
        flags.append("LONG-TERM OWNER")
    elif last_sale_years >= 5:
        score += 5

    if score < 30:
        rating = "🔴 SKIP"
    elif score < 55:
        rating = "🟡 WATCH"
    elif score < 75:
        rating = "🟢 DEAL"
    else:
        rating = "🔥 HOT DEAL"

    return {"score": score, "rating": rating, "flags": flags}


# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────────────────────────────────────

def _http_get_json(url: str, params: dict, method: str = "GET") -> dict:
    """Fetch JSON from a URL. Returns {} on error."""
    if not HAS_REQUESTS:
        # Fallback to urllib
        import urllib.request
        if method == "POST":
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(url, data=data)
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        else:
            full_url = url + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(full_url)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"  ⚠️  Network error: {e}", file=sys.stderr)
            return {}
    else:
        try:
            if method == "POST":
                resp = requests.post(url, data=params, timeout=15)
            else:
                resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  ⚠️  Network error: {e}", file=sys.stderr)
            return {}


def detect_county(address: str) -> str | None:
    """Guess county from city name in address string."""
    addr_lower = address.lower()
    for city, county in CITY_TO_COUNTY.items():
        if city in addr_lower:
            return county
    return None


def query_king_county_parcel(address: str) -> dict:
    """Query King County ArcGIS for parcel data by address."""
    cfg = COUNTIES["king"]
    # Normalize: strip extra whitespace, uppercase for LIKE match
    addr_upper = " ".join(address.upper().split())
    # Try progressively shorter fragments if full match fails
    fragments = [addr_upper]
    parts = addr_upper.split()
    if len(parts) >= 3:
        fragments.append(" ".join(parts[:3]))
    if len(parts) >= 2:
        fragments.append(" ".join(parts[:2]))

    for fragment in fragments:
        params = {
            "where": f"ADDR_FULL LIKE '%{fragment}%'",
            "outFields": cfg["parcel_fields"],
            "f": "json",
            "resultRecordCount": "5",
            "returnGeometry": "false",
        }
        data = _http_get_json(cfg["parcel_url"], params, method=cfg["method"])
        features = data.get("features", [])
        if features:
            # Return best match (first result)
            return features[0]["attributes"]
    return {}


def query_king_county_sales(pin: str) -> list:
    """Query King County ArcGIS for recent sales by parcel PIN."""
    cfg = COUNTIES["king"]
    params = {
        "where": f"PIN='{pin}'",
        "outFields": cfg["sales_fields"],
        "f": "json",
        "orderByFields": "SaleDate DESC",
        "resultRecordCount": "3",
        "returnGeometry": "false",
    }
    data = _http_get_json(cfg["sales_url"], params, method=cfg["method"])
    return [f["attributes"] for f in data.get("features", [])]


def get_redfin_comps(city: str) -> dict:
    """
    Try to get ARV estimate from pp-redfin CLI.
    Returns dict with median_price, price_per_sqft, dom keys (or empty).
    """
    try:
        result = subprocess.run(
            ["pp-redfin", "search", city, "--limit", "5"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        output = result.stdout
        # Parse median price from output (heuristic)
        import re
        prices = re.findall(r'\$([0-9,]+)', output)
        if prices:
            prices_int = [int(p.replace(',', '')) for p in prices if int(p.replace(',', '')) > 50000]
            if prices_int:
                median = sorted(prices_int)[len(prices_int) // 2]
                return {"median_price": median, "source": "pp-redfin"}
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return {}


def fetch_property_data(address: str) -> dict:
    """
    Master fetch: detects county, queries assessor, returns unified property dict.
    Returns dict with keys: found, county, parcel, assessed_value, prop_type,
    last_sale_price, last_sale_date, last_sale_years, error
    """
    county_key = detect_county(address)

    if county_key is None:
        return {
            "found": False,
            "error": "County not detected. Include city name (e.g., 'Seattle', 'Tacoma') in the address.",
        }

    cfg = COUNTIES[county_key]

    if cfg["parcel_url"] is None:
        return {
            "found": False,
            "county": cfg["name"],
            "error": cfg.get("note", f"{cfg['name']} API not available."),
        }

    if county_key == "king":
        parcel = query_king_county_parcel(address)
        if not parcel:
            return {
                "found": False,
                "county": cfg["name"],
                "error": f"Property not found in King County assessor data.\nTry: pp-redfin search \"{address}\"",
            }

        pin = parcel.get("PIN", "")
        assessed_land = parcel.get("APPRLNDVAL", 0) or 0
        assessed_impr = parcel.get("APPR_IMPR", 0) or 0
        assessed_total = assessed_land + assessed_impr
        prop_type = parcel.get("PREUSE_DESC", parcel.get("PROPTYPE", "Unknown"))
        addr_full = parcel.get("ADDR_FULL", address)

        sales = query_king_county_sales(pin) if pin else []
        last_sale_price = None
        last_sale_date = None
        last_sale_years = 0.0
        last_sale_year = None

        if sales:
            s = sales[0]
            last_sale_price = s.get("SalePrice")
            sale_ts = s.get("SaleDate")
            if sale_ts:
                # ArcGIS returns epoch ms
                sale_dt = datetime.fromtimestamp(sale_ts / 1000, tz=timezone.utc)
                last_sale_date = sale_dt.strftime("%Y-%m-%d")
                last_sale_year = sale_dt.year
                now = datetime.now(tz=timezone.utc)
                last_sale_years = (now - sale_dt).days / 365.25

        return {
            "found": True,
            "county": cfg["name"],
            "parcel": pin,
            "address": addr_full,
            "assessed_value": assessed_total,
            "assessed_land": assessed_land,
            "assessed_impr": assessed_impr,
            "prop_type": prop_type,
            "last_sale_price": last_sale_price,
            "last_sale_date": last_sale_date,
            "last_sale_year": last_sale_year,
            "last_sale_years": last_sale_years,
        }

    return {
        "found": False,
        "county": cfg["name"],
        "error": f"{cfg['name']} API not yet implemented.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────────────────────────────────────

def fmt_money(n) -> str:
    if n is None:
        return "N/A"
    return f"${int(n):,}"


def fmt_pct(n) -> str:
    return f"{n:.1f}%"


SEP = "━" * 44


# ─────────────────────────────────────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_mao(arv: float, repairs: float):
    """Print MAO calculation."""
    mao = mao_70(arv, repairs)
    profit_margin = arv * 0.30
    print()
    print(SEP)
    print("📐 MAX ALLOWABLE OFFER — 70% RULE")
    print(SEP)
    print(f"   ARV (After Repair Value):  {fmt_money(arv)}")
    print(f"   Repairs:                   {fmt_money(repairs)}")
    print(f"   ─────────────────────────────────")
    print(f"   ARV × 70%:                 {fmt_money(arv * 0.70)}")
    print(f"   Minus Repairs:           - {fmt_money(repairs)}")
    print(f"   ─────────────────────────────────")
    print(f"   ✅ MAX OFFER:              {fmt_money(mao)}")
    print(f"   Implied Profit Margin:     {fmt_money(profit_margin)} (30% of ARV)")
    print(SEP)
    print()


def cmd_counties():
    """List supported counties and API status."""
    print()
    print(SEP)
    print("🗺️  SUPPORTED COUNTIES")
    print(SEP)
    status_icon = {"live": "🟢 LIVE", "beta": "🟡 BETA", "offline": "🔴 OFFLINE"}
    for key, cfg in COUNTIES.items():
        icon = status_icon.get(cfg["status"], "⚪")
        print(f"   {icon}  {cfg['name']}")
        if cfg["note"]:
            print(f"         ↳ {cfg['note']}")
    print()
    print("   Cities detected automatically from address.")
    print("   King County: ArcGIS REST API (public, no key required)")
    print("   Pierce/Snohomish: Manual lookup links provided on error")
    print()
    print("   Contribute county integrations: clawhub.ai")
    print(SEP)
    print()


def cmd_equity(address: str):
    """Quick equity check for an address."""
    print(f"\n🔍 Checking equity: {address}")
    prop = fetch_property_data(address)

    if not prop["found"]:
        print(f"\n❌ {prop.get('error', 'Property not found.')}")
        if "county" in prop:
            print(f"   County: {prop['county']}")
        print()
        return

    assessed = prop["assessed_value"]
    # Use assessed as conservative ARV (market is typically higher)
    # Try redfin for better ARV
    city = address.split(",")[0].strip().split()[-1] if "," in address else ""
    redfin = get_redfin_comps(city) if city else {}
    arv = redfin.get("median_price") or assessed * 1.15  # 15% above assessed as fallback

    eq_dollars = arv - assessed
    eq_percent = equity_pct(arv, assessed)

    print()
    print(SEP)
    print(f"💰 EQUITY CHECK — {prop['address']}")
    print(SEP)
    print(f"   County:          {prop['county']}")
    print(f"   Parcel:          {prop['parcel']}")
    print(f"   Assessed Value:  {fmt_money(assessed)}")
    if redfin.get("median_price"):
        print(f"   ARV (Redfin):    {fmt_money(arv)}")
    else:
        print(f"   ARV (est):       {fmt_money(arv)}  ⚠️  estimated — install pp-redfin for real comps")
    print(f"   Equity:          {fmt_money(eq_dollars)} ({fmt_pct(eq_percent)})")
    if eq_percent >= 40:
        print(f"   Signal:          🟢 STRONG equity position")
    elif eq_percent >= 20:
        print(f"   Signal:          🟡 MODERATE equity")
    else:
        print(f"   Signal:          🔴 LOW equity — likely mortgaged up")
    if prop.get("last_sale_years"):
        print(f"   Last Sale:       {prop.get('last_sale_year', 'N/A')} ({prop['last_sale_years']:.0f} yrs ago) @ {fmt_money(prop.get('last_sale_price'))}")
    print(SEP)
    print()


def cmd_analyze(address: str, repairs: float = 35000.0, arv_override: float = None):
    """Full deal analysis."""
    print(f"\n🔍 Analyzing: {address}")
    prop = fetch_property_data(address)

    if not prop["found"]:
        print(f"\n❌ {prop.get('error', 'Property not found.')}")
        if "county" in prop:
            print(f"   County detected: {prop['county']}")
        print()
        return

    assessed = prop["assessed_value"]

    # ARV: override > redfin > assessed * 1.15
    city_guess = ""
    for word in address.split():
        word_clean = word.strip(",.").lower()
        if word_clean in CITY_TO_COUNTY:
            city_guess = word_clean.title()
            break

    redfin = get_redfin_comps(city_guess) if city_guess else {}
    if arv_override:
        arv = arv_override
        arv_source = "manual override"
    elif redfin.get("median_price"):
        arv = redfin["median_price"]
        arv_source = "pp-redfin comps"
    else:
        arv = assessed * 1.15
        arv_source = "estimated (assessed × 1.15)"

    # Equity
    eq_dollars = arv - assessed
    eq_percent = equity_pct(arv, assessed)

    # MAO
    mao = mao_70(arv, repairs)
    list_price = None  # Would come from MLS/Redfin listing data
    dom = 0            # Would come from listing data
    price_drops = 0    # Would come from listing data

    # Score
    score_data = deal_score(eq_percent, dom, price_drops, prop.get("last_sale_years", 0))

    print()
    print(SEP)
    print(f"🏠 DEAL ANALYSIS — {prop['address']}")
    print(SEP)

    print("📋 PROPERTY")
    print(f"   Parcel:      {prop['parcel']}")
    print(f"   Type:        {prop.get('prop_type', 'Unknown')}")
    print(f"   County:      {prop['county']}")

    print()
    print("💰 VALUATION")
    print(f"   Assessed Value:   {fmt_money(assessed)}")
    print(f"   ARV ({arv_source}):".ljust(28) + f"{fmt_money(arv)}")
    print(f"   Equity:           {fmt_money(eq_dollars)} ({fmt_pct(eq_percent)})")

    print()
    print("🏷️  LISTING")
    if list_price:
        print(f"   List Price:    {fmt_money(list_price)}")
    else:
        print(f"   List Price:    N/A — run: pp-redfin search \"{address}\"")
    print(f"   Days on Market: {dom}  (add --dom flag for accurate score)")
    print(f"   Price Drops:    {price_drops}  (use pp-redfin for live listing data)")
    if prop.get("last_sale_year"):
        yrs = prop["last_sale_years"]
        print(f"   Last Sale:     {prop['last_sale_year']} ({yrs:.0f} yrs ago) @ {fmt_money(prop.get('last_sale_price'))}")
    else:
        print(f"   Last Sale:     N/A")

    print()
    print("📐 INVESTOR MATH")
    print(f"   ARV:                        {fmt_money(arv)}")
    print(f"   Repairs (est):              {fmt_money(repairs)}  [adjust with --repairs N]")
    print(f"   MAO (70% rule):             {fmt_money(mao)}")
    if list_price:
        discount = list_price - mao
        discount_pct = (discount / list_price) * 100
        print(f"   Asking Discount Needed:     {fmt_money(discount)} ({fmt_pct(discount_pct)})")

    print()
    score = score_data["score"]
    rating = score_data["rating"]
    flags = score_data["flags"]
    print(f"⚡ DEAL SCORE: {score}/100 — {rating}")
    if flags:
        print("   " + "  ✓ ".join(["✓ " + flags[0]] + flags[1:]))
    if dom == 0:
        print("   ⚠️  DOM/price-drop data missing — score is equity-only")
        print("      Run pp-redfin to get full listing signals")

    print()
    print("📞 NEXT STEPS")
    print(f"   1. Verify repairs estimate on-site")
    print(f"   2. Pull full comp set: pp-redfin comps \"{address}\"")
    print(f"   3. Skip trace owner if off-market target")
    if eq_percent < 20:
        print(f"   4. ⚠️  Low equity — seller likely needs full price. Check for other motivation.")
    print()
    print(f"💡 REHAB ESTIMATE: Run pp-rehab-pricer estimate \"{address}\" <sqft> --scope partial")
    print(SEP)
    print()


def cmd_scan(city: str, limit: int = 10, min_equity: float = 30.0, min_dom: int = 45):
    """Scan a city for potential deals. Currently uses assessed-value equity screening."""
    county_key = CITY_TO_COUNTY.get(city.lower())

    if not county_key:
        print(f"\n❌ City '{city}' not in supported city list.")
        print("   Supported cities include: Seattle, Bellevue, Renton, Tacoma, Everett, etc.")
        print("   Or run: pp_deal_finder.py counties\n")
        return

    cfg = COUNTIES[county_key]

    if cfg["parcel_url"] is None:
        print(f"\n⚠️  {cfg['name']} API unavailable.")
        print(f"   {cfg['note']}\n")
        return

    if county_key != "king":
        print(f"\n⚠️  Scan not yet implemented for {cfg['name']}.")
        print(f"   Supported for scan: King County cities\n")
        return

    print(f"\n🔍 Scanning {city} for deals (equity ≥ {min_equity}%, DOM ≥ {min_dom})...")
    print("   Note: Assessor scan shows equity signal only.")
    print("   DOM/price-drop data requires pp-redfin integration.\n")

    # Query King County for properties in city with high assessed improvement value
    # We look for properties where assessed value suggests equity opportunity
    params = {
        "where": f"ADDR_FULL LIKE '%{city.upper()}%' AND APPR_IMPR > 100000",
        "outFields": "PIN,ADDR_FULL,APPRLNDVAL,APPR_IMPR,PREUSE_DESC",
        "f": "json",
        "resultRecordCount": str(limit * 3),  # Fetch more, filter down
        "returnGeometry": "false",
        "orderByFields": "APPR_IMPR DESC",
    }

    data = _http_get_json(cfg["parcel_url"], params, method=cfg["method"])
    features = data.get("features", [])

    if not features:
        print(f"   No properties found in {city}. Try a different city name.\n")
        return

    deals = []
    for feat in features:
        attr = feat["attributes"]
        pin = attr.get("PIN", "")
        addr = attr.get("ADDR_FULL", "")
        land = attr.get("APPRLNDVAL", 0) or 0
        impr = attr.get("APPR_IMPR", 0) or 0
        assessed = land + impr
        prop_type = attr.get("PREUSE_DESC", "Unknown")

        if assessed <= 0:
            continue

        # Estimated ARV = assessed * 1.15 (conservative)
        arv_est = assessed * 1.15
        eq = equity_pct(arv_est, assessed)

        # Get sale data
        sales = query_king_county_sales(pin) if pin else []
        last_sale_years = 0.0
        last_sale_price = None
        last_sale_year = None
        if sales:
            s = sales[0]
            sp = s.get("SalePrice")
            st = s.get("SaleDate")
            if sp:
                last_sale_price = sp
            if st:
                sale_dt = datetime.fromtimestamp(st / 1000, tz=timezone.utc)
                last_sale_year = sale_dt.year
                last_sale_years = (datetime.now(tz=timezone.utc) - sale_dt).days / 365.25

        score_data = deal_score(eq, 0, 0, last_sale_years)

        if score_data["score"] >= 15 and eq >= min_equity:
            deals.append({
                "address": addr,
                "pin": pin,
                "assessed": assessed,
                "arv_est": arv_est,
                "equity_pct": eq,
                "last_sale_year": last_sale_year,
                "last_sale_years": last_sale_years,
                "last_sale_price": last_sale_price,
                "prop_type": prop_type,
                "score": score_data["score"],
                "rating": score_data["rating"],
                "flags": score_data["flags"],
            })

    # Sort by score descending
    deals.sort(key=lambda x: x["score"], reverse=True)
    deals = deals[:limit]

    if not deals:
        print(f"   No deals matching criteria found. Try lowering --min-equity.\n")
        return

    print(SEP)
    print(f"🏘️  DEAL SCAN — {city.title()} ({len(deals)} results)")
    print(SEP)
    for i, d in enumerate(deals, 1):
        yrs = f"{d['last_sale_years']:.0f}yr" if d["last_sale_years"] else "?"
        print(f"  {i:2}. {d['rating']} [{d['score']:3}/100] {d['address']}")
        print(f"      Assessed: {fmt_money(d['assessed'])} | Equity: {fmt_pct(d['equity_pct'])} | Last sale: {d.get('last_sale_year','?')} ({yrs} ago @ {fmt_money(d.get('last_sale_price'))})")
        if d["flags"]:
            print(f"      Tags: {', '.join(d['flags'])}")
        print()

    print(f"  Run: pp_deal_finder.py analyze \"<address>\" for full analysis")
    print(SEP)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="pp_deal_finder",
        description="Real estate deal analyzer — Kapowsin Business Solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  analyze <address>              Full deal analysis
  equity  <address>              Quick equity check
  mao     <arv> <repairs>        Max Allowable Offer (70% rule)
  scan    <city>                 Scan city for deals
  counties                       List supported counties + status

Examples:
  pp_deal_finder.py mao 385000 35000
  pp_deal_finder.py equity "1020 S Main St Seattle WA"
  pp_deal_finder.py analyze "1020 S Main St Seattle WA" --repairs 25000
  pp_deal_finder.py scan Seattle --limit 10 --min-equity 35
  pp_deal_finder.py counties
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Full deal analysis")
    p_analyze.add_argument("address", help="Property address (include city)")
    p_analyze.add_argument("--repairs", type=float, default=35000, help="Estimated repair cost (default: 35000)")
    p_analyze.add_argument("--arv", type=float, default=None, help="Override ARV estimate")

    # equity
    p_equity = subparsers.add_parser("equity", help="Quick equity check")
    p_equity.add_argument("address", help="Property address (include city)")

    # mao
    p_mao = subparsers.add_parser("mao", help="Max Allowable Offer calculator")
    p_mao.add_argument("arv", type=float, help="After Repair Value")
    p_mao.add_argument("repairs", type=float, help="Estimated repair cost")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan city for deals")
    p_scan.add_argument("city", help="City name")
    p_scan.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p_scan.add_argument("--min-equity", type=float, default=30.0, dest="min_equity", help="Minimum equity %% (default: 30)")
    p_scan.add_argument("--min-dom", type=int, default=45, dest="min_dom", help="Minimum days on market (default: 45)")

    # counties
    subparsers.add_parser("counties", help="List supported counties")

    args = parser.parse_args()

    if args.command == "mao":
        cmd_mao(args.arv, args.repairs)
    elif args.command == "counties":
        cmd_counties()
    elif args.command == "equity":
        cmd_equity(args.address)
    elif args.command == "analyze":
        cmd_analyze(args.address, repairs=args.repairs, arv_override=args.arv)
    elif args.command == "scan":
        cmd_scan(args.city, limit=args.limit, min_equity=args.min_equity, min_dom=args.min_dom)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
