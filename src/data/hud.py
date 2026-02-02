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

    async def get_fmr(
        self, state_fips: str, county_fips: str, zip_code: str = ""
    ) -> HUDFairMarketRent | None:
        """Fetch Fair Market Rent for a county.

        Entity ID format: state_fips + county_fips + "99999" (county-level).
        If zip_code is provided and the area uses Small Area FMR, returns
        the zip-level rate; otherwise falls back to the MSA-level rate.
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

        top = data.get("data", {})
        if not top:
            return None

        area_name = top.get("area_name", top.get("areaname", ""))
        year = top.get("year", 0)

        # FMR values live inside basicdata (Small Area FMR areas) or directly on top
        basicdata = top.get("basicdata")
        if isinstance(basicdata, list) and basicdata:
            # Try zip-level match first, fall back to MSA-level row
            fmr_row = None
            if zip_code:
                for row in basicdata:
                    if str(row.get("zip_code", "")) == zip_code:
                        fmr_row = row
                        break
            if fmr_row is None:
                # First entry is typically "MSA level"
                fmr_row = basicdata[0]
        else:
            # Non-SAFMR response: values directly on top-level data
            fmr_row = top

        try:
            return HUDFairMarketRent(
                entity_id=entity_id,
                area_name=area_name,
                year=int(year),
                fmr_0br=float(fmr_row.get("Efficiency", fmr_row.get("fmr_0", 0))),
                fmr_1br=float(fmr_row.get("One-Bedroom", fmr_row.get("fmr_1", 0))),
                fmr_2br=float(fmr_row.get("Two-Bedroom", fmr_row.get("fmr_2", 0))),
                fmr_3br=float(fmr_row.get("Three-Bedroom", fmr_row.get("fmr_3", 0))),
                fmr_4br=float(fmr_row.get("Four-Bedroom", fmr_row.get("fmr_4", 0))),
            )
        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse HUD FMR response: %s", e)
            return None
