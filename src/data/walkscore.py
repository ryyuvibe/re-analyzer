"""Walk Score API client."""

import logging

import httpx

from src.config import settings
from src.models.neighborhood import WalkScoreResult

logger = logging.getLogger(__name__)

WALKSCORE_URL = "https://api.walkscore.com/score"


async def get_walk_score(
    address: str,
    lat: float,
    lon: float,
    api_key: str | None = None,
) -> WalkScoreResult | None:
    """Fetch walk, transit, and bike scores for a location.

    Returns None if the API key is missing or the request fails.
    """
    key = api_key or settings.walkscore_api_key
    if not key:
        logger.debug("Walk Score API key not configured, skipping")
        return None

    params = {
        "format": "json",
        "address": address,
        "lat": str(lat),
        "lon": str(lon),
        "transit": "1",
        "bike": "1",
        "wsapikey": key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(WALKSCORE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError, Exception) as e:
        logger.warning("Walk Score request failed: %s", e)
        return None

    if data.get("status") != 1:
        logger.warning("Walk Score returned status %s", data.get("status"))
        return None

    return WalkScoreResult(
        walk_score=data.get("walkscore"),
        transit_score=data.get("transit", {}).get("score") if isinstance(data.get("transit"), dict) else None,
        bike_score=data.get("bike", {}).get("score") if isinstance(data.get("bike"), dict) else None,
    )
