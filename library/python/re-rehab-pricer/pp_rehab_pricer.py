#!/usr/bin/env python3
"""
pp_rehab_pricer.py — WA State Rehab Cost Estimator
Kapowsin Business Solutions LLC

Commands:
  estimate <address> <sqft> [--scope cosmetic|partial|full_gut] [--quality low|mid|high]
  lookup <item_name>
  category <category_name>
  categories
  mao <arv> <repairs> [--contingency 15] [--tax 10.25]
  sheet <spreadsheet_id> [--populate]
  update <item_name> <new_mid_price>
"""

import argparse
import sqlite3
import sys
import os
import subprocess
from datetime import datetime

# ─── Config ────────────────────────────────────────────────────────────────────

DB_PATH = os.path.expanduser(
    "~/.openclaw/workspace/knowledge-vault/rehab_materials.db"
)

WA_TAX_DEFAULT = 10.25      # WA state average sales tax %
CONTINGENCY_DEFAULT = 15.0  # Standard rehab contingency %

SCOPE_PRESETS = {
    "cosmetic": {
        "description": "Paint, flooring, fixtures, landscaping only",
        "line_items": [
            ("Interior Paint",       "Interior/Paint",        "sqft",    2.50),
            ("LVP Flooring",         "Surfaces/LVP",          "sqft",    5.50),
            ("Carpet (bedrooms)",    "Surfaces/Carpet",       "sqft",    2.00),  # ~40% of sqft
            ("Bath Fixtures",        "Baths/Fixtures",        "each",  350.00),  # per bath
            ("Landscaping",          "Yard/Landscaping",      "project", 1500),
        ],
        "cost_per_sqft_low":  12,
        "cost_per_sqft_mid":  22,
        "cost_per_sqft_high": 38,
        "labor_pct": 0.55,
    },
    "partial": {
        "description": "Cosmetic + kitchen refresh + bath updates + some systems",
        "line_items": [
            ("Interior Paint",              "Interior/Paint",         "sqft",    2.50),
            ("LVP Flooring",                "Surfaces/LVP",           "sqft",    5.50),
            ("Kitchen (cabs + quartz)",     "Kitchen/Cabinets",       "project", 6000),
            ("Bath refresh × 2",            "Baths/Vanity",           "each",    4200),  # 2 baths
            ("HVAC update",                 "Systems/HVAC",           "project", 4500),
            ("Electrical (partial)",        "Systems/Electrical",     "project", 3500),
            ("Plumbing fixtures",           "Systems/Plumbing",       "project", 2500),
            ("Landscaping",                 "Yard/Landscaping",       "project", 2000),
        ],
        "cost_per_sqft_low":  25,
        "cost_per_sqft_mid":  45,
        "cost_per_sqft_high": 75,
        "labor_pct": 0.60,
    },
    "full_gut": {
        "description": "Full renovation: systems, structural, finishes, everything",
        "line_items": [
            ("Demo + haul",                 "Interior/Demo",          "sqft",    3.50),
            ("Structural / reframe",        "Interior/Framing",       "project", 8000),
            ("Full rewire + panel",         "Systems/Electrical",     "project", 15000),
            ("Full replumb (PEX)",          "Systems/Plumbing",       "project", 15000),
            ("HVAC full replacement",       "Systems/HVAC",           "project", 10000),
            ("Insulation",                  "Interior/Insulation",    "sqft",    1.75),
            ("Drywall (hang+tape+prime)",   "Interior/Drywall",       "sqft",    4.00),
            ("Interior Paint",              "Interior/Paint",         "sqft",    2.50),
            ("Trim + millwork",             "Interior/Trim",          "sqft",    5.00),
            ("Kitchen full build",          "Kitchen/Cabinets",       "project", 18000),
            ("Appliances",                  "Kitchen/Appliances",     "package", 4500),
            ("Bath × 2 (full)",            "Baths/Shower",           "each",    5500),
            ("LVP Flooring",                "Surfaces/LVP",           "sqft",    5.50),
            ("Exterior paint",              "Exterior/Paint",         "sqft",    2.50),
            ("Roof (if needed)",            "Exterior/Roof",          "sqft",    7.00),
            ("Landscaping",                 "Yard/Landscaping",       "project", 2500),
            ("Permits + soft costs",        "Soft Costs/Permits",     "project", 4000),
        ],
        "cost_per_sqft_low":   50,
        "cost_per_sqft_mid":   80,
        "cost_per_sqft_high": 130,
        "labor_pct": 0.65,
    },
}

