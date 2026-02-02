"""Census API client for population data."""

import logging
from decimal import Decimal

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

CENSUS_BASE_URL = "https://api.census.gov/data"


class CensusClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.census_api_key

    async def get_population(self, state_fips: str, county_fips: str) -> int | None:
        """Get population for a county."""
        params = {
            "get": "POP",
            "for": f"county:{county_fips}",
            "in": f"state:{state_fips}",
        }
        if self.api_key:
            params["key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{CENSUS_BASE_URL}/2020/dec/pl", params=params)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPStatusError, Exception) as e:
            logger.warning("Census population request failed: %s", e)
            return None

        if len(data) > 1:
            return int(data[1][0])
        return None
