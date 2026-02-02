"""FEMA National Flood Hazard Layer (NFHL) lookup.

Queries the FEMA NFHL MapServer to determine flood zone for a lat/lon coordinate.
Free, no API key required.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# FEMA NFHL REST MapServer — layer 28 is the flood hazard zones
NFHL_URL = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"

# Flood zone risk ordering (higher = worse)
FLOOD_ZONE_RISK = {
    "V": 5,    # Coastal high hazard
    "VE": 5,
    "A": 4,    # 100-year floodplain
    "AE": 4,
    "AH": 4,
    "AO": 4,
    "A99": 3,
    "X500": 2,  # 500-year floodplain (moderate risk)
    "B": 2,     # Older designation for 500-year
    "X": 1,     # Minimal risk
    "C": 1,     # Older designation for minimal
    "D": 1,     # Undetermined
}


async def get_flood_zone(lat: float, lon: float) -> str | None:
    """Query FEMA NFHL for the flood zone at given coordinates.

    Returns flood zone string (e.g., 'AE', 'X', 'VE') or None on failure.
    """
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE",
        "returnGeometry": "false",
        "f": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(NFHL_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        logger.warning("FEMA NFHL request failed: %s", e)
        return None

    features = data.get("features", [])
    if not features:
        return "X"  # No flood zone data = minimal risk

    zone = features[0].get("attributes", {}).get("FLD_ZONE", "X")
    return zone
