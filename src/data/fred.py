"""FRED API client for macro economic indicators."""

import logging
import math
from decimal import Decimal
from datetime import date, timedelta

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# Common FRED series IDs
SERIES = {
    "treasury_10y": "DGS10",
    "treasury_30y": "DGS30",
    "cpi": "CPIAUCSL",
    "unemployment": "UNRATE",
    "mortgage_30y": "MORTGAGE30US",
    "median_home_price": "MSPUS",
}


class FREDClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.fred_api_key

    async def _get_latest(self, series_id: str) -> Decimal | None:
        """Fetch the most recent observation for a FRED series."""
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{FRED_BASE_URL}/series/observations", params=params
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("FRED request failed for %s: %s", series_id, e)
            return None

        observations = data.get("observations", [])
        for obs in observations:
            value = obs.get("value", ".")
            if value != ".":
                return Decimal(value)
        return None

    async def get_treasury_yield(self, maturity: str = "10y") -> Decimal | None:
        series_key = f"treasury_{maturity}"
        series_id = SERIES.get(series_key)
        if not series_id:
            return None
        value = await self._get_latest(series_id)
        if value is not None:
            return value / 100  # Convert percentage to decimal
        return None

    async def get_cpi(self) -> Decimal | None:
        return await self._get_latest(SERIES["cpi"])

    async def get_unemployment_rate(self) -> Decimal | None:
        value = await self._get_latest(SERIES["unemployment"])
        if value is not None:
            return value / 100
        return None

    async def get_mortgage_rate(self) -> Decimal | None:
        value = await self._get_latest(SERIES["mortgage_30y"])
        if value is not None:
            return value / 100
        return None

    async def get_series(
        self,
        series_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Fetch a full series of observations."""
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = start_date.isoformat()
        if end_date:
            params["observation_end"] = end_date.isoformat()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{FRED_BASE_URL}/series/observations", params=params
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("FRED series request failed for %s: %s", series_id, e)
            return []

        return [
            {"date": obs["date"], "value": Decimal(obs["value"])}
            for obs in data.get("observations", [])
            if obs.get("value", ".") != "."
        ]

    async def get_cpi_5yr_cagr(self) -> Decimal | None:
        """Compute CPI compound annual growth rate over the last 5 years.

        Uses CPIAUCSL (Consumer Price Index for All Urban Consumers).
        Returns as decimal (e.g. 0.035 for 3.5%).
        """
        end = date.today()
        start = date(end.year - 5, end.month, 1)
        series = await self.get_series(SERIES["cpi"], start_date=start, end_date=end)

        if len(series) < 2:
            return None

        first_val = float(series[0]["value"])
        last_val = float(series[-1]["value"])

        if first_val <= 0:
            return None

        # Number of years between first and last observation
        first_date = date.fromisoformat(series[0]["date"])
        last_date = date.fromisoformat(series[-1]["date"])
        years = (last_date - first_date).days / 365.25

        if years <= 0:
            return None

        cagr = math.pow(last_val / first_val, 1 / years) - 1
        return Decimal(str(round(cagr, 4)))

    async def get_median_home_price(self) -> Decimal | None:
        """Get the latest national median home sale price (MSPUS series).

        Returns in dollars.
        """
        return await self._get_latest(SERIES["median_home_price"])
