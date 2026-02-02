"""CLI client for the RE Analyzer API — posts a deal and prints a rich terminal report.

Usage:
    python deal-analyzer/analyze_deal.py "107 Midland Ave, Columbus, OH 43223" --price 120000 --beds 3 --baths 1 --sqft 1500
    python deal-analyzer/analyze_deal.py "123 Main St, Springfield, OH" --condition medium --rehab-months 3
"""

import argparse
import asyncio
import sys
from decimal import Decimal

import httpx


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pct(v) -> str:
    """Format a decimal/float as a percentage string."""
    return f"{float(v) * 100:.2f}%"


def _dollar(v) -> str:
    return f"${float(v):,.0f}"


def _header(title: str) -> None:
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}")


# ── Report sections ──────────────────────────────────────────────────────────

def print_property_summary(data: dict) -> None:
    prop = data["property"]
    _header("Property Summary")
    print(f"  Address:          {prop['street']}, {prop['city']}, {prop['state']} {prop['zip_code']}")
    print(f"  Beds / Baths:     {prop['bedrooms']} bd / {float(prop['bathrooms']):.1f} ba")
    print(f"  Sqft:             {int(prop['sqft']):,}")
    print(f"  Year Built:       {prop['year_built']}")
    print(f"  Estimated Value:  {_dollar(prop['estimated_value'])}")
    print(f"  Estimated Rent:   {_dollar(prop['estimated_rent'])}/mo")
    print(f"  Annual Tax:       {_dollar(prop['annual_tax'])}")


def print_deal_metrics(data: dict) -> None:
    _header("Deal Metrics")
    print(f"  Before-Tax IRR:       {_pct(data['before_tax_irr'])}")
    print(f"  After-Tax IRR:        {_pct(data['after_tax_irr'])}")
    print(f"  Equity Multiple:      {float(data['equity_multiple']):.2f}x")
    print(f"  Avg Cash-on-Cash:     {_pct(data['average_cash_on_cash'])}")
    print(f"  Total Profit:         {_dollar(data['total_profit'])}")
    print(f"  Initial Investment:   {_dollar(data['total_initial_investment'])}")
    if data.get("loan_type"):
        print(f"  Loan Type:            {data['loan_type']}")


def print_rent_estimate(data: dict) -> None:
    rent = data.get("rent_estimate")
    if not rent:
        return
    _header("Rent Estimate")
    print(f"  Estimated Rent:   ${rent['estimated_rent']:,.0f}/mo")
    print(f"  Confidence:       {rent['confidence']} ({rent['confidence_score']:.0%})")
    lo, hi = rent["recommended_range"]
    print(f"  Range:            ${lo:,.0f} – ${hi:,.0f}")
    print()
    for tr in rent.get("tier_results", []):
        est = f"${tr['estimate']:,.0f}" if tr["estimate"] else "N/A"
        print(f"  [{tr['tier'].upper():>8}]  {est:>10}  ({tr['confidence']})")
        print(f"             {tr['reasoning']}")


def print_rehab_summary(data: dict) -> None:
    if not data.get("condition_grade"):
        return
    _header("Rehab Summary")
    print(f"  Condition Grade:  {data['condition_grade']}")
    print(f"  Rehab Cost:       {_dollar(data['rehab_total_cost'])}")
    print(f"  Rehab Months:     {data['rehab_months']}")
    items = data.get("rehab_line_items", [])
    if items:
        print()
        for item in items:
            override = f" (override: {_dollar(item['override_cost'])})" if item.get("override_cost") else ""
            print(f"    {item['category']:<24} {_dollar(item['cost']):>10}{override}")


def print_cashflow_table(data: dict) -> None:
    projections = data.get("yearly_projections", [])
    if not projections:
        return
    _header("Cash Flow Projections")
    header = (
        f"  {'Yr':>3}  {'Gross Rent':>11}  {'NOI':>11}  {'CFBT':>11}  "
        f"{'CFAT':>11}  {'CoC':>7}  {'DSCR':>5}"
    )
    print(header)
    print(f"  {'---':>3}  {'-' * 11}  {'-' * 11}  {'-' * 11}  {'-' * 11}  {'-' * 7}  {'-' * 5}")
    for yr in projections:
        print(
            f"  {yr['year']:>3}  {_dollar(yr['gross_rent']):>11}  "
            f"{_dollar(yr['noi']):>11}  {_dollar(yr['cash_flow_before_tax']):>11}  "
            f"{_dollar(yr['cash_flow_after_tax']):>11}  {_pct(yr['cash_on_cash']):>7}  "
            f"{float(yr['dscr']):>5.2f}"
        )


