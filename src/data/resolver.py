"""Address resolver: orchestrates data sources to build a complete PropertyDetail.

Flow: raw address → geocode → RentCast → county assessor → FRED
Extended flow: + ACS demographics → Walk Score → GreatSchools → neighborhood grade → AI narrative
Full flow: + macro context + hazard data (FEMA, USGS, wildfire, crime)
"""

import logging
from dataclasses import replace
from decimal import Decimal

from src.models.property import PropertyDetail, Address
from src.models.neighborhood import NeighborhoodReport
from src.models.smart_assumptions import MacroContext
from src.data.geocode import geocode_address
from src.data.rent_estimator import RentEstimator
from src.data.rentcast import RentCastClient
from src.models.rent_estimate import RentEstimate
from src.data.county_assessor import estimate_annual_tax, get_property_tax_rate
from src.data.census import CensusClient
from src.data.walkscore import get_walk_score
from src.data.greatschools import get_nearby_schools
from src.data.narrative import generate_neighborhood_narrative
from src.data.macro import MacroDataFetcher
from src.data.fema import get_flood_zone
from src.data.usgs_seismic import get_seismic_pga, get_seismic_pga_from_state
from src.data.wildfire import get_wildfire_risk, get_wildfire_risk_from_state
from src.data.noaa_hazards import get_hurricane_zone, get_hail_frequency
from src.data.fbi_crime import get_crime_rate
from src.data.climate import get_climate_zone
from src.data.osm import get_traffic_noise_score
from src.engine.neighborhood import compute_neighborhood_grade

logger = logging.getLogger(__name__)


class PropertyResolver:
    def __init__(self, rentcast_client: RentCastClient | None = None):
        self.rentcast = rentcast_client or RentCastClient()
        self.census = CensusClient()
        self.rent_estimator = RentEstimator()

    async def resolve(self, raw_address: str) -> tuple[PropertyDetail, RentEstimate | None]:
        """Resolve a raw address string into a complete PropertyDetail.

        Orchestrates: geocode → property data → rent estimate → tax estimate

        Returns (PropertyDetail, RentEstimate | None) tuple.
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

        # Step 3: Rent estimate (tiered: LLM → HUD FMR → RentCast)
        rent_estimate: RentEstimate | None = None
        try:
            rent_estimate = await self.rent_estimator.estimate_rent(
                address=address.full,
                beds=prop.bedrooms,
                baths=float(prop.bathrooms),
                sqft=prop.sqft,
                property_type=prop.property_type,
            )
            if rent_estimate and rent_estimate.estimated_rent > 0:
                prop = replace(prop, estimated_rent=Decimal(str(rent_estimate.estimated_rent)))
        except Exception as e:
            logger.warning("Tiered rent estimation failed, falling back to RentCast: %s", e)
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

        return prop, rent_estimate

    async def resolve_with_neighborhood(
        self, raw_address: str
    ) -> tuple[PropertyDetail, NeighborhoodReport | None, RentEstimate | None]:
        """Resolve property data plus neighborhood intelligence.

        Returns (PropertyDetail, NeighborhoodReport, RentEstimate) tuple.
        The report may be None if all neighborhood data sources fail.
        """
        prop, rent_estimate = await self.resolve(raw_address)
        addr = prop.address
        state = addr.state or "OH"
        lat = float(addr.latitude) if addr.latitude else 0.0
        lon = float(addr.longitude) if addr.longitude else 0.0

        # Step 7: ACS demographics (needs tract FIPS from geocode)
        demographics = None
        if addr.state_fips and addr.county_fips and addr.tract_fips:
            demographics = await self.census.get_neighborhood_demographics(
                addr.state_fips, addr.county_fips, addr.tract_fips,
            )

        # Step 8: Walk Score
        walk_result = await get_walk_score(
            address=addr.full,
            lat=lat,
            lon=lon,
        )

        # Step 9: GreatSchools
        schools = await get_nearby_schools(
            lat=lat,
            lon=lon,
        )

        # Step 10: Hazard data
        flood_zone = None
        seismic_pga = None
        wildfire_risk_val = None
        traffic_noise = None

        if lat and lon:
            flood_zone = await get_flood_zone(lat, lon)
            seismic_pga = await get_seismic_pga(lat, lon)
            if seismic_pga is None:
                seismic_pga = get_seismic_pga_from_state(state)
            wildfire_risk_val = await get_wildfire_risk(lat, lon)
            if wildfire_risk_val is None:
                wildfire_risk_val = get_wildfire_risk_from_state(state)
            traffic_noise = await get_traffic_noise_score(lat, lon)

        hurricane_zone_val = get_hurricane_zone(state)
        hail_freq = get_hail_frequency(state)
        prop_crime, violent_crime = get_crime_rate(state)
        climate_zone = get_climate_zone(state)

        # Step 11: Compute neighborhood grade (expanded)
        grade, score = compute_neighborhood_grade(
            demographics, walk_result, schools,
            crime_rate=prop_crime,
            flood_zone=flood_zone,
            seismic_pga=seismic_pga,
            wildfire_risk=wildfire_risk_val,
            hurricane_zone=hurricane_zone_val,
            hail_frequency=hail_freq,
        )

        # Average school rating
        avg_school_rating = None
        if schools:
            avg_school_rating = Decimal(str(
                sum(s.rating for s in schools) / len(schools)
            )).quantize(Decimal("0.1"))

        # Step 12: AI narrative
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
            flood_zone=flood_zone,
            seismic_pga=seismic_pga,
            wildfire_risk=wildfire_risk_val,
            hurricane_zone=hurricane_zone_val,
            hail_frequency=hail_freq,
            crime_rate=prop_crime,
            climate_zone=climate_zone.value,
            traffic_noise_score=traffic_noise,
        )

        return prop, report, rent_estimate

    async def resolve_full(
        self, raw_address: str
    ) -> tuple[PropertyDetail, NeighborhoodReport | None, MacroContext, RentEstimate | None]:
        """Full resolution: property + neighborhood + macro context.

        Returns (PropertyDetail, NeighborhoodReport | None, MacroContext, RentEstimate | None).
        """
        prop, neighborhood, rent_estimate = await self.resolve_with_neighborhood(raw_address)

        macro_fetcher = MacroDataFetcher()
        macro = await macro_fetcher.fetch()

        return prop, neighborhood, macro, rent_estimate
