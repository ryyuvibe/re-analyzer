"""Investor profile routes."""

from uuid import UUID, uuid4

from fastapi import APIRouter

from src.api.schemas import InvestorProfileCreate, InvestorProfileResponse

router = APIRouter(prefix="/api/v1/investor", tags=["investor"])


@router.post("/profile", response_model=InvestorProfileResponse)
async def create_profile(req: InvestorProfileCreate):
    """Create an investor tax profile."""
    # In production, persist to DB. For now, return with generated ID.
    return InvestorProfileResponse(
        id=uuid4(),
        name=req.name,
        filing_status=req.filing_status,
        agi=req.agi,
        marginal_federal_rate=req.marginal_federal_rate,
        marginal_state_rate=req.marginal_state_rate,
        state=req.state,
        is_re_professional=req.is_re_professional,
    )
