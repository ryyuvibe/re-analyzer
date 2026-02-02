"""Market data routes."""

from fastapi import APIRouter, Depends

from src.api.schemas import MacroResponse
from src.api.deps import get_fred_client
from src.data.fred import FREDClient

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/macro", response_model=MacroResponse)
async def get_macro(fred: FREDClient = Depends(get_fred_client)):
    """Get current macro economic indicators."""
    treasury = await fred.get_treasury_yield("10y")
    mortgage = await fred.get_mortgage_rate()
    cpi = await fred.get_cpi()
    unemployment = await fred.get_unemployment_rate()

    return MacroResponse(
        treasury_10y=treasury,
        mortgage_30y=mortgage,
        cpi=cpi,
        unemployment=unemployment,
    )
