"""USFS Wildfire Risk to Communities lookup.

Queries the Wildfire Risk to Communities ArcGIS service for risk class at a lat/lon.
Free, no API key required.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# USFS Wildfire Risk to Communities MapServer
WILDFIRE_URL = (
    "https://apps.fs.usda.gov/arcx/rest/services/RDW_Wildfire/"
    "ProbabilisticWildfireRisk/MapServer/2/query"
)


async def get_wildfire_risk(lat: float, lon: float) -> int | None:
    """Get wildfire risk class (1-5) for a location.

    1 = minimal risk, 5 = extreme risk.
    Returns None on failure.
    """
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Risk_Class,WHPS",
        "returnGeometry": "false",
        "f": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(WILDFIRE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        logger.warning("USFS wildfire risk request failed: %s", e)
        return None

    features = data.get("features", [])
    if not features:
        return 1  # No data = likely minimal risk

    attrs = features[0].get("attributes", {})
    risk_class = attrs.get("Risk_Class")
    if risk_class is not None:
        return max(1, min(5, int(risk_class)))
    return 1


def get_wildfire_risk_from_state(state: str) -> int:
    """Fallback: rough wildfire risk by state when API unavailable."""
    high_risk = {"CA": 4, "CO": 3, "OR": 3, "WA": 3, "MT": 3, "ID": 3,
                 "NM": 3, "AZ": 3, "NV": 2, "UT": 2, "TX": 2}
    return high_risk.get(state.upper(), 1)