def print_disposition(data: dict) -> None:
    disp = data.get("disposition")
    if not disp:
        return
    _header("Disposition (Sale)")
    print(f"  Sale Price:           {_dollar(disp['sale_price'])}")
    print(f"  Selling Costs:        {_dollar(disp['selling_costs'])}")
    print(f"  Net Sale Proceeds:    {_dollar(disp['net_sale_proceeds'])}")
    print(f"  Total Tax on Sale:    {_dollar(disp['total_tax_on_sale'])}")
    print(f"  After-Tax Proceeds:   {_dollar(disp['after_tax_sale_proceeds'])}")
    print()
    print(f"  Depreciation Recapture:  {_dollar(disp['depreciation_recapture'])}")
    print(f"  Capital Gain:            {_dollar(disp['capital_gain'])}")
    print(f"  Suspended Losses Released: {_dollar(disp['suspended_losses_released'])}")


def print_neighborhood(data: dict) -> None:
    nbr = data.get("neighborhood")
    if not nbr:
        return
    _header("Neighborhood")
    print(f"  Grade:            {nbr['grade']} ({float(nbr['grade_score']):.1f}/100)")

    demo = nbr.get("demographics")
    if demo:
        print()
        if demo.get("median_household_income"):
            print(f"  Median Income:    ${demo['median_household_income']:,}")
        if demo.get("median_home_value"):
            print(f"  Median Home Value: ${demo['median_home_value']:,}")
        if demo.get("poverty_rate") is not None:
            print(f"  Poverty Rate:     {_pct(demo['poverty_rate'])}")
        if demo.get("renter_pct") is not None:
            print(f"  Renter %:         {_pct(demo['renter_pct'])}")

    # Risk factors
    risks = []
    if nbr.get("flood_zone") and nbr["flood_zone"] != "X":
        risks.append(f"Flood zone: {nbr['flood_zone']}")
    if nbr.get("wildfire_risk") and nbr["wildfire_risk"] > 3:
        risks.append(f"Wildfire risk: {nbr['wildfire_risk']}/6")
    if nbr.get("hurricane_zone") and nbr["hurricane_zone"] > 0:
        risks.append(f"Hurricane zone: {nbr['hurricane_zone']}")
    if nbr.get("crime_rate") is not None:
        risks.append(f"Crime rate: {float(nbr['crime_rate']):.1f}")
    if risks:
        print()
        print(f"  Risk Factors:     {', '.join(risks)}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze a real estate deal via the RE Analyzer API"
    )
    parser.add_argument("address", help="Full US address string")
    parser.add_argument("--price", type=int, help="Purchase price override")
    parser.add_argument("--sqft", type=int, help="Square footage")
    parser.add_argument("--beds", type=int, help="Bedrooms")
    parser.add_argument("--baths", type=float, help="Bathrooms")
    parser.add_argument("--year-built", type=int, help="Year built")
    parser.add_argument(
        "--condition",
        choices=["turnkey", "light", "medium", "heavy", "full_gut"],
        default=None,
        help="Condition grade (default: turnkey)",
    )
    parser.add_argument("--rehab-months", type=int, help="Rehab duration in months")
    parser.add_argument("--monthly-rent", type=Decimal, help="Monthly rent override")
    parser.add_argument("--hold-years", type=int, help="Hold period in years")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    # Build payload — only include non-None overrides
    payload: dict = {"address": args.address}

    field_map = {
        "price": "purchase_price_override",
        "sqft": "sqft",
        "beds": "bedrooms",
        "baths": "bathrooms",
        "year_built": "year_built",
        "condition": "condition_grade",
        "rehab_months": "rehab_months",
        "monthly_rent": "monthly_rent",
        "hold_years": "hold_years",
    }
    for cli_name, api_name in field_map.items():
        val = getattr(args, cli_name)
        if val is not None:
            payload[api_name] = val if not isinstance(val, Decimal) else str(val)

    url = f"{args.api_url}/api/v1/analyze"

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.ConnectError:
            print(f"Error: Could not connect to API at {args.api_url}", file=sys.stderr)
            print("Is the server running? Start with: uvicorn src.api.app:app --reload", file=sys.stderr)
            sys.exit(1)
        except httpx.TimeoutException:
            print("Error: Request timed out (analysis may take a while for new addresses)", file=sys.stderr)
            sys.exit(1)

        if resp.status_code != 200:
            print(f"Error: API returned {resp.status_code}", file=sys.stderr)
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            print(f"  {detail}", file=sys.stderr)
            sys.exit(1)

        data = resp.json()

    # Print report
    print_property_summary(data)
    print_deal_metrics(data)
    print_rent_estimate(data)
    print_rehab_summary(data)
    print_cashflow_table(data)
    print_disposition(data)
    print_neighborhood(data)
    print()


if __name__ == "__main__":
    asyncio.run(main())
