"""USGS Seismic Hazard API lookup.

Queries USGS for Peak Ground Acceleration (PGA) at a given lat/lon.
Free, no API key required.
"""

import logging
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

# USGS Unified Hazard Tool API — returns probabilistic seismic hazard
USGS_HAZARD_URL = "https://earthquake.usgs.gov/nshmp-haz-ws/hazard"


async def get_seismic_pga(lat: float, lon: float) -> Decimal | None:
    """Get the 2% in 50-year PGA (peak ground acceleration in g) for a location.

    Returns PGA as a Decimal, or None on failure.
    Higher values = more seismic risk.
    Typical ranges: 0.0-0.1 (low), 0.1-0.3 (moderate), 0.3+ (high).
    """
    # Use the NSHM conterminous US 2018 model
    params = {
        "latitude": lat,
        "longitude": lon,
        "edition": "E2014",
        "region": "COUS",
        "imt": "PGA",
        "vs30": 760,  # Site class B/C boundary
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(USGS_HAZARD_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        logger.warning("USGS seismic hazard request failed: %s", e)
        return None

    try:
        # Navigate the response to find 2% in 50-year hazard curve
        # The response contains hazard curves; we want the PGA value at 2%/50yr
        response_data = data.get("response", [])
        if not response_data:
            return None

        for curve_set in response_data:
            metadata = curve_set.get("metadata", {})
            if metadata.get("imt", {}).get("value") == "PGA":
                hazard_data = curve_set.get("data", [])
                if hazard_data:
                    # Get the mean hazard curve
                    for series in hazard_data:
                        if series.get("component") == "Total":
                            xvals = metadata.get("xvalues", [])
                            yvals = series.get("yvalues", [])
                            if xvals and yvals:
                                # Find PGA at ~2%/50yr exceedance (0.000404/yr)
                                target_rate = 0.000404
                                best_pga = Decimal("0.1")
                                best_diff = float("inf")
                                for x, y in zip(xvals, yvals):
                                    diff = abs(y - target_rate)
                                    if diff < best_diff:
                                        best_diff = diff
                                        best_pga = Decimal(str(round(x, 4)))
                                return best_pga
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("Failed to parse USGS response: %s", e)

    return None


def get_seismic_pga_from_state(state: str) -> Decimal:
    """Fallback: rough PGA estimate by state for when API is unavailable.

    Based on USGS seismic hazard maps, approximate values.
    """
    high_seismic = {"CA": "0.60", "AK": "0.50", "HI": "0.30", "WA": "0.30",
                    "OR": "0.25", "UT": "0.25", "NV": "0.20", "MT": "0.15"}
    moderate_seismic = {"SC": "0.15", "TN": "0.15", "MO": "0.15", "AR": "0.12",
                        "IL": "0.10", "KY": "0.10", "IN": "0.08", "ID": "0.15"}

    state_upper = state.upper()
    if state_upper in high_seismic:
        return Decimal(high_seismic[state_upper])
    if state_upper in moderate_seismic:
        return Decimal(moderate_seismic[state_upper])
    return Decimal("0.05")  # Low seismic risk default
