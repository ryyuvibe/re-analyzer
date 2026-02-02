"""Cash flow analysis: NOI, cap rate, CoC return, DSCR.

Pure functions: Decimal in, Decimal out. No I/O.
"""

from decimal import Decimal, ROUND_HALF_UP

from src.models.assumptions import DealAssumptions

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def gross_rent(assumptions: DealAssumptions, year: int) -> Decimal:
    """Gross scheduled rent for a given year (1-indexed).

    Year 1 is pro-rated if there is a rehab period (no rental income during rehab).
    """
    annual = assumptions.monthly_rent * 12
    growth_factor = (1 + assumptions.annual_rent_growth) ** (year - 1)
    full_year = (annual * growth_factor).quantize(TWO_PLACES, ROUND_HALF_UP)
    if year == 1 and assumptions.rehab_budget.rehab_months > 0:
        rehab_months = min(assumptions.rehab_budget.rehab_months, 12)
        rent_months = 12 - rehab_months
        return (full_year * Decimal(str(rent_months)) / Decimal("12")).quantize(
            TWO_PLACES, ROUND_HALF_UP
        )
    return full_year


def effective_gross_income(assumptions: DealAssumptions, year: int) -> Decimal:
    """EGI = gross rent - vacancy + other income."""
    gr = gross_rent(assumptions, year)
    vacancy = (gr * assumptions.vacancy_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
    return gr - vacancy + assumptions.other_income


def operating_expenses(assumptions: DealAssumptions, year: int) -> dict[str, Decimal]:
    """Calculate itemized operating expenses for a given year."""
    gr = gross_rent(assumptions, year)
    expense_growth = (1 + assumptions.annual_expense_growth) ** (year - 1)

    # Property tax and insurance grow with expense growth rate
    prop_tax = (assumptions.property_tax * Decimal(str(expense_growth))).quantize(
        TWO_PLACES, ROUND_HALF_UP
    )
    insurance = (assumptions.insurance * Decimal(str(expense_growth))).quantize(
        TWO_PLACES, ROUND_HALF_UP
    )

    # Percentage-based expenses use current year's gross rent
    maintenance = (gr * assumptions.maintenance_pct).quantize(TWO_PLACES, ROUND_HALF_UP)
    management = (gr * assumptions.management_pct).quantize(TWO_PLACES, ROUND_HALF_UP)
    capex = (gr * assumptions.capex_reserve_pct).quantize(TWO_PLACES, ROUND_HALF_UP)
    hoa = (assumptions.hoa * 12).quantize(TWO_PLACES, ROUND_HALF_UP)

    total = prop_tax + insurance + maintenance + management + capex + hoa

    return {
        "property_tax": prop_tax,
        "insurance": insurance,
        "maintenance": maintenance,
        "management": management,
        "capex_reserve": capex,
        "hoa": hoa,
        "total": total,
    }


def noi(assumptions: DealAssumptions, year: int) -> Decimal:
    """Net Operating Income = EGI - operating expenses."""
    egi = effective_gross_income(assumptions, year)
    expenses = operating_expenses(assumptions, year)
    return egi - expenses["total"]


def cash_flow_before_tax(
    assumptions: DealAssumptions, year: int, annual_debt_service: Decimal
) -> Decimal:
    """CFBT = NOI - debt service."""
    return noi(assumptions, year) - annual_debt_service


def cap_rate(assumptions: DealAssumptions, year: int = 1) -> Decimal:
    """Cap rate = Year 1 NOI / purchase price."""
    if assumptions.purchase_price == 0:
        return Decimal("0")
    return (noi(assumptions, year) / assumptions.purchase_price).quantize(
        FOUR_PLACES, ROUND_HALF_UP
    )


def cash_on_cash(
    cash_flow: Decimal, total_initial_investment: Decimal
) -> Decimal:
    """Cash-on-cash return = annual CFBT / total cash invested."""
    if total_initial_investment == 0:
        return Decimal("0")
    return (cash_flow / total_initial_investment).quantize(FOUR_PLACES, ROUND_HALF_UP)


def dscr(noi_amount: Decimal, annual_debt_service: Decimal) -> Decimal:
    """Debt Service Coverage Ratio = NOI / annual debt service."""
    if annual_debt_service == 0:
        return Decimal("0")
    return (noi_amount / annual_debt_service).quantize(FOUR_PLACES, ROUND_HALF_UP)


def property_value(assumptions: DealAssumptions, year: int) -> Decimal:
    """Estimated property value at end of year based on appreciation."""
    growth = (1 + assumptions.annual_appreciation) ** year
    return (assumptions.purchase_price * Decimal(str(growth))).quantize(
        TWO_PLACES, ROUND_HALF_UP
    )
