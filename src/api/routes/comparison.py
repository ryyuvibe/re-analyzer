"""RE vs equities comparison routes."""

from fastapi import APIRouter, HTTPException

from src.api.schemas import ComparisonRequest, ComparisonResponse

router = APIRouter(prefix="/api/v1/comparison", tags=["comparison"])


@router.post("/run", response_model=ComparisonResponse)
async def run_comparison(req: ComparisonRequest):
    """Run RE vs S&P 500 comparison for a saved analysis."""
    # In production, load analysis from DB, run comparison engine.
    raise HTTPException(status_code=501, detail="Requires database connection")
