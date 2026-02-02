"""Redfin scraper for property enrichment data.

Uses Redfin's unofficial stingray API endpoints which return JSON.
Falls back gracefully if blocked or unavailable.
"""

import logging
from decimal import Decimal

import httpx

from src.models.property import Address

logger = logging.getLogger(__name__)

REDFIN_URL = "https://www.redfin.com/stingray/api/home/details/belowTheFold"
REDFIN_SEARCH_URL = "https://www.redfin.com/stingray/do/location-autocomplete"


class RedfinClient:
    """Redfin data client using their unofficial JSON API.

    Caching is essential — Redfin will block aggressive requests.
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

    async def search_address(self, address: Address) -> dict | None:
        """Search Redfin for a property URL/ID."""
        params = {"location": address.full, "v": "2"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    REDFIN_SEARCH_URL, params=params, headers=self.headers
                )
                resp.raise_for_status()
                # Redfin returns `{}&&{...}` format
                text = resp.text
                if text.startswith("{}&&"):
                    text = text[4:]
                import json
                data = json.loads(text)
                results = data.get("payload", {}).get("exactMatch", {})
                return results if results else None
        except Exception as e:
            logger.warning("Redfin search failed: %s", e)
            return None

    async def get_price_history(self, property_url: str) -> list[dict]:
        """Fetch price history for a property.

        Requires a Redfin property URL path (e.g., /CA/San-Francisco/...).
        """
        # This would use Selenium with undetected-chromedriver for full scraping.
        # For now, return empty — this is an enrichment source, not primary.
        logger.info("Redfin price history not implemented (requires Selenium)")
        return []
