"""Neighborhood rule-based grading engine.

Scoring dimensions (0-100 total):
  Income:           0-20
  Schools:          0-20
  Walkability:      0-15
  Housing stability: 0-15
  Safety (crime):   0-20
  Natural hazard:   0-10
"""

from decimal import Decimal

from src.models.neighborhood import (
    NeighborhoodDemographics,
    NeighborhoodGrade,
    SchoolInfo,
    WalkScoreResult,
)

NATIONAL_MEDIAN_INCOME = 75_000


def _income_score(demographics: NeighborhoodDemographics | None) -> Decimal:
    """Score 0-20 based on median household income vs national median."""
    if demographics is None or demographics.median_household_income is None:
        return Decimal("10")  # neutral
    income = demographics.median_household_income
    if income >= 100_000:
        return Decimal("20")
    if income >= 75_000:
        return Decimal("16")
    if income >= 50_000:
        return Decimal("12")
    if income >= 35_000:
        return Decimal("8")
    return Decimal("4")


def _school_score(schools: list[SchoolInfo]) -> Decimal:
    """Score 0-20 based on average school rating (1-10 scale)."""
    if not schools:
        return Decimal("10")  # neutral
    avg = sum(s.rating for s in schools) / len(schools)
    return (Decimal(str(avg)) / 10 * 20).quantize(Decimal("0.1"))


def _walkability_score(walk_score: WalkScoreResult | None) -> Decimal:
    """Score 0-15 based on walk score (0-100)."""
    if walk_score is None or walk_score.walk_score is None:
        return Decimal("7")  # neutral
    return (Decimal(str(walk_score.walk_score)) / 100 * 15).quantize(Decimal("0.1"))


def _housing_stability_score(demographics: NeighborhoodDemographics | None) -> Decimal:
    """Score 0-15 based on poverty rate and renter percentage.

    Low poverty is good. Moderate renter % (30-60%) is ideal for landlords.
    """
    if demographics is None:
        return Decimal("7")  # neutral

    score = Decimal("0")

    # Poverty component (0-8): lower poverty = higher score
    if demographics.poverty_rate is not None:
        pov = float(demographics.poverty_rate)
        if pov < 0.05:
            score += Decimal("8")
        elif pov < 0.10:
            score += Decimal("6")
        elif pov < 0.15:
            score += Decimal("5")
        elif pov < 0.25:
            score += Decimal("3")
        else:
            score += Decimal("1")

    # Renter % component (0-7): moderate renter % best for landlords
    if demographics.renter_pct is not None:
        rp = float(demographics.renter_pct)
        if 0.30 <= rp <= 0.60:
            score += Decimal("7")  # sweet spot
        elif 0.20 <= rp < 0.30 or 0.60 < rp <= 0.70:
            score += Decimal("5")
        elif rp < 0.20:
            score += Decimal("3")  # very owner-heavy
        else:
            score += Decimal("2")  # very renter-heavy

    return score


def _safety_score(crime_rate: Decimal | None) -> Decimal:
    """Score 0-20 based on property crime rate per 100K (inverse).

    Lower crime = higher score.
    National average ~ 2000/100K property crime.
    """
    if crime_rate is None:
        return Decimal("10")  # neutral

    rate = float(crime_rate)
    if rate < 1000:
        return Decimal("20")
    if rate < 1500:
        return Decimal("17")
    if rate < 2000:
        return Decimal("14")
    if rate < 2500:
        return Decimal("11")
    if rate < 3000:
        return Decimal("8")
    if rate < 3500:
        return Decimal("5")
    return Decimal("2")


def _hazard_score(
    flood_zone: str | None = None,
    seismic_pga: Decimal | None = None,
    wildfire_risk: int | None = None,
    hurricane_zone: int | None = None,
    hail_frequency: str | None = None,
) -> Decimal:
    """Score 0-10 based on natural hazard risk (inverse — lower risk = higher score).

    Each hazard contributes a penalty. Start at 10, subtract.
    """
    score = Decimal("10")

    # Flood penalty
    if flood_zone:
        fz = flood_zone.upper()
        if fz in ("V", "VE"):
            score -= Decimal("3")
        elif fz in ("A", "AE", "AH", "AO"):
            score -= Decimal("2")
        elif fz in ("X500", "B"):
            score -= Decimal("1")

    # Seismic penalty
    if seismic_pga is not None:
        if seismic_pga >= Decimal("0.4"):
            score -= Decimal("2")
        elif seismic_pga >= Decimal("0.2"):
            score -= Decimal("1")

    # Wildfire penalty
    if wildfire_risk is not None:
        if wildfire_risk >= 4:
            score -= Decimal("2")
        elif wildfire_risk >= 3:
            score -= Decimal("1")

    # Hurricane penalty
    if hurricane_zone is not None:
        if hurricane_zone >= 3:
            score -= Decimal("2")
        elif hurricane_zone >= 1:
            score -= Decimal("1")

    # Hail penalty
    if hail_frequency == "high":
        score -= Decimal("1")

    return max(Decimal("0"), score)


def compute_neighborhood_grade(
    demographics: NeighborhoodDemographics | None,
    walk_score: WalkScoreResult | None,
    schools: list[SchoolInfo],
    crime_rate: Decimal | None = None,
    flood_zone: str | None = None,
    seismic_pga: Decimal | None = None,
    wildfire_risk: int | None = None,
    hurricane_zone: int | None = None,
    hail_frequency: str | None = None,
) -> tuple[NeighborhoodGrade, Decimal]:
    """Compute a composite neighborhood grade from available data.

    Returns (grade, score) where score is 0-100.
    """
    total = (
        _income_score(demographics)
        + _school_score(schools)
        + _walkability_score(walk_score)
        + _housing_stability_score(demographics)
        + _safety_score(crime_rate)
        + _hazard_score(flood_zone, seismic_pga, wildfire_risk, hurricane_zone, hail_frequency)
    )

    total = total.quantize(Decimal("0.1"))

    if total >= 80:
        grade = NeighborhoodGrade.A
    elif total >= 65:
        grade = NeighborhoodGrade.B
    elif total >= 45:
        grade = NeighborhoodGrade.C
    elif total >= 30:
        grade = NeighborhoodGrade.D
    else:
        grade = NeighborhoodGrade.F

    return grade, total
