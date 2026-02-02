"""Neighborhood rule-based grading engine."""

from decimal import Decimal

from src.models.neighborhood import (
    NeighborhoodDemographics,
    NeighborhoodGrade,
    SchoolInfo,
    WalkScoreResult,
)

NATIONAL_MEDIAN_INCOME = 75_000


def _income_score(demographics: NeighborhoodDemographics | None) -> Decimal:
    """Score 0-25 based on median household income vs national median."""
    if demographics is None or demographics.median_household_income is None:
        return Decimal("12")  # neutral
    income = demographics.median_household_income
    if income >= 100_000:
        return Decimal("25")
    if income >= 75_000:
        return Decimal("20")
    if income >= 50_000:
        return Decimal("15")
    if income >= 35_000:
        return Decimal("10")
    return Decimal("5")


def _school_score(schools: list[SchoolInfo]) -> Decimal:
    """Score 0-25 based on average school rating (1-10 scale)."""
    if not schools:
        return Decimal("12")  # neutral
    avg = sum(s.rating for s in schools) / len(schools)
    return (Decimal(str(avg)) / 10 * 25).quantize(Decimal("0.1"))


def _walkability_score(walk_score: WalkScoreResult | None) -> Decimal:
    """Score 0-25 based on walk score (0-100)."""
    if walk_score is None or walk_score.walk_score is None:
        return Decimal("12")  # neutral
    return (Decimal(str(walk_score.walk_score)) / 100 * 25).quantize(Decimal("0.1"))


def _housing_stability_score(demographics: NeighborhoodDemographics | None) -> Decimal:
    """Score 0-25 based on poverty rate and renter percentage.

    Low poverty is good. Moderate renter % (30-60%) is ideal for landlords —
    signals rental demand without being a distressed area.
    """
    if demographics is None:
        return Decimal("12")  # neutral

    score = Decimal("0")

    # Poverty component (0-15): lower poverty = higher score
    if demographics.poverty_rate is not None:
        pov = float(demographics.poverty_rate)
        if pov < 0.05:
            score += Decimal("15")
        elif pov < 0.10:
            score += Decimal("12")
        elif pov < 0.15:
            score += Decimal("9")
        elif pov < 0.25:
            score += Decimal("5")
        else:
            score += Decimal("2")

    # Renter % component (0-10): moderate renter % best for landlords
    if demographics.renter_pct is not None:
        rp = float(demographics.renter_pct)
        if 0.30 <= rp <= 0.60:
            score += Decimal("10")  # sweet spot
        elif 0.20 <= rp < 0.30 or 0.60 < rp <= 0.70:
            score += Decimal("7")
        elif rp < 0.20:
            score += Decimal("5")  # very owner-heavy, less rental demand
        else:
            score += Decimal("3")  # very renter-heavy, may indicate distress

    return score


def compute_neighborhood_grade(
    demographics: NeighborhoodDemographics | None,
    walk_score: WalkScoreResult | None,
    schools: list[SchoolInfo],
) -> tuple[NeighborhoodGrade, Decimal]:
    """Compute a composite neighborhood grade from available data.

    Returns (grade, score) where score is 0-100.
    """
    total = (
        _income_score(demographics)
        + _school_score(schools)
        + _walkability_score(walk_score)
        + _housing_stability_score(demographics)
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
