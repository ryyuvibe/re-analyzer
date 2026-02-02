"""RentCast API client for property data, valuations, and rent estimates."""

import logging
from decimal import Decimal
from datetime import date

import httpx

from src.config import settings
from src.models.property import Address, PropertyDetail, RentalComp, SaleComp

logger = logging.getLogger(__name__)

RENTCAST_BASE_URL = "https://api.rentcast.io/v1"


class RentCastClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.rentcast_api_key
        self.headers = {"X-Api-Key": self.api_key, "Accept": "application/json"}

    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{RENTCAST_BASE_URL}{endpoint}",
                headers=self.headers,
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_property(self, address: Address) -> PropertyDetail | None:
        """Fetch property details from RentCast."""
        try:
            data = await self._get("/properties", {"address": address.full})
        except httpx.HTTPStatusError as e:
            logger.warning("RentCast property lookup failed: %s", e)
            return None

        if not data:
            return None

        # RentCast returns a list; take first match
        prop = data[0] if isinstance(data, list) else data

        # Parse image URL if available
        image_url = prop.get("imageUrl") or None
        if not image_url:
            photos = prop.get("photos")
            if isinstance(photos, list) and photos:
                image_url = photos[0] if isinstance(photos[0], str) else photos[0].get("url")

        logger.debug("RentCast raw property keys: %s", list(prop.keys()))

        return PropertyDetail(
            address=address,
            bedrooms=prop.get("bedrooms", 0),
            bathrooms=Decimal(str(prop.get("bathrooms", 0))),
            sqft=prop.get("squareFootage", 0),
            year_built=prop.get("yearBuilt", 0),
            lot_sqft=prop.get("lotSize", 0),
            property_type=prop.get("propertyType", "SFR"),
            assessed_value=Decimal(str(prop.get("assessedValue", 0))),
            annual_tax=Decimal(str(prop.get("taxAmount", 0))),
            last_sale_price=Decimal(str(prop.get("lastSalePrice", 0))),
            image_url=image_url,
        )

    async def get_rent_estimate(self, address: Address) -> Decimal | None:
        """Get rent estimate from RentCast."""
        try:
            data = await self._get("/avm/rent/long-term", {"address": address.full})
        except httpx.HTTPStatusError:
            return None

        rent = data.get("rent")
        return Decimal(str(rent)) if rent else None

    async def get_value_estimate(self, address: Address) -> Decimal | None:
        """Get property value estimate from RentCast."""
        try:
            data = await self._get("/avm/value", {"address": address.full})
        except httpx.HTTPStatusError:
            return None

        value = data.get("price")
        return Decimal(str(value)) if value else None

    async def get_rental_comps(
        self, address: Address, radius_miles: float = 1.0, limit: int = 10
    ) -> list[RentalComp]:
        """Fetch rental comparables."""
        try:
            data = await self._get(
                "/avm/rent/comparable",
                {
                    "address": address.full,
                    "radius": radius_miles,
                    "limit": limit,
                },
            )
        except httpx.HTTPStatusError:
            return []

        comps = []
        for c in data.get("comparables", []):
            comps.append(RentalComp(
                address=c.get("formattedAddress", ""),
                rent=Decimal(str(c.get("price", 0))),
                bedrooms=c.get("bedrooms", 0),
                bathrooms=Decimal(str(c.get("bathrooms", 0))),
                sqft=c.get("squareFootage", 0),
                distance_miles=Decimal(str(c.get("distance", 0))),
            ))
        return comps

    async def get_sale_comps(
        self, address: Address, radius_miles: float = 1.0, limit: int = 10
    ) -> list[SaleComp]:
        """Fetch comparable sales."""
        try:
            data = await self._get(
                "/avm/value/comparable",
                {
                    "address": address.full,
                    "radius": radius_miles,
                    "limit": limit,
                },
            )
        except httpx.HTTPStatusError:
            return []

        comps = []
        for c in data.get("comparables", []):
            sale_date_str = c.get("lastSaleDate", "")
            try:
                sale_date = date.fromisoformat(sale_date_str) if sale_date_str else date.today()
            except ValueError:
                sale_date = date.today()

            sqft = c.get("squareFootage", 0)
            price = Decimal(str(c.get("price", 0)))
            ppsf = (price / sqft).quantize(Decimal("0.01")) if sqft > 0 else Decimal("0")

            comps.append(SaleComp(
                address=c.get("formattedAddress", ""),
                sale_price=price,
                sale_date=sale_date,
                bedrooms=c.get("bedrooms", 0),
                bathrooms=Decimal(str(c.get("bathrooms", 0))),
                sqft=sqft,
                distance_miles=Decimal(str(c.get("distance", 0))),
                price_per_sqft=ppsf,
            ))
        return comps
