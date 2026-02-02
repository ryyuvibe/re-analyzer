"""OpenStreetMap Overpass API for traffic/noise proximity scoring.

Counts major roads (motorway, trunk, primary) within a radius of a point.
Free, no API key required.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def get_traffic_noise_score(lat: float, lon: float, radius_m: int = 200) -> int:
    """Count major road segments within radius of a point.

    Returns a score 0-10 based on road density:
        0 = no major roads nearby (quiet)
        1-3 = some traffic
        4-6 = moderate traffic
        7-10 = heavy traffic / highway adjacent

    Returns 0 on API failure (assume quiet).
    """
    query = f"""
    [out:json][timeout:10];
    (
      way["highway"="motorway"](around:{radius_m},{lat},{lon});
      way["highway"="trunk"](around:{radius_m},{lat},{lon});
      way["highway"="primary"](around:{radius_m},{lat},{lon});
    );
    out count;
    """

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        logger.warning("Overpass API request failed: %s", e)
        return 0

    total = data.get("elements", [{}])[0].get("tags", {}).get("total", 0)
    try:
        count = int(total)
    except (ValueError, TypeError):
        count = 0

    # Map count to 0-10 score
    if count == 0:
        return 0
    if count <= 2:
        return 2
    if count <= 5:
        return 4
    if count <= 10:
        return 6
    if count <= 20:
        return 8
    return 10
