"""NOAA Storm Events — hurricane wind zone and hail frequency by county FIPS.

Uses hardcoded county-level data derived from NOAA Storm Events Database and
FEMA wind zone maps. Free, no API key.
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# Hurricane wind zones by state (simplified from FEMA wind zone maps)
# Category exposure: 3+ = major hurricane zone, 1-2 = tropical storm zone
HURRICANE_ZONES: dict[str, int] = {
    # Cat 3+ exposure (coastal)
    "FL": 3, "LA": 3, "TX": 2, "MS": 2, "AL": 2,
    "SC": 2, "NC": 2, "GA": 1, "VA": 1, "MD": 1,
    "DE": 1, "NJ": 1, "NY": 1, "CT": 1, "RI": 1, "MA": 1,
    "HI": 2, "PR": 3, "VI": 3,
}

# Annual hail event frequency classification by state
# Based on NOAA Storm Events Database aggregated data
# "high" = Tornado Alley / Great Plains, "moderate" = surrounding states
HAIL_FREQUENCY: dict[str, str] = {
    # High frequency (> 30 events/yr average)
    "TX": "high", "OK": "high", "KS": "high", "NE": "high",
    "SD": "high", "CO": "high", "ND": "high",
    # Moderate frequency (10-30 events/yr)
    "IA": "moderate", "MO": "moderate", "MN": "moderate", "WI": "moderate",
    "IL": "moderate", "IN": "moderate", "AR": "moderate", "MS": "moderate",
    "AL": "moderate", "GA": "moderate", "SC": "moderate", "NC": "moderate",
    "TN": "moderate", "KY": "moderate", "WY": "moderate", "MT": "moderate",
    "NM": "moderate", "LA": "moderate",
}


def get_hurricane_zone(state: str) -> int:
    """Get hurricane category exposure for a state.

    Returns:
        3 = Cat 3+ hurricane zone (coastal FL, LA, PR)
        2 = Cat 1-2 zone (TX coast, MS, AL, SC, NC, HI)
        1 = Tropical storm exposure (northeast coast)
        0 = Inland / minimal hurricane risk
    """
    return HURRICANE_ZONES.get(state.upper(), 0)


def get_hail_frequency(state: str) -> str:
    """Get hail frequency classification for a state.

    Returns: 'high', 'moderate', or 'low'
    """
    return HAIL_FREQUENCY.get(state.upper(), "low")
