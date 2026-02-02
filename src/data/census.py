"""Census API client for population and demographic data."""

import logging
from decimal import Decimal

import httpx

from src.config import settings
from src.models.neighborhood import NeighborhoodDemographics

logger = logging.getLogger(__name__)

CENSUS_BASE_URL = "https://api.census.gov/data"

# ACS 5-year variable codes
ACS_VARIABLES = {
    "B19013_001E": "median_household_income",
    "B25077_001E": "median_home_value",
    "B17001_002E": "poverty_count",
    "B01003_001E": "total_population",
    "B25003_001E": "total_occupied",
    "B25003_002E": "owner_occupied",
}


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

    async def get_neighborhood_demographics(
        self,
        state_fips: str,
        county_fips: str,
        tract_fips: str,
    ) -> NeighborhoodDemographics | None:
        """Fetch ACS 5-year demographic data for a census tract."""
        if not all([state_fips, county_fips, tract_fips]):
            logger.warning("Missing FIPS codes for ACS query")
            return None

        variables = ",".join(ACS_VARIABLES.keys())
        params = {
            "get": variables,
            "for": f"tract:{tract_fips}",
            "in": f"state:{state_fips} county:{county_fips}",
        }
        if self.api_key:
            params["key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{CENSUS_BASE_URL}/2022/acs/acs5",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPStatusError, Exception) as e:
            logger.warning("Census ACS request failed: %s", e)
            return None

        if len(data) < 2:
            return None

        headers = data[0]
        values = data[1]
        row = dict(zip(headers, values))

        def safe_int(key: str) -> int | None:
            v = row.get(key)
            if v is None or v in ("", "-666666666"):
                return None
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return None

        median_income = safe_int("B19013_001E")
        median_home_value = safe_int("B25077_001E")
        poverty_count = safe_int("B17001_002E")
        total_pop = safe_int("B01003_001E")
        total_occupied = safe_int("B25003_001E")
        owner_occupied = safe_int("B25003_002E")

        # Compute derived rates
        poverty_rate = None
        if poverty_count is not None and total_pop and total_pop > 0:
            poverty_rate = Decimal(str(poverty_count)) / Decimal(str(total_pop))

        renter_pct = None
        if total_occupied and owner_occupied is not None and total_occupied > 0:
            renter_count = total_occupied - owner_occupied
            renter_pct = Decimal(str(renter_count)) / Decimal(str(total_occupied))

        return NeighborhoodDemographics(
            median_household_income=median_income,
            median_home_value=median_home_value,
            poverty_rate=poverty_rate,
            population=total_pop,
            renter_pct=renter_pct,
        )
