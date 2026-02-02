"""HUD Fair Market Rent (FMR) API client."""

import logging

import httpx

from src.config import settings
from src.models.rent_estimate import HUDFairMarketRent

logger = logging.getLogger(__name__)

HUD_BASE_URL = "https://www.huduser.gov/hudapi/public/fmr/data"


class HUDClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.hud_api_key

    async def get_fmr(self, state_fips: str, county_fips: str) -> HUDFairMarketRent | None:
        """Fetch Fair Market Rent for a county.

        Entity ID format: state_fips + county_fips + "99999" (county-level).
        """
        if not self.api_key:
            logger.debug("HUD API key not configured, skipping FMR lookup")
            return None

        entity_id = f"{state_fips}{county_fips}99999"

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{HUD_BASE_URL}/{entity_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("HUD FMR lookup failed for %s: %s", entity_id, e)
            return None
        except Exception as e:
            logger.warning("HUD FMR request error: %s", e)
            return None

        fmr_data = data.get("data", {})
        if not fmr_data:
            return None

        # Handle both list and dict responses
        if isinstance(fmr_data, list):
            fmr_data = fmr_data[0] if fmr_data else {}

        try:
            return HUDFairMarketRent(
                entity_id=entity_id,
                area_name=fmr_data.get("area_name", fmr_data.get("areaname", "")),
                year=int(fmr_data.get("year", 0)),
                fmr_0br=float(fmr_data.get("Efficiency", fmr_data.get("fmr_0", 0))),
                fmr_1br=float(fmr_data.get("One-Bedroom", fmr_data.get("fmr_1", 0))),
                fmr_2br=float(fmr_data.get("Two-Bedroom", fmr_data.get("fmr_2", 0))),
                fmr_3br=float(fmr_data.get("Three-Bedroom", fmr_data.get("fmr_3", 0))),
                fmr_4br=float(fmr_data.get("Four-Bedroom", fmr_data.get("fmr_4", 0))),
            )
        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse HUD FMR response: %s", e)
            return None
