"""Protocol definitions for data sources.

Each protocol defines the interface that concrete data source implementations must satisfy.
"""

from typing import Protocol, runtime_checkable
from decimal import Decimal

from src.models.property import PropertyDetail, Address, RentalComp, SaleComp


@runtime_checkable
class GeocodeSource(Protocol):
    async def geocode(self, raw_address: str) -> Address:
        """Normalize and geocode an address string."""
        ...


@runtime_checkable
class PropertyDataSource(Protocol):
    async def get_property(self, address: Address) -> PropertyDetail | None:
        """Fetch property details for a given address."""
        ...

    async def get_sale_comps(
        self, address: Address, radius_miles: float = 1.0, limit: int = 10
    ) -> list[SaleComp]:
        """Fetch comparable sales near an address."""
        ...

    async def get_valuation(self, address: Address) -> Decimal | None:
        """Get estimated market value."""
        ...


@runtime_checkable
class RentalDataSource(Protocol):
    async def get_rent_estimate(self, address: Address) -> Decimal | None:
        """Get estimated monthly rent for a property."""
        ...

    async def get_rental_comps(
        self, address: Address, radius_miles: float = 1.0, limit: int = 10
    ) -> list[RentalComp]:
        """Fetch rental comparables near an address."""
        ...


@runtime_checkable
class MacroDataSource(Protocol):
    async def get_treasury_yield(self, maturity: str = "10y") -> Decimal | None:
        """Get current treasury yield."""
        ...

    async def get_cpi(self) -> Decimal | None:
        """Get current CPI year-over-year change."""
        ...

    async def get_unemployment_rate(self) -> Decimal | None:
        """Get current unemployment rate."""
        ...


@runtime_checkable
class TaxDataSource(Protocol):
    async def get_property_tax_rate(self, county: str, state: str) -> Decimal | None:
        """Get effective property tax rate for a county."""
        ...

    async def get_assessed_value(self, address: Address) -> Decimal | None:
        """Get assessed value from county assessor."""
        ...
