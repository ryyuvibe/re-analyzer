"""Macro data fetcher: assembles MacroContext from FRED APIs."""

import logging

from src.data.fred import FREDClient
from src.models.smart_assumptions import MacroContext

logger = logging.getLogger(__name__)


class MacroDataFetcher:
    def __init__(self, fred_client: FREDClient | None = None):
        self.fred = fred_client or FREDClient()

    async def fetch(self) -> MacroContext:
        """Fetch all macro indicators and return a MacroContext.

        Gracefully handles failures — each field may be None.
        """
        mortgage_rate = await self.fred.get_mortgage_rate()
        treasury_10y = await self.fred.get_treasury_yield("10y")
        cpi_current = await self.fred.get_cpi()
        cpi_5yr_cagr = await self.fred.get_cpi_5yr_cagr()
        unemployment = await self.fred.get_unemployment_rate()
        median_home_price = await self.fred.get_median_home_price()

        return MacroContext(
            mortgage_rate_30y=mortgage_rate,
            treasury_10y=treasury_10y,
            cpi_current=cpi_current,
            cpi_5yr_cagr=cpi_5yr_cagr,
            unemployment_rate=unemployment,
            median_home_price_national=median_home_price,
        )
