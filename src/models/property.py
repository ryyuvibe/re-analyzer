from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date


@dataclass(frozen=True)
class Address:
    street: str
    city: str
    state: str
    zip_code: str
    county: str = ""
    latitude: Decimal = Decimal("0")
    longitude: Decimal = Decimal("0")
    state_fips: str = ""
    county_fips: str = ""
    tract_fips: str = ""

    @property
    def full(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"


@dataclass(frozen=True)
class PropertyDetail:
    address: Address
    bedrooms: int
    bathrooms: Decimal
    sqft: int
    year_built: int
    lot_sqft: int = 0
    property_type: str = "SFR"  # SFR, Condo, Townhouse, Multi-Family
    stories: int = 1

    # Valuation
    estimated_value: Decimal = Decimal("0")
    last_sale_price: Decimal = Decimal("0")
    last_sale_date: date | None = None

    # Tax / Assessment
    assessed_value: Decimal = Decimal("0")
    annual_tax: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")

    # Rental
    estimated_rent: Decimal = Decimal("0")
    rental_comps: list["RentalComp"] = field(default_factory=list)

    # Sale comps
    sale_comps: list["SaleComp"] = field(default_factory=list)


@dataclass(frozen=True)
class RentalComp:
    address: str
    rent: Decimal
    bedrooms: int
    bathrooms: Decimal
    sqft: int
    distance_miles: Decimal


@dataclass(frozen=True)
class SaleComp:
    address: str
    sale_price: Decimal
    sale_date: date
    bedrooms: int
    bathrooms: Decimal
    sqft: int
    distance_miles: Decimal
    price_per_sqft: Decimal
