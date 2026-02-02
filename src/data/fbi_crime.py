"""FBI UCR (Uniform Crime Report) crime data lookup.

Provides county-level crime rates. Uses state-level fallback tables
since the FBI API requires registration and can be unreliable.
"""

import logging
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

# State-level property crime rates per 100,000 (FBI UCR 2022 estimates)
# Source: FBI Crime Data Explorer
STATE_PROPERTY_CRIME_RATES: dict[str, int] = {
    "AL": 2784, "AK": 3241, "AZ": 2751, "AR": 3227, "CA": 2491,
    "CO": 3338, "CT": 1604, "DE": 2574, "FL": 2087, "GA": 2397,
    "HI": 3062, "ID": 1546, "IL": 1630, "IN": 2083, "IA": 1735,
    "KS": 2616, "KY": 1743, "LA": 3054, "ME": 1316, "MD": 2050,
    "MA": 1159, "MI": 1789, "MN": 2256, "MS": 2400, "MO": 2972,
    "MT": 2573, "NE": 1940, "NV": 2371, "NH": 1064, "NJ": 1313,
    "NM": 3649, "NY": 1618, "NC": 2510, "ND": 2263, "OH": 2275,
    "OK": 3116, "OR": 3282, "PA": 1418, "RI": 1521, "SC": 3014,
    "SD": 1715, "TN": 2734, "TX": 2779, "UT": 2797, "VT": 1218,
    "VA": 1643, "WA": 3397, "WV": 1653, "WI": 1649, "WY": 1722,
    "DC": 3736,
}

# State-level violent crime rates per 100,000
STATE_VIOLENT_CRIME_RATES: dict[str, int] = {
    "AL": 454, "AK": 838, "AZ": 485, "AR": 672, "CA": 500,
    "CO": 492, "CT": 182, "DE": 431, "FL": 384, "GA": 400,
    "HI": 248, "ID": 225, "IL": 426, "IN": 382, "IA": 294,
    "KS": 410, "KY": 223, "LA": 639, "ME": 109, "MD": 471,
    "MA": 309, "MI": 474, "MN": 281, "MS": 293, "MO": 543,
    "MT": 459, "NE": 310, "NV": 461, "NH": 146, "NJ": 195,
    "NM": 832, "NY": 364, "NC": 402, "ND": 314, "OH": 321,
    "OK": 458, "OR": 292, "PA": 391, "RI": 220, "SC": 531,
    "SD": 501, "TN": 673, "TX": 447, "UT": 252, "VT": 173,
    "VA": 209, "WA": 366, "WV": 355, "WI": 296, "WY": 217,
    "DC": 900,
}


def get_crime_rate(state: str) -> tuple[Decimal, Decimal]:
    """Get property and violent crime rates per 100K for a state.

    Returns (property_crime_rate, violent_crime_rate).
    """
    state_upper = state.upper()
    prop_rate = STATE_PROPERTY_CRIME_RATES.get(state_upper, 2000)
    violent_rate = STATE_VIOLENT_CRIME_RATES.get(state_upper, 350)
    return Decimal(str(prop_rate)), Decimal(str(violent_rate))
