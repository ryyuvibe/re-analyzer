"""Dynamic appreciation rate estimator.

Weighted composite:
  50% neighborhood grade premium
  30% CPI 5yr CAGR (inflation floor)
  20% walkability/amenity premium
"""

from decimal import Decimal

from src.models.neighborhood import NeighborhoodGrade
from src.models.smart_assumptions import AssumptionDetail, AssumptionSource, Confidence

# Appreciation premium by neighborhood grade
GRADE_PREMIUMS: dict[NeighborhoodGrade, Decimal] = {
    NeighborhoodGrade.A: Decimal("0.045"),
    NeighborhoodGrade.B: Decimal("0.035"),
    NeighborhoodGrade.C: Decimal("0.025"),
    NeighborhoodGrade.D: Decimal("0.015"),
    NeighborhoodGrade.F: Decimal("0.005"),
}

DEFAULT_CPI_CAGR = Decimal("0.03")  # Fallback if FRED unavailable
WALKABILITY_PREMIUM = Decimal("0.005")  # +0.5% for walk score >= 80


def estimate_appreciation(
    neighborhood_grade: NeighborhoodGrade | None = None,
    cpi_5yr_cagr: Decimal | None = None,
    walk_score: int | None = None,
) -> tuple[Decimal, AssumptionDetail]:
    """Estimate annual property appreciation rate.

    Returns (appreciation_rate, AssumptionDetail with breakdown).
    """
    grade = neighborhood_grade or NeighborhoodGrade.C
    cpi = cpi_5yr_cagr if cpi_5yr_cagr is not None else DEFAULT_CPI_CAGR

    # 50% neighborhood grade
    grade_component = GRADE_PREMIUMS.get(grade, Decimal("0.025"))

    # 30% CPI inflation floor
    cpi_component = cpi

    # 20% walkability premium
    walk_component = Decimal("0")
    if walk_score is not None and walk_score >= 80:
        walk_component = WALKABILITY_PREMIUM

    # Weighted composite
    result = (
        grade_component * Decimal("0.50")
        + cpi_component * Decimal("0.30")
        + walk_component * Decimal("0.20")
    )

    # Add baseline — the components above are premium-weighted,
    # so we ensure a reasonable floor/ceiling
    result = max(Decimal("0.005"), min(Decimal("0.06"), result))
    result = result.quantize(Decimal("0.001"))

    components = [
        f"Neighborhood grade {grade.value}: {float(grade_component)*100:.1f}% (50% weight)",
        f"CPI 5yr CAGR: {float(cpi)*100:.1f}% (30% weight)",
    ]
    if walk_component > 0:
        components.append(f"Walkability premium: +{float(walk_component)*100:.1f}% (walk score {walk_score}, 20% weight)")
    else:
        ws_str = f"walk score {walk_score}" if walk_score is not None else "no data"
        components.append(f"No walkability premium ({ws_str}, need >= 80)")

    has_data = neighborhood_grade is not None or cpi_5yr_cagr is not None
    confidence = Confidence.MEDIUM if has_data else Confidence.LOW
    source = AssumptionSource.ESTIMATED if has_data else AssumptionSource.DEFAULT

    detail = AssumptionDetail(
        field_name="annual_appreciation",
        value=result,
        source=source,
        confidence=confidence,
        justification=f"Appreciation: {float(result)*100:.1f}%/yr. {'; '.join(components)}",
        data_points={
            "neighborhood_grade": grade.value,
            "cpi_5yr_cagr": float(cpi),
            "walk_score": walk_score,
            "grade_component": float(grade_component),
            "cpi_component": float(cpi_component),
            "walk_component": float(walk_component),
        },
    )

    return result, detail
