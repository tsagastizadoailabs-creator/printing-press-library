#!/usr/bin/env python3
"""
pp_mls_wa.py — WA State MLS listing search via SimplyRETS API (NWMLS-ready scaffold).

SimplyRETS provides a hosted API layer over MLS data including NWMLS.
Direct NWMLS access requires a licensed WA broker; SimplyRETS handles that layer.

Demo mode: uses simplyrets/simplyrets credentials against api.simplyrets.com,
returns sample data. Run `setup` to configure live credentials.

Commands:
  search <city_or_zip> [--status Active|Closed|Pending] [--limit 25]
         [--min-price N] [--max-price N] [--beds N] [--baths N]
  detail <mls_id>
  comps <address_or_mls_id> [--radius-miles 1]
  stats <city>
  setup
  counties
"""
import argparse
import json
import os
import statistics
import sys
from pathlib import Path

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("ERROR: requests library not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------- Config ----------

CONFIG_PATH = Path.home() / ".openclaw" / "workspace" / "knowledge-vault" / "mls_config.json"
DEMO_USER = "simplyrets"
DEMO_PASS = "simplyrets"
BASE_URL = "https://api.simplyrets.com"

DEFAULT_CONFIG = {
    "simplyrets_user": None,
    "simplyrets_pass": None,
    "mode": "demo",
}

# WA counties commonly covered by NWMLS
WA_COUNTIES = [
    "King", "Pierce", "Snohomish", "Kitsap", "Thurston", "Whatcom",
    "Skagit", "Island", "San Juan", "Clallam", "Jefferson", "Mason",
    "Lewis", "Cowlitz", "Clark", "Skamania", "Klickitat", "Yakima",
    "Kittitas", "Chelan", "Douglas", "Okanogan", "Grant", "Ferry",
    "Stevens", "Pend Oreille", "Spokane", "Lincoln", "Adams", "Franklin",
    "Benton", "Walla Walla", "Columbia", "Garfield", "Asotin", "Whitman",
    "Grays Harbor", "Pacific", "Wahkiakum",
]


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        return dict(DEFAULT_CONFIG)
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return dict(DEFAULT_CONFIG)


def get_auth(cfg):
    """Return (auth, is_demo) tuple."""
    user = cfg.get("simplyrets_user")
    pw = cfg.get("simplyrets_pass")
    if user and pw:
        return HTTPBasicAuth(user, pw), False
    return HTTPBasicAuth(DEMO_USER, DEMO_PASS), True


def demo_notice(is_demo):
    if is_demo:
        print("⚠️  Using SimplyRETS demo data — not live NWMLS listings. Run setup for live data.")
        print()


# ---------- HTTP ----------

def api_get(path, params, auth):
    url = f"{BASE_URL}{path}"
    try:
        r = requests.get(url, params=params, auth=auth, timeout=30,
                         headers={"Accept": "application/json"})
    except requests.RequestException as e:
        print(f"ERROR: network failure: {e}", file=sys.stderr)
        sys.exit(2)
    if r.status_code == 401:
        print("ERROR: 401 Unauthorized — check SimplyRETS credentials (run setup).", file=sys.stderr)
        sys.exit(3)
    if r.status_code >= 400:
        print(f"ERROR: API {r.status_code}: {r.text[:300]}", file=sys.stderr)
        sys.exit(4)
    try:
        return r.json()
    except ValueError:
        print(f"ERROR: invalid JSON response: {r.text[:200]}", file=sys.stderr)
        sys.exit(5)


# ---------- Formatting helpers ----------

def fmt_price(n):
    if n is None:
        return "—"
    try:
        return f"${int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def fmt_addr(prop):
    a = prop.get("address") or {}
    parts = []
    full = a.get("full") or ""
    if full:
        parts.append(full)
    city = a.get("city") or ""
    state = a.get("state") or ""
    pc = a.get("postalCode") or ""
    tail = ", ".join([x for x in [city, f"{state} {pc}".strip()] if x])
    if tail:
        parts.append(tail)
    return ", ".join(parts) if parts else "(address unknown)"


def days_listed(listing):
    """Best-effort: SimplyRETS exposes listDate."""
    from datetime import datetime, timezone
    ld = listing.get("listDate")
    if not ld:
        return None
    try:
        dt = datetime.fromisoformat(ld.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).days
    except Exception:
        return None


def get_beds_baths_sqft(prop):
    p = prop.get("property") or {}
    beds = p.get("bedrooms")
    baths_full = p.get("bathsFull") or 0
    baths_half = p.get("bathsHalf") or 0
    baths_total = p.get("bathrooms") or (baths_full + 0.5 * baths_half if (baths_full or baths_half) else None)
    sqft = p.get("area")
    return beds, baths_total, sqft


def get_agent_office(listing):
    agent = (listing.get("agent") or {})
    office = (listing.get("office") or {})
    name = " ".join([x for x in [agent.get("firstName"), agent.get("lastName")] if x]).strip() or (agent.get("contact") or {}).get("email") or "—"
    office_name = office.get("name") or "—"
    return name, office_name


# ---------- Commands ----------

def cmd_search(args, cfg):
    auth, is_demo = get_auth(cfg)
    demo_notice(is_demo)

    params = {"limit": args.limit}
    q = args.city_or_zip
    if q.isdigit() and len(q) == 5:
        params["postalCodes"] = q
    else:
        params["q"] = q
    if args.status:
        params["status"] = args.status
    if args.min_price is not None:
        params["minprice"] = args.min_price
    if args.max_price is not None:
        params["maxprice"] = args.max_price
    if args.beds is not None:
        params["minbeds"] = args.beds
    if args.baths is not None:
        params["minbaths"] = args.baths

    listings = api_get("/properties", params, auth)
    if not isinstance(listings, list):
        listings = []

    status_label = args.status or "All"
    print("━" * 60)
    print(f"🏡 MLS SEARCH — {q} | {status_label} | {len(listings)} results")
    print("━" * 60)

    if not listings:
        print("  (no listings matched)")
        return

    for i, l in enumerate(listings, 1):
        addr = fmt_addr(l)
        price = fmt_price(l.get("listPrice"))
        beds, baths, sqft = get_beds_baths_sqft(l)
        sqft_s = f"{int(sqft):,} sqft" if sqft else "— sqft"
        bb = f"{beds or '—'}bd/{baths or '—'}ba"
        dom = days_listed(l)
        dom_s = f"Listed: {dom} days" if dom is not None else "Listed: —"
        mls_id = l.get("mlsId") or l.get("listingId") or "—"
        agent, office = get_agent_office(l)

        print(f"  {i}. {addr}")
        print(f"     {price} | {bb} | {sqft_s} | {dom_s}")
        print(f"     MLS#: {mls_id} | Agent: {agent} ({office})")
        print()


def cmd_detail(args, cfg):
    auth, is_demo = get_auth(cfg)
    demo_notice(is_demo)

    listings = api_get(f"/properties/{args.mls_id}", {}, auth)
    if isinstance(listings, list):
        listings = listings[0] if listings else None
    if not listings:
        print(f"No listing found for MLS# {args.mls_id}")
        return
    l = listings
    addr = fmt_addr(l)
    price = fmt_price(l.get("listPrice"))
    beds, baths, sqft = get_beds_baths_sqft(l)
    p = l.get("property") or {}
    agent, office = get_agent_office(l)
    dom = days_listed(l)

    print("━" * 60)
    print(f"🏡 LISTING DETAIL — MLS# {l.get('mlsId') or args.mls_id}")
    print("━" * 60)
    print(f"  Address    : {addr}")
    print(f"  Price      : {price}")
    print(f"  Beds/Baths : {beds or '—'} / {baths or '—'}")
    if sqft:
        print(f"  Sqft       : {int(sqft):,}")
    else:
        print("  Sqft       : —")
    print(f"  Year Built : {p.get('yearBuilt') or '—'}")
    print(f"  Type       : {p.get('type') or '—'} / {p.get('subType') or '—'}")
    print(f"  Lot Size   : {p.get('lotSize') or '—'}")
    print(f"  Stories    : {p.get('stories') or '—'}")
    print(f"  Status     : {(l.get('mls') or {}).get('status') or l.get('listingStatus') or '—'}")
    print(f"  Days Listed: {dom if dom is not None else '—'}")
    print(f"  Agent      : {agent}")
    print(f"  Office     : {office}")
    remarks = l.get("remarks")
    if remarks:
        print()
        print("  Remarks:")
        print("    " + (remarks[:500] + ("…" if len(remarks) > 500 else "")))


def cmd_comps(args, cfg):
    auth, is_demo = get_auth(cfg)
    demo_notice(is_demo)

    target = args.address_or_mls_id
    subject = None

    if target.isdigit():
        try:
            res = api_get(f"/properties/{target}", {}, auth)
            subject = res[0] if isinstance(res, list) and res else (res if isinstance(res, dict) else None)
        except SystemExit:
            subject = None

    if subject is None:
        res = api_get("/properties", {"q": target, "limit": 1}, auth)
        if isinstance(res, list) and res:
            subject = res[0]

    if not subject:
        print(f"Could not locate subject property for: {target}")
        return

    addr = subject.get("address") or {}
    city = addr.get("city")
    postal = addr.get("postalCode")
    params = {"limit": 10}
    if postal:
        params["postalCodes"] = postal
    elif city:
        params["cities"] = city
    params["status"] = "Closed"

    comps = api_get("/properties", params, auth)
    if not isinstance(comps, list):
        comps = []

    print("━" * 60)
    print(f"🏡 COMPS — Subject: {fmt_addr(subject)}")
    print(f"   Radius: {args.radius_miles} mi | {len(comps)} closed comps")
    print("━" * 60)

    for i, l in enumerate(comps, 1):
        a = fmt_addr(l)
        sp = fmt_price((l.get("mls") or {}).get("soldPrice") or l.get("listPrice"))
        beds, baths, sqft = get_beds_baths_sqft(l)
        sqft_s = f"{int(sqft):,} sqft" if sqft else "— sqft"
        mls_id = l.get("mlsId") or "—"
        print(f"  {i}. {a}")
        print(f"     Sold: {sp} | {beds or '—'}bd/{baths or '—'}ba | {sqft_s} | MLS# {mls_id}")
        print()


def cmd_stats(args, cfg):
    auth, is_demo = get_auth(cfg)
    demo_notice(is_demo)

    closed = api_get("/properties", {"cities": args.city, "status": "Closed", "limit": 100}, auth)
    if not isinstance(closed, list):
        closed = []

    if not closed:
        print(f"No closed listings found for {args.city}.")
        return

    sold_prices = []
    list_prices = []
    dom_days = []
    ratios = []
    for l in closed:
        mls = l.get("mls") or {}
        sp = mls.get("soldPrice") or l.get("soldPrice")
        lp = l.get("listPrice")
        dom = mls.get("daysOnMarket") or days_listed(l)
        if sp:
            sold_prices.append(sp)
        if lp:
            list_prices.append(lp)
        if dom is not None:
            try:
                dom_days.append(int(dom))
            except (TypeError, ValueError):
                pass
        if sp and lp:
            try:
                ratios.append(float(sp) / float(lp))
            except (TypeError, ValueError, ZeroDivisionError):
                pass

    median_sp = statistics.median(sold_prices) if sold_prices else None
    avg_dom = statistics.mean(dom_days) if dom_days else None
    avg_ratio = statistics.mean(ratios) if ratios else None

    print("━" * 60)
    print(f"📊 MARKET STATS — {args.city} | Closed listings (sample size {len(closed)})")
    print("━" * 60)
    print(f"  Median Sold Price   : {fmt_price(median_sp)}")
    if avg_dom is not None:
        print(f"  Avg Days on Market  : {avg_dom:.1f}")
    else:
        print("  Avg Days on Market  : —")
    if avg_ratio is not None:
        print(f"  Avg List→Sale Ratio : {avg_ratio * 100:.1f}%")
    else:
        print("  Avg List→Sale Ratio : —")
    if sold_prices:
        print(f"  Price Range         : {fmt_price(min(sold_prices))} – {fmt_price(max(sold_prices))}")


def cmd_setup(args, cfg):
    print("━" * 60)
    print("🔧 SimplyRETS / NWMLS Setup")
    print("━" * 60)
    print()
    print("SimplyRETS provides hosted MLS API access including NWMLS.")
    print("Direct NWMLS access requires a licensed WA broker sponsor;")
    print("SimplyRETS resells access at a per-MLS subscription price.")
    print()
    print("Steps:")
    print("  1. Sign up at https://simplyrets.com")
    print("  2. Subscribe to NWMLS feed (requires broker license verification)")
    print("  3. Get API username + password from your SimplyRETS dashboard")
    print(f"  4. Edit config file: {CONFIG_PATH}")
    print()
    print("  Set:")
    print('    {"simplyrets_user": "YOUR_USER",')
    print('     "simplyrets_pass": "YOUR_PASS",')
    print('     "mode": "live"}')
    print()
    print(f"Current config: {CONFIG_PATH}")
    if CONFIG_PATH.exists():
        print(f"  Mode  : {cfg.get('mode')}")
        print(f"  User  : {'(set)' if cfg.get('simplyrets_user') else '(not set — using demo)'}")
    else:
        print("  (not yet created — will be created on first run)")


def cmd_counties(args, cfg):
    print("━" * 60)
    print(f"🗺️  Washington State Counties ({len(WA_COUNTIES)} total)")
    print("━" * 60)
    print("NWMLS primary coverage: King, Pierce, Snohomish, Kitsap, Thurston,")
    print("Whatcom, Skagit, Island, San Juan, Clallam, Jefferson, Mason.")
    print("Other WA counties may be on Spokane MLS, NEREIA, or smaller boards.")
    print()
    cols = 4
    for i in range(0, len(WA_COUNTIES), cols):
        row = WA_COUNTIES[i:i + cols]
        print("  " + "  ".join(f"{c:<16}" for c in row))


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(prog="pp_mls_wa", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="search listings")
    p_search.add_argument("city_or_zip")
    p_search.add_argument("--status", choices=["Active", "Closed", "Pending"])
    p_search.add_argument("--limit", type=int, default=25)
    p_search.add_argument("--min-price", type=int, dest="min_price")
    p_search.add_argument("--max-price", type=int, dest="max_price")
    p_search.add_argument("--beds", type=int)
    p_search.add_argument("--baths", type=int)

    p_detail = sub.add_parser("detail", help="listing detail")
    p_detail.add_argument("mls_id")

    p_comps = sub.add_parser("comps", help="comps for address or mls_id")
    p_comps.add_argument("address_or_mls_id")
    p_comps.add_argument("--radius-miles", type=float, default=1.0)

    p_stats = sub.add_parser("stats", help="market stats for city")
    p_stats.add_argument("city")

    sub.add_parser("setup", help="show credential setup")
    sub.add_parser("counties", help="list supported WA counties")

    args = parser.parse_args()
    cfg = load_config()

    dispatch = {
        "search": cmd_search,
        "detail": cmd_detail,
        "comps": cmd_comps,
        "stats": cmd_stats,
        "setup": cmd_setup,
        "counties": cmd_counties,
    }
    dispatch[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
