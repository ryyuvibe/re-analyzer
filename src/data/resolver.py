"""Address resolver: orchestrates data sources to build a complete PropertyDetail.

Flow: raw address → geocode → RentCast → county assessor → FRED
"""

import logging
from dataclasses import replace
from decimal import Decimal

from src.models.property import PropertyDetail, Address
from src.data.geocode import geocode_address
from src.data.rentcast import RentCastClient
from src.data.county_assessor import estimate_annual_tax, get_property_tax_rate

logger = logging.getLogger(__name__)


class PropertyResolver:
    def __init__(self, rentcast_client: RentCastClient | None = None):
        self.rentcast = rentcast_client or RentCastClient()

    async def resolve(self, raw_address: str) -> PropertyDetail:
        """Resolve a raw address string into a complete PropertyDetail.

        Orchestrates: geocode → property data → rent estimate → tax estimate
        """
        # Step 1: Geocode
        address = await geocode_address(raw_address)
        logger.info("Geocoded: %s → %s, %s %s", raw_address, address.city, address.state, address.zip_code)

        # Step 2: Property data from RentCast
        prop = await self.rentcast.get_property(address)

        if prop is None:
            # Create a minimal PropertyDetail for manual entry
            prop = PropertyDetail(
                address=address,
                bedrooms=0,
                bathrooms=Decimal("0"),
                sqft=0,
                year_built=0,
            )

        # Step 3: Rent estimate
        rent = await self.rentcast.get_rent_estimate(address)
        if rent:
            prop = replace(prop, estimated_rent=rent)

        # Step 4: Value estimate
        value = await self.rentcast.get_value_estimate(address)
        if value:
            prop = replace(prop, estimated_value=value)

        # Step 5: Tax estimate (if not already from RentCast)
        if prop.annual_tax == 0 and prop.estimated_value > 0:
            tax = await estimate_annual_tax(address, prop.estimated_value)
            prop = replace(prop, annual_tax=tax)

        # Step 6: Sale and rental comps
        sale_comps = await self.rentcast.get_sale_comps(address)
        rental_comps = await self.rentcast.get_rental_comps(address)
        prop = replace(prop, sale_comps=sale_comps, rental_comps=rental_comps)

        return prop
