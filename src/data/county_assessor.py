"""County assessor data for property tax rates.

Since assessor data varies dramatically by county and most don't have APIs,
this module provides a lookup of average effective tax rates by state/county
and falls back to state averages.
"""

import logging
from decimal import Decimal

from src.models.property import Address

logger = logging.getLogger(__name__)

# Average effective property tax rates by state (source: Tax Foundation)
STATE_AVG_TAX_RATES: dict[str, Decimal] = {
    "AL": Decimal("0.0040"), "AK": Decimal("0.0118"), "AZ": Decimal("0.0062"),
    "AR": Decimal("0.0062"), "CA": Decimal("0.0071"), "CO": Decimal("0.0051"),
    "CT": Decimal("0.0215"), "DE": Decimal("0.0056"), "FL": Decimal("0.0089"),
    "GA": Decimal("0.0092"), "HI": Decimal("0.0028"), "ID": Decimal("0.0069"),
    "IL": Decimal("0.0227"), "IN": Decimal("0.0085"), "IA": Decimal("0.0157"),
    "KS": Decimal("0.0141"), "KY": Decimal("0.0086"), "LA": Decimal("0.0055"),
    "ME": Decimal("0.0136"), "MD": Decimal("0.0109"), "MA": Decimal("0.0123"),
    "MI": Decimal("0.0154"), "MN": Decimal("0.0113"), "MS": Decimal("0.0081"),
    "MO": Decimal("0.0097"), "MT": Decimal("0.0083"), "NE": Decimal("0.0173"),
    "NV": Decimal("0.0060"), "NH": Decimal("0.0218"), "NJ": Decimal("0.0249"),
    "NM": Decimal("0.0080"), "NY": Decimal("0.0172"), "NC": Decimal("0.0084"),
    "ND": Decimal("0.0098"), "OH": Decimal("0.0157"), "OK": Decimal("0.0090"),
    "OR": Decimal("0.0097"), "PA": Decimal("0.0153"), "RI": Decimal("0.0163"),
    "SC": Decimal("0.0057"), "SD": Decimal("0.0131"), "TN": Decimal("0.0071"),
    "TX": Decimal("0.0180"), "UT": Decimal("0.0063"), "VT": Decimal("0.0190"),
    "VA": Decimal("0.0082"), "WA": Decimal("0.0098"), "WV": Decimal("0.0058"),
    "WI": Decimal("0.0185"), "WY": Decimal("0.0061"), "DC": Decimal("0.0056"),
}


async def get_property_tax_rate(state: str) -> Decimal:
    """Get effective property tax rate for a state.

    Returns state average rate. For production, this would query
    the county assessor's website/API for the specific jurisdiction.
    """
    return STATE_AVG_TAX_RATES.get(state.upper(), Decimal("0.0100"))


async def estimate_annual_tax(address: Address, estimated_value: Decimal) -> Decimal:
    """Estimate annual property tax based on state average rate and property value."""
    rate = await get_property_tax_rate(address.state)
    return (estimated_value * rate).quantize(Decimal("0.01"))
