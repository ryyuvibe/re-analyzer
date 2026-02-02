"""State-level closing cost estimation.

Closing costs include: title insurance, transfer tax, recording fees, attorney fees.
Expressed as a percentage of purchase price.
"""

from decimal import Decimal

# State-level buyer closing cost percentages
# Sources: Bankrate, ClosingCorp national closing cost surveys
# Includes title insurance, recording, attorney, and misc fees
# Does NOT include lender fees (points) or prepaid items (escrow)
STATE_CLOSING_COST_PCT: dict[str, Decimal] = {
    # Higher closing cost states (>3%)
    "NY": Decimal("0.040"),  # High attorney fees + mortgage recording tax
    "CT": Decimal("0.035"),  # Attorney state
    "NJ": Decimal("0.035"),  # Attorney state
    "DE": Decimal("0.035"),  # Transfer tax
    "DC": Decimal("0.035"),  # Transfer tax
    "MD": Decimal("0.032"),  # Transfer tax
    "PA": Decimal("0.032"),  # Transfer tax
    "WA": Decimal("0.030"),  # Excise tax
    "HI": Decimal("0.030"),  # Transfer tax

    # Moderate (2.5-3%)
    "FL": Decimal("0.028"),
    "CA": Decimal("0.025"),
    "TX": Decimal("0.025"),
    "IL": Decimal("0.028"),
    "MA": Decimal("0.028"),
    "VA": Decimal("0.025"),
    "GA": Decimal("0.025"),
    "NC": Decimal("0.025"),
    "SC": Decimal("0.025"),
    "TN": Decimal("0.025"),
    "OH": Decimal("0.025"),
    "MI": Decimal("0.025"),
    "AZ": Decimal("0.025"),
    "CO": Decimal("0.022"),
    "NV": Decimal("0.025"),
    "MN": Decimal("0.025"),

    # Lower closing cost states (<2.5%)
    "IN": Decimal("0.020"),
    "MO": Decimal("0.020"),
    "WI": Decimal("0.020"),
    "IA": Decimal("0.020"),
    "KS": Decimal("0.020"),
    "NE": Decimal("0.020"),
    "OK": Decimal("0.020"),
    "AR": Decimal("0.020"),
    "KY": Decimal("0.020"),
    "AL": Decimal("0.020"),
    "MS": Decimal("0.020"),
    "LA": Decimal("0.020"),
    "WV": Decimal("0.020"),
    "ID": Decimal("0.018"),
    "MT": Decimal("0.018"),
    "WY": Decimal("0.018"),
    "SD": Decimal("0.018"),
    "ND": Decimal("0.018"),
}

DEFAULT_CLOSING_PCT = Decimal("0.025")  # 2.5% national average


def estimate_closing_costs(
    purchase_price: Decimal,
    state: str,
) -> tuple[Decimal, Decimal]:
    """Estimate buyer closing costs for a state.

    Returns (closing_cost_amount, closing_cost_pct).
    """
    pct = STATE_CLOSING_COST_PCT.get(state.upper(), DEFAULT_CLOSING_PCT)
    amount = (purchase_price * pct).quantize(Decimal("1"))
    return amount, pct
