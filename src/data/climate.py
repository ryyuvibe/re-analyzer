"""State-to-climate zone mapping based on IECC climate zones.

Simplified mapping for maintenance cost estimation.
"""

from enum import Enum


class ClimateZone(Enum):
    HOT_HUMID = "hot_humid"
    HOT_DRY = "hot_dry"
    MIXED_HUMID = "mixed_humid"
    MIXED_DRY = "mixed_dry"
    COLD = "cold"
    VERY_COLD = "very_cold"
    MARINE = "marine"


# Predominant IECC climate zone per state (simplified)
STATE_CLIMATE_ZONES: dict[str, ClimateZone] = {
    # Hot-humid
    "FL": ClimateZone.HOT_HUMID, "HI": ClimateZone.HOT_HUMID,
    "LA": ClimateZone.HOT_HUMID, "TX": ClimateZone.HOT_HUMID,
    "MS": ClimateZone.HOT_HUMID, "AL": ClimateZone.HOT_HUMID,
    "GA": ClimateZone.HOT_HUMID, "SC": ClimateZone.HOT_HUMID,
    "PR": ClimateZone.HOT_HUMID, "VI": ClimateZone.HOT_HUMID,
    # Hot-dry
    "AZ": ClimateZone.HOT_DRY, "NV": ClimateZone.HOT_DRY,
    "NM": ClimateZone.HOT_DRY,
    # Mixed-humid
    "NC": ClimateZone.MIXED_HUMID, "TN": ClimateZone.MIXED_HUMID,
    "VA": ClimateZone.MIXED_HUMID, "KY": ClimateZone.MIXED_HUMID,
    "AR": ClimateZone.MIXED_HUMID, "MO": ClimateZone.MIXED_HUMID,
    "OK": ClimateZone.MIXED_HUMID, "DE": ClimateZone.MIXED_HUMID,
    "MD": ClimateZone.MIXED_HUMID, "DC": ClimateZone.MIXED_HUMID,
    "WV": ClimateZone.MIXED_HUMID, "IN": ClimateZone.MIXED_HUMID,
    "OH": ClimateZone.MIXED_HUMID, "KS": ClimateZone.MIXED_HUMID,
    # Mixed-dry
    "CO": ClimateZone.MIXED_DRY, "UT": ClimateZone.MIXED_DRY,
    # Cold
    "PA": ClimateZone.COLD, "NJ": ClimateZone.COLD,
    "NY": ClimateZone.COLD, "CT": ClimateZone.COLD,
    "MA": ClimateZone.COLD, "RI": ClimateZone.COLD,
    "NH": ClimateZone.COLD, "IL": ClimateZone.COLD,
    "IA": ClimateZone.COLD, "MI": ClimateZone.COLD,
    "NE": ClimateZone.COLD, "WI": ClimateZone.COLD,
    "ID": ClimateZone.COLD, "SD": ClimateZone.COLD,
    "WY": ClimateZone.COLD, "MT": ClimateZone.COLD,
    # Very cold
    "MN": ClimateZone.VERY_COLD, "ND": ClimateZone.VERY_COLD,
    "VT": ClimateZone.VERY_COLD, "ME": ClimateZone.VERY_COLD,
    "AK": ClimateZone.VERY_COLD,
    # Marine
    "WA": ClimateZone.MARINE, "OR": ClimateZone.MARINE,
    "CA": ClimateZone.MARINE,
}


def get_climate_zone(state: str) -> ClimateZone:
    """Get the predominant climate zone for a state."""
    return STATE_CLIMATE_ZONES.get(state.upper(), ClimateZone.MIXED_HUMID)
