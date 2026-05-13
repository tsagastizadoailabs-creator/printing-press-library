#!/usr/bin/env python3
"""
pp-deal-hunter — Off-Market Deal Finder for King County WA
Kapowsin Business Solutions — kapowsincompany.com

Usage:
  python3 pp_deal_hunter.py search 98122 [--min-years 5] [--limit 25]
  python3 pp_deal_hunter.py owner "11745 24th Ave NE Seattle WA"
  python3 pp_deal_hunter.py tenure "1234 Main St Seattle WA"
  python3 pp_deal_hunter.py buybox save "KC-Flips" --zip 98122 --min-years 8 --property-type SFR
  python3 pp_deal_hunter.py buybox list
  python3 pp_deal_hunter.py buybox run "KC-Flips"
  python3 pp_deal_hunter.py export results.json --csv leads.csv
  python3 pp_deal_hunter.py skiprtrace "JOHNSON ROBERT" "1234 Main St Tacoma"
  python3 pp_deal_hunter.py token set skip-sherpa <key>
  python3 pp_deal_hunter.py counties
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import Optional

import requests

# ─── Paths ────────────────────────────────────────────────────────────────────

WORKSPACE = "/home/openclaw/.openclaw/workspace"
CONFIG_FILE = os.path.join(WORKSPACE, "knowledge-vault", "deal_hunter_config.json")
DB_FILE = os.path.join(WORKSPACE, "knowledge-vault", "deal_hunter.db")

# ─── API Endpoints ────────────────────────────────────────────────────────────

KC_BASE = "https://gismaps.kingcounty.gov/arcgis/rest/services/Property/KingCo_PropertyInfo/MapServer"
KC_PARCELS_URL = f"{KC_BASE}/2/query"   # Layer 2: assessed value, property type, address, ZIP
KC_SALES_URL   = f"{KC_BASE}/3/query"   # Layer 3: last sale date, price, owner names

# Correct field names (validated against live API)
# Layer 2: PIN, ADDR_FULL, APPRLNDVAL, APPR_IMPR, PROPTYPE, PREUSE_DESC, ZIP5, CTYNAME
# Layer 3: PIN, address, SaleDate, SalePrice, Sellername, buyername, Principal_Use, Property_Class

SUPPORTED_COUNTIES = {
    "king": {
        "name": "King County, WA",
        "parcels_url": KC_PARCELS_URL,
        "sales_url": KC_SALES_URL,
        "status": "✅ LIVE",
        "notes": "Full support — ArcGIS public REST API",
    },
    "pierce": {
        "name": "Pierce County, WA",
        "parcels_url": None,
        "sales_url": None,
        "status": "🔜 PLANNED",
        "notes": "Architecture stubbed — API endpoint TBD",
    },
    "snohomish": {
        "name": "Snohomish County, WA",
        "parcels_url": None,
        "sales_url": None,
        "status": "🔜 PLANNED",
        "notes": "Architecture stubbed — API endpoint TBD",
    },
}

# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    defaults = {
        "skip_sherpa_key": None,
        "default_county": "king",
        "default_min_years": 5,
        "default_limit": 25,
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
        defaults.update(saved)
    return defaults


def save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ─── Database ─────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS buyboxes (
            name        TEXT PRIMARY KEY,
            zip         TEXT,
            min_years   INTEGER,
            max_years   INTEGER,
            property_type TEXT,
            min_equity  INTEGER,
            limit_n     INTEGER,
            county      TEXT DEFAULT 'king',
            created_at  TEXT DEFAULT (datetime('now')),
            last_run    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query       TEXT,
            county      TEXT,
            params      TEXT,
            result_count INTEGER,
            ran_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


# ─── Core Calculations ────────────────────────────────────────────────────────

def calculate_tenure(sale_date_ms: Optional[int]) -> dict:
    """Calculate how long owner has held property."""
    if not sale_date_ms:
        return {"years": None, "signal": "UNKNOWN", "label": "Unknown tenure", "sale_date": None}

    sale_date = datetime.fromtimestamp(sale_date_ms / 1000)
    years = (datetime.now() - sale_date).days / 365.25

    if years >= 10:
        signal = "LONG_TERM"
        label = f"🔥 {years:.1f} years (long-term owner)"
    elif years >= 5:
        signal = "MID_TERM"
        label = f"⚡ {years:.1f} years (mid-term)"
    elif years >= 2:
        signal = "SHORT_TERM"
        label = f"🟡 {years:.1f} years"
    else:
        signal = "RECENT"
        label = f"🔴 {years:.1f} years (recent buyer)"

    return {
        "years": round(years, 1),
        "signal": signal,
        "label": label,
        "sale_date": sale_date.strftime("%b %Y"),
    }


def score_deal(tenure_years: Optional[float], price_drops: int = 0, dom: int = 0) -> dict:
    score = 0
    flags = []

    if tenure_years is None:
        # No Layer 3 record = not sold in 2.5+ years = long-term holder candidate
        # Score as mid-tier target — skip trace to confirm ownership
        return {"score": 45, "rating": "🔥 SKIP-TRACE TARGET", "flags": ["NO RECENT SALE (5+ yrs)", "SKIP TRACE FOR OWNER NAME"]}

    # Tenure (60 pts — most important off-market signal)
    if tenure_years >= 15:
        score += 60
        flags.append("VERY LONG-TERM OWNER 🔥")
    elif tenure_years >= 10:
        score += 50
        flags.append("LONG-TERM OWNER")
    elif tenure_years >= 7:
        score += 35
        flags.append("MID-LONG TENURE")
    elif tenure_years >= 5:
        score += 20
    elif tenure_years < 2:
        score -= 20
        flags.append("RECENT BUYER — LOW MOTIVATION")

    # DOM (from Redfin if listed — 20 pts)
    if dom >= 90:
        score += 20
        flags.append("STALE LISTING")
    elif dom >= 45:
        score += 10

    # Price drops (20 pts)
    if price_drops >= 2:
        score += 20
        flags.append("MULTIPLE PRICE DROPS")
    elif price_drops >= 1:
        score += 10

    score = max(0, score)
    if score < 20:
        rating = "🔴 SKIP"
    elif score < 45:
        rating = "🟡 WATCH"
    elif score < 65:
        rating = "🟢 TARGET"
    else:
        rating = "🔥 HOT TARGET"

    return {"score": score, "rating": rating, "flags": flags}


def fmt_money(val) -> str:
    if val is None:
        return "N/A"
    try:
        return f"${int(val):,}"
    except (ValueError, TypeError):
        return str(val)


def tenure_emoji(signal: str) -> str:
    return {"LONG_TERM": "🔥", "MID_TERM": "⚡", "SHORT_TERM": "🟡", "RECENT": "🔴"}.get(signal, "❓")


# ─── King County API ──────────────────────────────────────────────────────────

def kc_query_parcels_by_address(address: str, limit: int = 10) -> list:
    """Search parcels layer by address string. Extracts house number for best match."""
    # Extract house number (first token) for reliable LIKE match
    parts = address.strip().upper().split()
    if parts and parts[0].isdigit():
        house_num = parts[0]
        # Try to get street name fragment too
        street_fragment = " ".join(parts[1:3]) if len(parts) > 1 else ""
        if street_fragment:
            where = f"ADDR_FULL LIKE '{house_num} {street_fragment}%'"
        else:
            where = f"ADDR_FULL LIKE '{house_num}%'"
    else:
        where = f"ADDR_FULL LIKE '%{parts[0] if parts else address.upper()}%'"
    params = {
        "where": where,
        "outFields": "PIN,ADDR_FULL,APPRLNDVAL,APPR_IMPR,PROPTYPE,PREUSE_DESC,ZIP5,CTYNAME",
        "f": "json",
        "resultRecordCount": limit,
    }
    try:
        resp = requests.post(KC_PARCELS_URL, data=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            print(f"  ⚠️  Parcels API error: {data['error']}", file=sys.stderr)
            return []
        return data.get("features", [])
    except Exception as e:
        print(f"  ⚠️  Parcels API error: {e}", file=sys.stderr)
        return []


def kc_query_sales_by_pin(pin: str) -> list:
    """Get sales records for a specific PIN."""
    params = {
        "where": f"PIN='{pin}'",
        "outFields": "PIN,address,SaleDate,SalePrice,Sellername,buyername,Principal_Use,Property_Class",
        "f": "json",
        "resultRecordCount": 5,
    }
    try:
        resp = requests.post(KC_SALES_URL, data=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("features", [])
    except Exception as e:
        print(f"  ⚠️  Sales API error: {e}", file=sys.stderr)
        return []


def kc_query_sales_by_zip(zip_code: str, limit: int = 200) -> list:
    """Bulk scan sales records by ZIP code, sorted oldest first (long-term owners)."""
    params = {
        "where": f"address LIKE '%{zip_code}%' AND SalePrice > 0",
        "outFields": "PIN,address,SaleDate,SalePrice,buyername,Sellername,Principal_Use",
        "f": "json",
        "resultRecordCount": limit,
        "orderByFields": "SaleDate ASC",
    }
    try:
        resp = requests.post(KC_SALES_URL, data=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get("features", [])
    except Exception as e:
        print(f"  ⚠️  Sales bulk API error: {e}", file=sys.stderr)
        return []


def kc_query_parcels_by_pin(pin: str) -> Optional[dict]:
    """Get parcel details for a specific PIN."""
    params = {
        "where": f"PIN='{pin}'",
        "outFields": "PIN,ADDR_FULL,APPRLNDVAL,APPR_IMPR,PROPTYPE,PREUSE_DESC,ZIP5,CTYNAME",
        "f": "json",
        "resultRecordCount": 1,
    }
    try:
        resp = requests.post(KC_PARCELS_URL, data=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            return None
        features = data.get("features", [])
        return features[0] if features else None
    except Exception as e:
        print(f"  ⚠️  Parcel PIN lookup error: {e}", file=sys.stderr)
        return None


def kc_query_parcels_by_zip(zip_code: str, limit: int = 500) -> list:
    """Get all parcels in a ZIP code from layer 2 (has assessed values + address)."""
    params = {
        "where": f"ZIP5='{zip_code}'",
        "outFields": "PIN,ADDR_FULL,APPRLNDVAL,APPR_IMPR,PROPTYPE,PREUSE_DESC,ZIP5,CTYNAME",
        "f": "json",
        "resultRecordCount": limit,
    }
    try:
        resp = requests.post(KC_PARCELS_URL, data=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            print(f"  ⚠️  Parcels ZIP query error: {data['error']}", file=sys.stderr)
            return []
        return data.get("features", [])
    except Exception as e:
        print(f"  ⚠️  Parcels ZIP query error: {e}", file=sys.stderr)
        return []


def kc_query_sales_by_pins(pins: list) -> dict:
    """Batch fetch sales records for multiple PINs. Returns dict keyed by PIN."""
    if not pins:
        return {}
    # ArcGIS IN clause — batch up to 100 at a time
    results = {}
    batch_size = 80
    for i in range(0, len(pins), batch_size):
        batch = pins[i:i + batch_size]
        pin_list = "','".join(batch)
        params = {
            "where": f"PIN IN ('{pin_list}') AND SalePrice > 0",
            "outFields": "PIN,address,SaleDate,SalePrice,Sellername,buyername,Principal_Use,Property_Class",
            "f": "json",
            "resultRecordCount": len(batch) * 2,
            "orderByFields": "SaleDate ASC",
        }
        try:
            resp = requests.post(KC_SALES_URL, data=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                continue
            for feat in data.get("features", []):
                a = feat["attributes"]
                pin = str(a.get("PIN", ""))
                # Keep oldest sale (lowest SaleDate = longest tenure)
                if pin not in results or (a.get("SaleDate") or 0) < (results[pin].get("SaleDate") or 0):
                    results[pin] = a
        except Exception as e:
            print(f"  ⚠️  Batch sales query error: {e}", file=sys.stderr)
    return results


PROP_TYPE_MAP = {
    "R": "Residential",
    "C": "Commercial",
    "I": "Industrial",
    "A": "Agricultural",
    "L": "Land/Vacant",
}

PROP_FILTER_MAP = {
    "SFR":   ["R"],
    "MFR":   ["R"],
    "CONDO": ["R"],
    "LAND":  ["A", "L"],
}

PRINCIPAL_USE_FILTER = {
    "SFR":   ["RESIDENTIAL", "SINGLE FAMILY"],
    "MFR":   ["APARTMENT", "MULTI FAMILY", "MULTIFAMILY"],
    "CONDO": ["CONDO"],
    "LAND":  ["VACANT"],
}


def matches_property_type_filter(principal_use: str, prop_type_filter: Optional[str]) -> bool:
    if not prop_type_filter:
        return True
    pu = (principal_use or "").upper()
    for kw in PRINCIPAL_USE_FILTER.get(prop_type_filter, []):
        if kw in pu:
            return True
    return False


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_counties(args):
    SEP = "━" * 58
    print(SEP)
    print("🗺️  DEAL HUNTER — Supported Counties")
    print(SEP)
    for key, info in SUPPORTED_COUNTIES.items():
        print(f"\n  {info['status']}  {info['name']}")
        print(f"     {info['notes']}")
    print(f"\n{SEP}")
    print("  Data source: King County ArcGIS REST API (public, no key)")
    print("  Pierce + Snohomish: coming in next release")
    print(SEP)


def cmd_owner(args):
    address = " ".join(args.address)
    SEP = "━" * 46

    print(f"\n  🔍 Looking up: {address} ...")

    # Step 1: Find parcel
    features = kc_query_parcels_by_address(address, limit=5)
    if not features:
        print(f"\n  ❌ No parcels found for address: {address}")
        print("     Try adjusting the address format (e.g., '11745 24TH AVE NE')")
        return

    parcel = features[0]["attributes"]
    pin = parcel.get("PIN", "")
    addr_full = parcel.get("ADDR_FULL", address)
    appr_land = parcel.get("APPRLNDVAL") or 0
    appr_impr = parcel.get("APPR_IMPR") or 0
    appr_value = (appr_land + appr_impr) if (appr_land or appr_impr) else None
    prop_type_code = parcel.get("PROPTYPE", "")
    prop_type_label = PROP_TYPE_MAP.get(str(prop_type_code), str(prop_type_code))
    preuse_desc = (parcel.get("PREUSE_DESC") or "").strip()

    # Step 2: Get sales data
    sales = kc_query_sales_by_pin(str(pin))
    sale_attrs = sales[0]["attributes"] if sales else {}

    sale_date_ms = sale_attrs.get("SaleDate")
    sale_price = sale_attrs.get("SalePrice")
    buyer = sale_attrs.get("buyername", "UNKNOWN")
    seller = sale_attrs.get("Sellername", "UNKNOWN")
    principal_use = (sale_attrs.get("Principal_Use") or preuse_desc or "").strip()
    prop_class = (sale_attrs.get("Property_Class") or prop_type_label or "").strip()

    tenure = calculate_tenure(sale_date_ms)
    deal = score_deal(tenure["years"])

    # Calculate sale age in months
    if tenure["sale_date"]:
        sale_dt = datetime.fromtimestamp(sale_date_ms / 1000)
        months_ago = int((datetime.now() - sale_dt).days / 30.44)
        if months_ago >= 24:
            age_label = f"{tenure['years']:.1f} years ago"
        else:
            age_label = f"{months_ago} months ago"
    else:
        age_label = "Unknown"

    tenure_label = tenure["label"]
    if tenure["signal"] == "RECENT":
        motivation = "Low probability (bought recently)"
    elif tenure["signal"] == "SHORT_TERM":
        motivation = "Below average (short tenure)"
    elif tenure["signal"] == "MID_TERM":
        motivation = "Moderate — worth a conversation"
    else:
        motivation = "High — prime off-market candidate 🎯"

    print()
    print(SEP)
    print(f"🏠 OWNER INTEL — {addr_full}, King County WA")
    print(SEP)
    print(f"📋 PROPERTY")
    print(f"   PIN:        {pin}")
    print(f"   Type:       {principal_use or prop_type_label} / {prop_class or 'N/A'}")
    print(f"   County:     King County, WA")
    print()
    print(f"💰 VALUATION")
    print(f"   Assessed Value:   {fmt_money(appr_value)}")
    print(f"   Last Sale Price:  {fmt_money(sale_price)} ({tenure['sale_date'] or 'Unknown'})")
    print(f"   Last Sale Age:    {age_label}")
    print()
    print(f"👤 OWNERSHIP")
    print(f"   Current Owner:   {buyer}")
    print(f"   Tenure:          {tenure_label}")
    print(f"   Previous Owner:  {seller}")
    print()
    print(f"⚡ DEAL SIGNALS")
    print(f"   Tenure signal:  {tenure_label}")
    print(f"   Score:          {deal['score']}/100 — {deal['rating']}")
    print(f"   Motivated?:     {motivation}")
    if deal["flags"]:
        for flag in deal["flags"]:
            print(f"   ⚑  {flag}")
    print()
    print(f"📞 NEXT STEP")
    first_name = buyer.split("+")[0].strip() if buyer else "OWNER"
    print(f"   Skip trace: python3 pp_deal_hunter.py skiprtrace \"{first_name}\" \"{addr_full}\"")
    print(SEP)
    print()


def cmd_tenure(args):
    address = " ".join(args.address)
    print(f"  🔍 Checking tenure: {address} ...")

    features = kc_query_parcels_by_address(address, limit=3)
    if not features:
        print(f"  ❌ No property found for: {address}")
        return

    parcel = features[0]["attributes"]
    pin = parcel.get("PIN", "")
    addr_full = parcel.get("ADDR_FULL", address)

    sales = kc_query_sales_by_pin(str(pin))
    if not sales:
        print(f"  ❌ No sales data for PIN {pin}")
        return

    sale_attrs = sales[0]["attributes"]
    sale_date_ms = sale_attrs.get("SaleDate")
    buyer = sale_attrs.get("buyername", "UNKNOWN")

    tenure = calculate_tenure(sale_date_ms)
    emoji = tenure_emoji(tenure["signal"])

    print(f"\n  {emoji}  {addr_full}")
    print(f"     Owner:    {buyer}")
    print(f"     Tenure:   {tenure['label']}")
    if tenure["sale_date"]:
        print(f"     Bought:   {tenure['sale_date']}")
    print()


def cmd_search(args):
    query = args.query
    min_years = args.min_years
    limit = args.limit
    prop_type = args.property_type
    no_recent = args.no_recent_sale

    SEP = "━" * 55
    is_zip = query.isdigit() and len(query) == 5

    print(f"\n  🔍 Scanning King County — {query} | Min {min_years} yrs ...")

    if is_zip:
        # Step 1: Get all parcels in this ZIP from layer 2 (has assessed values)
        print(f"  📋 Fetching parcels for ZIP {query} ...")
        parcel_features = kc_query_parcels_by_zip(query, limit=500)
        if not parcel_features:
            print(f"\n  ❌ No parcels found for ZIP: {query}")
            print("     Try a valid King County ZIP like 98122, 98005, 98103")
            return

        # Build parcel index by PIN
        parcel_index = {}
        for feat in parcel_features:
            a = feat["attributes"]
            pin = str(a.get("PIN", ""))
            if pin:
                parcel_index[pin] = a

        print(f"  📋 Found {len(parcel_index)} parcels → fetching sales data ...")

        # Step 2: Batch fetch oldest sales for all PINs
        all_pins = list(parcel_index.keys())
        sales_index = kc_query_sales_by_pins(all_pins)
    else:
        # Non-ZIP query: fall back to address-fragment search on layer 3
        print(f"  📋 Searching by area fragment: {query} ...")
        # Use older sales layer bulk scan with address LIKE fragment
        features = kc_query_sales_by_zip(query, limit=200)  # still tries LIKE on address
        parcel_index = {}
        sales_index = {}
        for feat in features:
            a = feat["attributes"]
            pin = str(a.get("PIN", ""))
            if pin:
                sales_index[pin] = a
                parcel_index[pin] = {"ADDR_FULL": a.get("address", ""), "APPRLNDVAL": 0, "APPR_IMPR": 0,
                                     "PROPTYPE": "R", "PREUSE_DESC": a.get("Principal_Use", "")}
        if not sales_index:
            print(f"\n  ❌ No data returned for: {query}")
            print("     Tip: Use a 5-digit ZIP code like 98122 for best results")
            return

    results = []

    for pin, parcel in parcel_index.items():
        sale = sales_index.get(pin, {})
        sale_date_ms = sale.get("SaleDate")
        sale_price = sale.get("SalePrice", 0)
        buyer = (sale.get("buyername") or "UNKNOWN").strip()
        seller = (sale.get("Sellername") or "UNKNOWN").strip()
        principal_use = (sale.get("Principal_Use") or parcel.get("PREUSE_DESC") or "").strip()
        address = parcel.get("ADDR_FULL") or sale.get("address", "")
        appr_val = (parcel.get("APPRLNDVAL") or 0) + (parcel.get("APPR_IMPR") or 0)
        proptype = parcel.get("PROPTYPE", "")

        # KEY INSIGHT: Layer 3 only covers last ~2.5 years.
        # Properties ABSENT from Layer 3 = no recent sale = long-term holder candidate.
        # Do NOT skip them — their absence IS the signal.
        if not sale_date_ms:
            # Not in Layer 3 = held 2.5+ years minimum
            # Treat as long-term: use a floor of 3 years for scoring
            NO_RECENT_SALE = True
            tenure = {"years": None, "signal": "LONG_TERM_UNKNOWN",
                      "label": "🔥 5+ years (no recent sale on record)",
                      "sale_date": None}
        else:
            NO_RECENT_SALE = False
            tenure = calculate_tenure(sale_date_ms)

        # Apply filters
        if not NO_RECENT_SALE and tenure["years"] is None:
            continue
        if not NO_RECENT_SALE and tenure["years"] < min_years:
            continue
        if not sale_price and not NO_RECENT_SALE:
            continue
        if no_recent and not NO_RECENT_SALE and tenure["years"] < 2:
            continue
        if prop_type and not matches_property_type_filter(principal_use, prop_type):
            continue
        # Residential filter: skip commercial/industrial if no prop_type filter set
        if not prop_type and proptype not in ("", "R", None):
            continue

        deal = score_deal(tenure["years"])

        results.append({
            "pin": pin,
            "address": address,
            "buyer": buyer,
            "seller": seller,
            "principal_use": principal_use,
            "sale_price": sale_price,
            "assessed_value": appr_val if appr_val > 0 else None,
            "tenure": tenure,
            "deal": deal,
        })

    # Sort: unknown tenure (long-term, no Layer 3 record) first, then by years desc
    results.sort(key=lambda r: r["tenure"]["years"] or 999, reverse=True)
    total = len(results)
    display = results[:limit]

    print()
    print(SEP)
    print(f"🔍 DEAL HUNTER — King County WA | {query} | Min {min_years} yrs")
    print(SEP)
    print(f"Found {total} properties | Showing top {len(display)} by tenure")
    print()

    for i, r in enumerate(display, 1):
        t = r["tenure"]
        d = r["deal"]
        emoji = tenure_emoji(t["signal"])
        flags_str = " | ".join(d["flags"]) if d["flags"] else ""
        assessed_str = fmt_money(r['assessed_value']) if r['assessed_value'] else "N/A"
        print(f"  {i:2d}. {emoji}  {r['address']}")
        held_str = f"{t['years']:.1f} years" if t['years'] is not None else "5+ years (no recent sale)"
        sale_str = f"{fmt_money(r['sale_price'])} ({t['sale_date']})" if r['sale_price'] else "No recent sale on record"
        print(f"       Owner:  {r['buyer']} | Held: {held_str}")
        print(f"       Assessed: {assessed_str} | Last Sale: {sale_str}")
        score_line = f"Score: {d['score']}/100 | {d['rating']}"
        if flags_str:
            score_line += f" | {flags_str}"
        print(f"       {score_line}")
        print()

    # Save to results file
    results_file = os.path.join(WORKSPACE, "knowledge-vault", f"deal_hunter_results_{query}_{int(time.time())}.json")
    with open(results_file, "w") as f:
        json.dump({"query": query, "min_years": min_years, "total": total, "results": display}, f, indent=2, default=str)

    # Log to DB
    try:
        db = get_db()
        db.execute(
            "INSERT INTO search_history (query, county, params, result_count) VALUES (?,?,?,?)",
            (query, "king", json.dumps({"min_years": min_years, "limit": limit, "prop_type": prop_type}), total)
        )
        db.commit()
        db.close()
    except Exception:
        pass

    print(f"📋 To owner intel: python3 pp_deal_hunter.py owner \"<address>\"")
    print(f"📋 To export CSV:  python3 pp_deal_hunter.py export {os.path.basename(results_file)} --csv leads.csv")
    print(f"📄 Results saved:  {results_file}")
    print(SEP)
    print()


def cmd_buybox(args):
    db = get_db()
    subcmd = args.subcmd

    if subcmd == "save":
        name = args.name
        row = {
            "name": name,
            "zip": getattr(args, "zip", None),
            "min_years": getattr(args, "min_years", 5),
            "max_years": getattr(args, "max_years", None),
            "property_type": getattr(args, "property_type", None),
            "min_equity": getattr(args, "min_equity", 0),
            "limit_n": getattr(args, "limit", 25),
            "county": "king",
        }
        db.execute("""
            INSERT OR REPLACE INTO buyboxes (name,zip,min_years,max_years,property_type,min_equity,limit_n,county)
            VALUES (:name,:zip,:min_years,:max_years,:property_type,:min_equity,:limit_n,:county)
        """, row)
        db.commit()
        print(f"\n  ✅ Buy box saved: \"{name}\"")
        print(f"     ZIP: {row['zip']} | Min years: {row['min_years']} | Type: {row['property_type'] or 'all'}")
        print(f"     Run it: python3 pp_deal_hunter.py buybox run \"{name}\"")
        print()

    elif subcmd == "list":
        rows = db.execute("SELECT * FROM buyboxes ORDER BY created_at DESC").fetchall()
        SEP = "━" * 52
        print(f"\n{SEP}")
        print("📦 SAVED BUY BOXES")
        print(SEP)
        if not rows:
            print("  No buy boxes saved yet.")
            print(f"  Create one: python3 pp_deal_hunter.py buybox save \"My Box\" --zip 98122")
        else:
            for r in rows:
                last_run = r["last_run"] or "Never"
                print(f"\n  📌 {r['name']}")
                print(f"     ZIP: {r['zip'] or 'any'} | County: {r['county']} | Min years: {r['min_years']}")
                print(f"     Type: {r['property_type'] or 'all residential'} | Limit: {r['limit_n']}")
                print(f"     Created: {r['created_at'][:10]} | Last run: {last_run}")
        print(f"\n{SEP}\n")

    elif subcmd == "run":
        name = args.name
        row = db.execute("SELECT * FROM buyboxes WHERE name=?", (name,)).fetchone()
        if not row:
            print(f"\n  ❌ Buy box not found: \"{name}\"")
            print(f"     List boxes: python3 pp_deal_hunter.py buybox list")
            return
        print(f"\n  ▶️  Running buy box: \"{name}\" ...")
        # Build synthetic args and call search
        class FakeArgs:
            pass
        fa = FakeArgs()
        fa.query = row["zip"] or "98122"
        fa.min_years = row["min_years"] or 5
        fa.limit = row["limit_n"] or 25
        fa.property_type = row["property_type"]
        fa.no_recent_sale = False
        fa.min_equity = row["min_equity"] or 0
        cmd_search(fa)
        # Update last_run
        db.execute("UPDATE buyboxes SET last_run=datetime('now') WHERE name=?", (name,))
        db.commit()

    db.close()


def cmd_export(args):
    results_json = args.results_json
    csv_out = args.csv

    # Try workspace/knowledge-vault first
    if not os.path.exists(results_json):
        alt = os.path.join(WORKSPACE, "knowledge-vault", results_json)
        if os.path.exists(alt):
            results_json = alt

    if not os.path.exists(results_json):
        print(f"\n  ❌ Results file not found: {args.results_json}")
        return

    with open(results_json) as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        print("  ❌ No results to export.")
        return

    fieldnames = ["address", "owner", "previous_owner", "last_sale_price", "last_sale_date",
                  "tenure_years", "tenure_signal", "deal_score", "deal_rating", "pin"]

    with open(csv_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "address": r.get("address", ""),
                "owner": r.get("buyer", ""),
                "previous_owner": r.get("seller", ""),
                "last_sale_price": r.get("sale_price", ""),
                "last_sale_date": r.get("tenure", {}).get("sale_date", ""),
                "tenure_years": r.get("tenure", {}).get("years", ""),
                "tenure_signal": r.get("tenure", {}).get("signal", ""),
                "deal_score": r.get("deal", {}).get("score", ""),
                "deal_rating": r.get("deal", {}).get("rating", ""),
                "pin": r.get("pin", ""),
            })

    print(f"\n  ✅ Exported {len(results)} leads → {csv_out}")
    print(f"     Ready for skip tracing in BatchSkipTracing, Skip Sherpa, or PropStream")
    print()


def cmd_skiprtrace(args):
    name = args.name
    address = args.address
    cfg = load_config()
    api_key = cfg.get("skip_sherpa_key")

    if not api_key:
        print(f"""
  ⚠️  Skip Sherpa API key not configured.

  HOW TO GET A FREE TEST KEY:
  1. Go to: https://skipsherpa.com
  2. Sign up for free (includes test credits)
  3. Copy your API key from the dashboard

  THEN SAVE IT:
     python3 pp_deal_hunter.py token set skip-sherpa YOUR_KEY_HERE

  Looking up: {name} at {address}
  → Once key is configured, will return phones, emails, and relatives.
