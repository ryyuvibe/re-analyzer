"""Claude API client for generating neighborhood investment narratives."""

import logging

from src.config import settings
from src.models.neighborhood import (
    NeighborhoodDemographics,
    NeighborhoodGrade,
    SchoolInfo,
    WalkScoreResult,
)
from src.models.property import PropertyDetail

logger = logging.getLogger(__name__)


async def generate_neighborhood_narrative(
    address: str,
    demographics: NeighborhoodDemographics | None,
    walk_score: WalkScoreResult | None,
    schools: list[SchoolInfo],
    grade: NeighborhoodGrade,
    property_detail: PropertyDetail,
) -> str | None:
    """Generate a qualitative neighborhood assessment using Claude API.

    Returns None if the API key is missing or the call fails.
    Uses claude-haiku-4-5-20250514 for speed and cost efficiency (~$0.001/call).
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        logger.debug("Anthropic API key not configured, skipping narrative")
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed, skipping narrative")
        return None

    # Build data context for the prompt
    lines = [
        f"Address: {address}",
        f"Property type: {property_detail.property_type}, {property_detail.sqft} sqft, built {property_detail.year_built}",
        f"Estimated value: ${property_detail.estimated_value:,.0f}" if property_detail.estimated_value else "",
        f"Estimated rent: ${property_detail.estimated_rent:,.0f}/mo" if property_detail.estimated_rent else "",
        f"Neighborhood grade: {grade.value}",
    ]

    if demographics:
        lines.append("\nDemographics (Census Tract):")
        if demographics.median_household_income is not None:
            lines.append(f"  Median household income: ${demographics.median_household_income:,}")
        if demographics.median_home_value is not None:
            lines.append(f"  Median home value: ${demographics.median_home_value:,}")
        if demographics.poverty_rate is not None:
            lines.append(f"  Poverty rate: {float(demographics.poverty_rate) * 100:.1f}%")
        if demographics.population is not None:
            lines.append(f"  Tract population: {demographics.population:,}")
        if demographics.renter_pct is not None:
            lines.append(f"  Renter percentage: {float(demographics.renter_pct) * 100:.1f}%")

    if walk_score:
        lines.append("\nWalkability:")
        if walk_score.walk_score is not None:
            lines.append(f"  Walk Score: {walk_score.walk_score}/100")
        if walk_score.transit_score is not None:
            lines.append(f"  Transit Score: {walk_score.transit_score}/100")
        if walk_score.bike_score is not None:
            lines.append(f"  Bike Score: {walk_score.bike_score}/100")

    if schools:
        lines.append("\nNearby Schools:")
        for s in schools[:5]:
            lines.append(f"  {s.name} ({s.level}) — {s.rating}/10, {s.distance_miles} mi")

    data_block = "\n".join(line for line in lines if line)

    prompt = f"""You are a real estate investment analyst. Based on the data below, write a 3-4 paragraph neighborhood assessment for a rental property investor. Be direct and practical.

Cover:
1. Neighborhood character and likely tenant profile
2. Investment outlook — appreciation potential and rental demand drivers
3. Any gentrification signals from the demographic data
4. Risks or red flags

Data:
{data_block}

Write the assessment now. No headers or bullet points — flowing paragraphs only."""

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-haiku-4-5-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning("Claude narrative generation failed: %s", e)
        return None
