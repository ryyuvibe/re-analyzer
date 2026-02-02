"""GreatSchools API client for nearby school ratings."""

import logging
from decimal import Decimal

import httpx

from src.config import settings
from src.models.neighborhood import SchoolInfo

logger = logging.getLogger(__name__)

GREATSCHOOLS_URL = "https://gs-api.greatschools.org/nearby-schools"


async def get_nearby_schools(
    lat: float,
    lon: float,
    radius: int = 5,
    limit: int = 10,
    api_key: str | None = None,
) -> list[SchoolInfo]:
    """Fetch nearby schools with ratings from GreatSchools.

    Returns an empty list if the API key is missing or the request fails.
    """
    key = api_key or settings.greatschools_api_key
    if not key:
        logger.debug("GreatSchools API key not configured, skipping")
        return []

    params = {
        "lat": str(lat),
        "lon": str(lon),
        "radius": str(radius),
        "limit": str(limit),
    }
    headers = {
        "x-api-key": key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GREATSCHOOLS_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError, Exception) as e:
        logger.warning("GreatSchools request failed: %s", e)
        return []

    schools: list[SchoolInfo] = []
    items = data if isinstance(data, list) else data.get("schools", [])
    for s in items:
        rating = s.get("rating")
        if rating is None:
            continue
        try:
            schools.append(SchoolInfo(
                name=s.get("name", "Unknown"),
                rating=int(rating),
                level=s.get("level", "unknown").lower(),
                distance_miles=Decimal(str(s.get("distance", 0))),
            ))
        except (ValueError, TypeError):
            continue

    return schools