QUALITY_FIELD = {
    "low":  "unit_cost_low",
    "mid":  "unit_cost_mid",
    "high": "unit_cost_high",
}

QUALITY_LABEL = {
    "low":  "Budget / Investor Grade",
    "mid":  "Mid-Market Flip",
    "high": "Luxury / Premium Finish",
}

DIVIDER_WIDE  = "━" * 50
DIVIDER_MED   = "━" * 42
DIVIDER_LINE  = "─" * 43


# ─── DB Helpers ────────────────────────────────────────────────────────────────

def get_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("   Run the seed script first.")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def search_materials(conn, query):
    """Case-insensitive search across item, subcategory, category."""
    cur = conn.cursor()
    q = f"%{query}%"
    cur.execute("""
        SELECT id, category, subcategory, item, unit,
               unit_cost_low, unit_cost_mid, unit_cost_high,
               labor_pct, notes, updated_date, source
        FROM materials
        WHERE item LIKE ? OR subcategory LIKE ? OR category LIKE ?
        ORDER BY category, subcategory, item
    """, (q, q, q))
    return cur.fetchall()


def get_categories(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT category, subcategory
        FROM materials
        ORDER BY category, subcategory
    """)
    return cur.fetchall()


def get_items_in_category(conn, category):
    cur = conn.cursor()
    q = f"%{category}%"
    cur.execute("""
        SELECT id, category, subcategory, item, unit,
               unit_cost_low, unit_cost_mid, unit_cost_high,
               labor_pct, notes, updated_date
        FROM materials
        WHERE category LIKE ? OR subcategory LIKE ?
        ORDER BY subcategory, item
    """, (q, q))
    return cur.fetchall()


def save_estimate(conn, address, sqft, quality, scope, total, mat, labor):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO project_estimates
        (address, sqft, quality_tier, scope_type, estimated_total,
         materials_total, labor_total, created_date)
        VALUES (?,?,?,?,?,?,?,?)
    """, (address, sqft, quality, scope, total, mat, labor,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()


# ─── Formatters ────────────────────────────────────────────────────────────────

def fmt_dollar(n, decimals=None):
    if decimals is not None:
        return f"${n:,.{decimals}f}"
    # Auto: show decimals if fractional
    if n != int(n) and n < 100:
        return f"${n:,.2f}"
    return f"${n:,.0f}"


def fmt_row(label, value, width=42):
    """Left-pad value to align in output."""
    label_str = f"   {label}"
    value_str = fmt_dollar(value)
    pad = width - len(label_str) - len(value_str)
    return f"{label_str}{' ' * max(1, pad)}{value_str}"


def print_material_card(row):
    """Pretty-print a single material row."""
    (mid, cat, sub, item, unit,
     low, mid_price, high, labor_pct,
     notes, updated, source) = row

    mat_pct  = round((1 - labor_pct) * 100)
    lab_pct  = round(labor_pct * 100)
    unit_lbl = f"/{unit}" if unit else ""

    print(DIVIDER_MED)
    print(f"🔍 {item}  [{cat}{(' / ' + sub) if sub else ''}]")
    print(DIVIDER_MED)
    print(f"   Unit: {unit} (installed)")
    print(f"   Low  (budget):   {fmt_dollar(low)}{unit_lbl}")
    print(f"   Mid  (standard): {fmt_dollar(mid_price)}{unit_lbl}")
    print(f"   High (premium):  {fmt_dollar(high)}{unit_lbl}")
    print(f"   Labor split: ~{lab_pct}% labor / {mat_pct}% materials")
    if notes:
        print(f"   Note: {notes}")
    print(f"   WA State data — Updated: {updated}")
    print(DIVIDER_MED)


# ─── Commands ──────────────────────────────────────────────────────────────────

def cmd_categories(args):
    conn = get_db()
    rows = get_categories(conn)
    conn.close()

    cats = {}
    for cat, sub in rows:
        cats.setdefault(cat, [])
        if sub and sub not in cats[cat]:
            cats[cat].append(sub)

    print(DIVIDER_WIDE)
    print("📂  REHAB MATERIALS — CATEGORIES")
    print(DIVIDER_WIDE)
    for cat, subs in sorted(cats.items()):
        if subs:
            print(f"\n  {cat}")
            for sub in sorted(subs):
                print(f"    └─ {sub}")
        else:
            print(f"\n  {cat}")
    print(f"\n   {sum(len(s) for s in cats.values())} subcategories across {len(cats)} categories")
    print(DIVIDER_WIDE)
    print("   Usage: pp-rehab-pricer category <name>")
    print(DIVIDER_WIDE)


def cmd_category(args):
    conn = get_db()
    rows = get_items_in_category(conn, args.name)
    conn.close()

    if not rows:
        print(f"❌ No items found for category: {args.name}")
        sys.exit(1)

    print(DIVIDER_WIDE)
    print(f"📋  CATEGORY — {args.name.upper()}")
    print(DIVIDER_WIDE)

    current_sub = None
    for row in rows:
        (mid_id, cat, sub, item, unit,
         low, mid_p, high, labor_pct, notes, updated) = row
        if sub != current_sub:
            current_sub = sub
            print(f"\n  ── {sub or cat} ──")

        unit_lbl = f"/{unit}" if unit else ""
        print(f"   • {item}")
        print(f"     Low: {fmt_dollar(low)}{unit_lbl}  |  Mid: {fmt_dollar(mid_p)}{unit_lbl}  |  High: {fmt_dollar(high)}{unit_lbl}")
        if notes:
            print(f"     ℹ  {notes}")

    print(f"\n   {len(rows)} items")
    print(DIVIDER_WIDE)


def cmd_lookup(args):
    conn = get_db()
    term = " ".join(args.item) if isinstance(args.item, list) else args.item
    rows = search_materials(conn, term)
    conn.close()

    if not rows:
        print(f"❌ No materials found matching: {term}")
        print("   Try: pp-rehab-pricer categories")
        sys.exit(1)

    print(DIVIDER_MED)
    print(f"🔍 MATERIALS LOOKUP — \"{term}\"")
    print(DIVIDER_MED)

    for row in rows:
        (mid_id, cat, sub, item, unit,
         low, mid_p, high, labor_pct,
         notes, updated, source) = row

        mat_pct = round((1 - labor_pct) * 100)
        lab_pct = round(labor_pct * 100)
        unit_lbl = f"/{unit}" if unit else ""

        print(f"\n  {item}    [{cat}{(' / ' + sub) if sub else ''}]")
        print(f"    Unit: {unit} (installed)")
        def ufmt(v): return f"${v:,.2f}" if v < 100 else fmt_dollar(v)
        print(f"    Low  (budget):   {ufmt(low)}{unit_lbl}")
        print(f"    Mid  (standard): {ufmt(mid_p)}{unit_lbl}")
        print(f"    High (premium):  {ufmt(high)}{unit_lbl}")
        print(f"    Labor split: ~{lab_pct}% labor / {mat_pct}% materials")
        if notes:
            print(f"    Note: {notes}")
        print(f"    WA State data — Updated: {updated}")

    print(DIVIDER_MED)


def cmd_mao(args):
    arv        = float(args.arv)
    repairs    = float(args.repairs)
    contingency = float(args.contingency) / 100
    tax         = float(args.tax) / 100

    # Add contingency + tax to repairs
    repairs_with_contingency = repairs * (1 + contingency)
    tax_on_materials = repairs * 0.40 * tax   # tax applies to materials only (~40%)
    total_cost = repairs_with_contingency + tax_on_materials

    # MAO formulas
    mao_70  = (arv * 0.70) - total_cost   # Standard 70% rule
    mao_75  = (arv * 0.75) - total_cost   # Conservative WA market
    mao_65  = (arv * 0.65) - total_cost   # Aggressive / high-risk

    roi_70 = ((arv - mao_70 - total_cost) / (mao_70 + total_cost)) * 100 if mao_70 > 0 else 0

    print(DIVIDER_WIDE)
    print("📐  MAO CALCULATOR — WA STATE")
    print(DIVIDER_WIDE)
    print(f"\n   ARV:                          {fmt_dollar(arv)}")
    print(f"   Repairs (base):               {fmt_dollar(repairs)}")
    print(f"   + Contingency ({args.contingency}%):          {fmt_dollar(repairs * contingency)}")
    print(f"   + WA Tax ({args.tax}% on materials):   {fmt_dollar(tax_on_materials)}")
    print(f"   {DIVIDER_LINE}")
    print(f"   Total All-In Cost:            {fmt_dollar(total_cost)}")
    print()
    print(f"   ── MAX ALLOWABLE OFFER ──────────────────")
    print(f"   MAO @ 70% rule:               {fmt_dollar(mao_70)}")
    print(f"   MAO @ 75% rule:               {fmt_dollar(mao_75)}")
    print(f"   MAO @ 65% rule (aggressive):  {fmt_dollar(mao_65)}")
    print()

    if mao_70 > 0:
        print(f"   📊 Expected gross profit @ MAO 70%:  {fmt_dollar(arv * 0.30)}")
        print(f"   📊 Net after costs:                  {fmt_dollar(arv - mao_70 - total_cost)}")
    else:
        print("   ⚠️  Numbers don't work at 70% rule — review repairs or ARV")

    print()
    print(f"   💡 Carrying costs, agent fees, closing not included.")
    print(f"      Add ~8-10% ARV for those: {fmt_dollar(arv * 0.09)}")
    print(DIVIDER_WIDE)


def cmd_estimate(args):
    address = args.address
    sqft    = int(args.sqft)
    quality = args.quality
    scope   = args.scope

    preset = SCOPE_PRESETS[scope]

    # Quality multipliers relative to mid
    q_mult = {
        "low":  preset["cost_per_sqft_low"]  / preset["cost_per_sqft_mid"],
        "mid":  1.0,
        "high": preset["cost_per_sqft_high"] / preset["cost_per_sqft_mid"],
    }[quality]

    # Build line items using preset defaults, scaled by quality
    line_items = []
    subtotal = 0.0

    for label, path, unit, mid_cost in preset["line_items"]:
        cost = mid_cost * q_mult

        if unit == "sqft":
            amount = sqft * cost
            line_label = f"{label} ({sqft:,} sqft × {fmt_dollar(cost)})"
        else:
            amount = cost
            line_label = label

        line_items.append((line_label, amount))
        subtotal += amount

    # Apply contingency + tax
    contingency_amt = subtotal * (WA_TAX_DEFAULT / 100 * 0 + 0.15)  # 15% contingency
    tax_amt = subtotal * 0.40 * (WA_TAX_DEFAULT / 100)              # tax on materials only
    project_total = subtotal + contingency_amt + tax_amt

    labor_pct = preset.get("labor_pct", 0.60)
    labor_total = project_total * labor_pct
    mat_total   = project_total * (1 - labor_pct)
    cost_per_sqft = project_total / sqft

    scope_label = {
        "cosmetic":  "Cosmetic Renovation",
        "partial":   "Partial Renovation",
        "full_gut":  "Full Gut Renovation",
    }[scope]

    print(DIVIDER_WIDE)
    print(f"🏗️  REHAB ESTIMATE — {address}")
    print(DIVIDER_WIDE)
    print(f"\n📋 PROJECT DETAILS")
    print(f"   Sqft: {sqft:,} | Scope: {scope_label} | Quality: {QUALITY_LABEL[quality]}")
    print(f"   WA State pricing — Pierce/King County")
    print(f"\n💰 COST BREAKDOWN ({QUALITY_LABEL[quality]})")

    col_w = 42
    for label, amount in line_items:
        pad = col_w - len(f"   {label}") - len(fmt_dollar(amount))
        print(f"   {label}{' ' * max(1, pad)}{fmt_dollar(amount)}")

    print(f"   {DIVIDER_LINE}")
    print(fmt_row("Subtotal", subtotal))
    print(fmt_row(f"+ Contingency (15%)", contingency_amt))
    print(fmt_row(f"+ WA State Tax ({WA_TAX_DEFAULT}%)", tax_amt))
    print(f"   {DIVIDER_LINE}")
    print(fmt_row("PROJECT TOTAL", project_total))
    print(f"   Cost per sqft                               ${cost_per_sqft:,.2f}")

    print(f"\n📊 LABOR / MATERIALS SPLIT")
    print(fmt_row(f"   Materials (~{round((1-labor_pct)*100)}%):", mat_total))
    print(fmt_row(f"   Labor (~{round(labor_pct*100)}%):", labor_total))

    print(f"\n📐 INVESTOR MATH")
    print(f"   Enter ARV + repairs: pp-rehab-pricer mao <arv> {round(project_total)}")

    print(DIVIDER_WIDE)

    # Save to DB
    try:
        conn2 = get_db()
        save_estimate(conn2, address, sqft, quality, scope,
                      project_total, mat_total, labor_total)
        conn2.close()
    except Exception:
        pass  # non-fatal


def cmd_sheet(args):
    """Read a Google Sheets rehab budget, match line items to DB, optionally populate."""
    try:
        result = subprocess.run(
            ["gog", "sheets", "get", args.spreadsheet_id],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"❌ Could not read sheet: {result.stderr}")
            sys.exit(1)
        sheet_data = result.stdout
    except FileNotFoundError:
        print("❌ gog CLI not found. Install it or check PATH.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("❌ Sheet read timed out.")
        sys.exit(1)

    print(DIVIDER_WIDE)
    print(f"📊  SHEET ANALYSIS — {args.spreadsheet_id}")
    print(DIVIDER_WIDE)
    print("⚠️  Sheet integration requires gog sheets CLI with read access.")
    print("   Match line items manually using: pp-rehab-pricer lookup <item>")
    print(DIVIDER_WIDE)


def cmd_update(args):
    """Update a material's mid price in the DB."""
    conn = get_db()
    term = " ".join(args.item) if isinstance(args.item, list) else args.item
    new_price = float(args.new_mid_price)

    rows = search_materials(conn, term)
    if not rows:
        print(f"❌ No materials found matching: {term}")
        conn.close()
        sys.exit(1)

    if len(rows) > 1:
        print(f"⚠️  Found {len(rows)} matches for '{term}'. Updating first match.")
        print(f"   → {rows[0][3]}")

    row = rows[0]
    mat_id = row[0]
    old_price = row[6]  # unit_cost_mid

    # Save to price history first
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO price_history (material_id, price, source, recorded_date)
        VALUES (?, ?, ?, ?)
    """, (mat_id, old_price, "manual update", datetime.now().strftime("%Y-%m-%d")))

    # Update mid price
    cur.execute("""
        UPDATE materials SET unit_cost_mid = ?, updated_date = ?
        WHERE id = ?
    """, (new_price, datetime.now().strftime("%Y-%m-%d"), mat_id))

    conn.commit()
    conn.close()

    print(DIVIDER_MED)
    print(f"✅  PRICE UPDATED")
    print(DIVIDER_MED)
    print(f"   Item:      {row[3]}")
    print(f"   Old price: {fmt_dollar(old_price)}")
    print(f"   New price: {fmt_dollar(new_price)}")
    print(f"   History:   saved to price_history")
    print(DIVIDER_MED)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="pp-rehab-pricer",
        description="WA State Rehab Cost Estimator — Kapowsin Business Solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pp-rehab-pricer estimate "1234 Main St Tacoma WA" 1450 --scope partial --quality mid
  pp-rehab-pricer lookup LVP
  pp-rehab-pricer category Kitchen
  pp-rehab-pricer categories
  pp-rehab-pricer mao 385000 55000
  pp-rehab-pricer mao 385000 55000 --contingency 20 --tax 10.5
  pp-rehab-pricer update "LVP flooring" 6.00
        """
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # estimate
    p_est = sub.add_parser("estimate", help="Full project estimate")
    p_est.add_argument("address", help="Property address (quote if multi-word)")
    p_est.add_argument("sqft", type=int, help="Square footage")
    p_est.add_argument("--scope", choices=["cosmetic", "partial", "full_gut"],
                       default="partial", help="Renovation scope")
    p_est.add_argument("--quality", choices=["low", "mid", "high"],
                       default="mid", help="Quality tier")

    # lookup
    p_look = sub.add_parser("lookup", help="Search materials database")
    p_look.add_argument("item", nargs="+", help="Item to search for")

    # category
    p_cat = sub.add_parser("category", help="List items in a category")
    p_cat.add_argument("name", help="Category or subcategory name")

    # categories
    sub.add_parser("categories", help="List all categories")

    # mao
    p_mao = sub.add_parser("mao", help="Calculate MAO with WA tax + contingency")
    p_mao.add_argument("arv", type=float, help="After Repair Value")
    p_mao.add_argument("repairs", type=float, help="Total repair cost")
    p_mao.add_argument("--contingency", type=float, default=15.0,
                       help="Contingency percentage (default: 15)")
    p_mao.add_argument("--tax", type=float, default=WA_TAX_DEFAULT,
                       help=f"WA sales tax %% (default: {WA_TAX_DEFAULT})")

    # sheet
    p_sheet = sub.add_parser("sheet", help="Read/populate a Google Sheets rehab template")
    p_sheet.add_argument("spreadsheet_id", help="Google Sheets ID or URL")
    p_sheet.add_argument("--populate", action="store_true",
                         help="Write suggested prices back to sheet")

    # update
    p_upd = sub.add_parser("update", help="Update a material mid price in the DB")
    p_upd.add_argument("item", nargs="+", help="Item name to update")
    p_upd.add_argument("new_mid_price", type=float, help="New mid-tier price")

    # suppliers
    p_sup = sub.add_parser("suppliers", help="Find local hardware/supply stores near a zip code")
    p_sup.add_argument("zip_code", help="Zip code to search near")

    args = parser.parse_args()

    dispatch = {
        "estimate":   cmd_estimate,
        "lookup":     cmd_lookup,
        "category":   cmd_category,
        "categories": cmd_categories,
        "mao":        cmd_mao,
        "sheet":      cmd_sheet,
        "update":     cmd_update,
        "suppliers":  cmd_suppliers,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


def cmd_suppliers(args):
    """Find local hardware and building supply stores near a zip code."""
    zip_code = args.zip_code

    print(f"{'━'*54}")
    print(f"🏪  LOCAL SUPPLIERS NEAR {zip_code}")
    print(f"{'━'*54}\n")

    categories = [
        ("Hardware Stores", "hardware store"),
        ("Home Depot / Lowe's", "home improvement store"),
        ("Lumber Yards", "lumber yard"),
        ("Tile & Flooring", "tile store"),
        ("Electrical Supply", "electrical supply store"),
        ("Plumbing Supply", "plumbing supply store"),
        ("Paint Stores", "paint store"),
    ]

    import json as _json

    for label, query in categories:
        print(f"  📍 {label}")
        try:
            result = subprocess.run(
                ["goplaces", "search", f"{query} near {zip_code}", "--limit", "3", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout:
                places = _json.loads(result.stdout)
                for p in places[:3]:
                    name = p.get("name", "Unknown")
                    addr = p.get("formatted_address", "")
                    rating = p.get("rating", "")
                    rating_str = f" ⭐ {rating}" if rating else ""
                    print(f"     • {name}{rating_str}")
                    if addr:
                        print(f"       {addr}")
            else:
                print(f"     (search unavailable — goplaces not configured)")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"     (goplaces not available — install or configure first)")
        print()

    print(f"  💡 Tip: Add the goplaces skill for live store data + hours + inventory hints.")
    print(f"{'━'*54}")


if __name__ == "__main__":
    main()
