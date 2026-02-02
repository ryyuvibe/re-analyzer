"""Address resolver: orchestrates data sources to build a complete PropertyDetail.

Flow: raw address → geocode → RentCast → county assessor → FRED
Extended flow: + ACS demographics → Walk Score → GreatSchools → neighborhood grade → AI narrative
"""

import logging
from dataclasses import replace
from decimal import Decimal

from src.models.property import PropertyDetail, Address
from src.models.neighborhood import NeighborhoodReport
from src.data.geocode import geocode_address
from src.data.rentcast import RentCastClient
from src.data.county_assessor import estimate_annual_tax, get_property_tax_rate
from src.data.census import CensusClient
from src.data.walkscore import get_walk_score
from src.data.greatschools import get_nearby_schools
from src.data.narrative import generate_neighborhood_narrative
from src.engine.neighborhood import compute_neighborhood_grade

logger = logging.getLogger(__name__)


class PropertyResolver:
    def __init__(self, rentcast_client: RentCastClient | None = None):
        self.rentcast = rentcast_client or RentCastClient()
        self.census = CensusClient()

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

    async def resolve_with_neighborhood(
        self, raw_address: str
    ) -> tuple[PropertyDetail, NeighborhoodReport | None]:
        """Resolve property data plus neighborhood intelligence.

        Returns (PropertyDetail, NeighborhoodReport) tuple.
        The report may be None if all neighborhood data sources fail.
        """
        prop = await self.resolve(raw_address)
        addr = prop.address

        # Step 7: ACS demographics (needs tract FIPS from geocode)
        demographics = None
        if addr.state_fips and addr.county_fips and addr.tract_fips:
            demographics = await self.census.get_neighborhood_demographics(
                addr.state_fips, addr.county_fips, addr.tract_fips,
            )

        # Step 8: Walk Score
        walk_result = await get_walk_score(
            address=addr.full,
            lat=float(addr.latitude),
            lon=float(addr.longitude),
        )

        # Step 9: GreatSchools
        schools = await get_nearby_schools(
            lat=float(addr.latitude),
            lon=float(addr.longitude),
        )

        # Step 10: Compute neighborhood grade
        grade, score = compute_neighborhood_grade(demographics, walk_result, schools)

        # Average school rating
        avg_school_rating = None
        if schools:
            avg_school_rating = Decimal(str(
                sum(s.rating for s in schools) / len(schools)
            )).quantize(Decimal("0.1"))

        # Step 11: AI narrative
        narrative = await generate_neighborhood_narrative(
            address=addr.full,
            demographics=demographics,
            walk_score=walk_result,
            schools=schools,
            grade=grade,
            property_detail=prop,
        )

        report = NeighborhoodReport(
            grade=grade,
            grade_score=score,
            demographics=demographics,
            walk_score=walk_result,
            schools=schools,
            avg_school_rating=avg_school_rating,
            ai_narrative=narrative,
        )

        return prop, report
