"""Address normalization and geocoding via Census Geocoder API (free, no key needed)."""

import logging
from decimal import Decimal

import httpx

from src.models.property import Address

logger = logging.getLogger(__name__)

CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"


async def geocode_address(raw_address: str) -> Address:
    """Geocode a raw address string using the Census Geocoder API.

    Returns an Address with normalized fields, lat/lon, and county.
    """
    params = {
        "address": raw_address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(CENSUS_GEOCODER_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        raise ValueError(f"Could not geocode address: {raw_address}")

    match = matches[0]
    coords = match["coordinates"]
    components = match["addressComponents"]
    geographies = match.get("geographies", {})

    # Extract county from geographies
    counties = geographies.get("Counties", [])
    county_name = counties[0]["NAME"] if counties else ""

    # Extract state from geographies or address components
    state = components.get("state", "")
    city = components.get("city", "")
    zip_code = components.get("zip", "")
    street = f"{components.get('preQualifier', '')} {components.get('preDirection', '')} {components.get('streetName', '')} {components.get('suffixType', '')} {components.get('suffixDirection', '')}".strip()
    street_num = components.get("fromAddress", "")
    if street_num:
        street = f"{street_num} {street}"

    return Address(
        street=match.get("matchedAddress", raw_address).split(",")[0].strip(),
        city=city,
        state=state,
        zip_code=zip_code,
        county=county_name,
        latitude=Decimal(str(coords["y"])),
        longitude=Decimal(str(coords["x"])),
    )
