"""Insurance cost estimator for rental properties."""

from decimal import Decimal

# State multipliers — hurricane/fire/tornado-prone states cost more
STATE_MULTIPLIERS: dict[str, Decimal] = {
    "FL": Decimal("1.40"),
    "LA": Decimal("1.40"),
    "TX": Decimal("1.40"),
    "MS": Decimal("1.30"),
    "SC": Decimal("1.25"),
    "NC": Decimal("1.20"),
    "AL": Decimal("1.25"),
    "CA": Decimal("1.30"),
    "CO": Decimal("1.15"),
    "OK": Decimal("1.25"),
    "KS": Decimal("1.20"),
}

BASE_RATE = Decimal("0.0035")  # 0.35% of property value
MINIMUM_ANNUAL = Decimal("800")


def estimate_annual_insurance(
    property_value: Decimal,
    sqft: int,
    year_built: int,
    state: str = "OH",
    property_type: str = "SFR",
) -> Decimal:
    """Estimate annual insurance premium for a rental property.

    Args:
        property_value: Current property value or purchase price.
        sqft: Square footage (unused in current model but reserved for future).
        year_built: Year the property was built.
        state: Two-letter state code.
        property_type: SFR, Multi-Family, Condo, Townhouse.

    Returns:
        Estimated annual insurance premium as Decimal.
    """
    # Base premium
    premium = property_value * BASE_RATE

    # State adjustment
    state_mult = STATE_MULTIPLIERS.get(state.upper(), Decimal("1.0"))
    premium *= state_mult

    # Age surcharge — older properties have dated wiring, plumbing, roofing
    if year_built and year_built < 1950:
        premium *= Decimal("1.20")
    elif year_built and year_built < 1970:
        premium *= Decimal("1.10")

    # Property type adjustment
    prop_upper = property_type.upper().replace("-", "").replace(" ", "")
    if prop_upper in ("MULTIFAMILY", "MULTI"):
        premium *= Decimal("1.15")
    elif prop_upper == "CONDO":
        premium *= Decimal("0.80")

    # Floor
    if premium < MINIMUM_ANNUAL:
        premium = MINIMUM_ANNUAL

    return premium.quantize(Decimal("1"))