""")
        return

    # Skip Sherpa API call
    print(f"\n  🔍 Skip tracing: {name} at {address} ...")
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"name": name, "address": address}
        resp = requests.post("https://api.skipsherpa.com/v1/search", json=payload, headers=headers, timeout=20)

        if resp.status_code == 401:
            print("  ❌ Invalid API key. Run: python3 pp_deal_hunter.py token set skip-sherpa <key>")
            return
        resp.raise_for_status()
        data = resp.json()

        phones = data.get("phones", [])
        emails = data.get("emails", [])
        relatives = data.get("relatives", [])

        SEP = "━" * 48
        print()
        print(SEP)
        print(f"📞 SKIP TRACE — {name}")
        print(SEP)
        print(f"   Address: {address}")
        print()
        if phones:
            print("   📱 PHONES:")
            for p in phones[:5]:
                print(f"      {p.get('number','?')} ({p.get('type','?')})")
        if emails:
            print("   ✉️  EMAILS:")
            for e in emails[:3]:
                print(f"      {e}")
        if relatives:
            print("   👥 RELATIVES:")
            for r in relatives[:3]:
                print(f"      {r}")
        if not phones and not emails:
            print("   ⚠️  No contact info found in Skip Sherpa database.")
        print(SEP)
        print()

    except requests.HTTPError as e:
        print(f"  ❌ Skip Sherpa API error: {e}")


def cmd_token(args):
    if args.service == "skip-sherpa":
        cfg = load_config()
        cfg["skip_sherpa_key"] = args.key
        save_config(cfg)
        print(f"\n  ✅ Skip Sherpa API key saved to config.")
        print(f"     Test it: python3 pp_deal_hunter.py skiprtrace \"OWNER NAME\" \"123 Main St Seattle\"\n")
    else:
        print(f"\n  ❌ Unknown service: {args.service}")
        print("     Supported: skip-sherpa\n")


# ─── Argument Parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pp-deal-hunter",
        description="🏠 Off-Market Deal Finder — King County WA | Kapowsin Business Solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 pp_deal_hunter.py counties
  python3 pp_deal_hunter.py owner "11745 24th Ave NE Seattle WA"
  python3 pp_deal_hunter.py tenure "1234 Main St Seattle WA"
  python3 pp_deal_hunter.py search 98122 --min-years 8 --limit 10
  python3 pp_deal_hunter.py buybox save "KC-Flips" --zip 98122 --min-years 8 --property-type SFR
  python3 pp_deal_hunter.py buybox list
  python3 pp_deal_hunter.py buybox run "KC-Flips"
  python3 pp_deal_hunter.py export results.json --csv leads.csv
  python3 pp_deal_hunter.py skiprtrace "JOHNSON ROBERT" "1234 Main St Seattle"
  python3 pp_deal_hunter.py token set skip-sherpa YOUR_KEY_HERE
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # counties
    sub.add_parser("counties", help="List supported counties and API status")

    # owner
    p_owner = sub.add_parser("owner", help="Full owner intel for one property")
    p_owner.add_argument("address", nargs="+", help="Property address")

    # tenure
    p_tenure = sub.add_parser("tenure", help="Quick ownership duration check")
    p_tenure.add_argument("address", nargs="+", help="Property address")

    # search
    p_search = sub.add_parser("search", help="Scan for motivated sellers by buy box")
    p_search.add_argument("query", help="ZIP code or area (e.g. 98122)")
    p_search.add_argument("--min-years", type=float, default=5, metavar="N",
                          help="Owner held property N+ years (default: 5)")
    p_search.add_argument("--min-equity", type=int, default=0, metavar="N",
                          help="Estimated equity N%+ (default: 0)")
    p_search.add_argument("--limit", type=int, default=25, metavar="N",
                          help="Max results to show (default: 25)")
    p_search.add_argument("--property-type", choices=["SFR", "MFR", "CONDO", "LAND"],
                          metavar="TYPE", help="Filter: SFR, MFR, CONDO, LAND")
    p_search.add_argument("--no-recent-sale", action="store_true",
                          help="Exclude properties sold in last 2 years")

    # buybox
    p_bb = sub.add_parser("buybox", help="Save and run buy boxes")
    bb_sub = p_bb.add_subparsers(dest="subcmd", metavar="subcmd")
    bb_sub.required = True

    p_bb_save = bb_sub.add_parser("save", help="Save a buy box")
    p_bb_save.add_argument("name", help="Buy box name")
    p_bb_save.add_argument("--zip", help="ZIP code")
    p_bb_save.add_argument("--min-years", type=float, default=5)
    p_bb_save.add_argument("--max-years", type=float, default=None)
    p_bb_save.add_argument("--property-type", choices=["SFR", "MFR", "CONDO", "LAND"])
    p_bb_save.add_argument("--min-equity", type=int, default=0)
    p_bb_save.add_argument("--limit", type=int, default=25)

    bb_sub.add_parser("list", help="List saved buy boxes")

    p_bb_run = bb_sub.add_parser("run", help="Run a saved buy box")
    p_bb_run.add_argument("name", help="Buy box name")

    # export
    p_export = sub.add_parser("export", help="Export search results to CSV")
    p_export.add_argument("results_json", help="Path to results JSON file")
    p_export.add_argument("--csv", required=True, help="Output CSV path")

    # skiprtrace
    p_skip = sub.add_parser("skiprtrace", help="Skip trace via Skip Sherpa API")
    p_skip.add_argument("name", help="Owner name (e.g. 'JOHNSON ROBERT')")
    p_skip.add_argument("address", help="Property address")

    # token
    p_token = sub.add_parser("token", help="Manage API tokens")
    token_sub = p_token.add_subparsers(dest="token_action", metavar="action")
    token_sub.required = True
    p_token_set = token_sub.add_parser("set", help="Set an API token")
    p_token_set.add_argument("service", help="Service name (e.g. skip-sherpa)")
    p_token_set.add_argument("key", help="API key value")

    return parser


# ─── Main ─────────────────────────────────────────────────────────────────────

DISPATCH = {
    "counties": cmd_counties,
    "owner": cmd_owner,
    "tenure": cmd_tenure,
    "search": cmd_search,
    "buybox": cmd_buybox,
    "export": cmd_export,
    "skiprtrace": cmd_skiprtrace,
    "token": cmd_token,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    fn = DISPATCH.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
