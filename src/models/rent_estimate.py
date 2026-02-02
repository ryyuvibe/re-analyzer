"""Pydantic models for the tiered rent estimation service."""

from pydantic import BaseModel


class TierResult(BaseModel):
    tier: str  # "llm" | "hud" | "rentcast"
    estimate: float | None
    confidence: str  # "low" | "medium" | "high"
    reasoning: str


class RentEstimate(BaseModel):
    address: str
    estimated_rent: float
    confidence: str  # "low" | "medium" | "high"
    confidence_score: float  # 0.0–1.0
    needs_review: bool
    tier_results: list[TierResult]
    recommended_range: tuple[float, float]  # (low, high)


class HUDFairMarketRent(BaseModel):
    entity_id: str
    area_name: str
    year: int
    fmr_0br: float
    fmr_1br: float
    fmr_2br: float
    fmr_3br: float
    fmr_4br: float

    def fmr_for_beds(self, beds: int) -> float:
        """Return FMR for a given bedroom count (capped at 4)."""
        mapping = {
            0: self.fmr_0br,
            1: self.fmr_1br,
            2: self.fmr_2br,
            3: self.fmr_3br,
            4: self.fmr_4br,
        }
        return mapping.get(min(beds, 4), self.fmr_3br)


class UsageStats(BaseModel):
    total_calls: int
    cache_hits: int
    cache_hit_rate: float
    calls_by_tier: dict[str, int]
    estimated_cost: float
    rentcast_calls_this_month: int
