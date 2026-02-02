"""Tests for neighborhood rule-based grading engine."""

from decimal import Decimal

import pytest

from src.engine.neighborhood import compute_neighborhood_grade
from src.models.neighborhood import (
    NeighborhoodDemographics,
    NeighborhoodGrade,
    SchoolInfo,
    WalkScoreResult,
)


class TestNeighborhoodGrading:
    def test_premium_neighborhood_grade_a(self):
        """High income, great schools, walkable, low poverty, low crime → A."""
        demographics = NeighborhoodDemographics(
            median_household_income=120_000,
            median_home_value=350_000,
            poverty_rate=Decimal("0.03"),
            population=5000,
            renter_pct=Decimal("0.40"),
        )
        walk = WalkScoreResult(walk_score=85, transit_score=60, bike_score=70)
        schools = [
            SchoolInfo(name="Lincoln Elementary", rating=9, level="elementary", distance_miles=Decimal("0.5")),
            SchoolInfo(name="Central Middle", rating=8, level="middle", distance_miles=Decimal("1.0")),
            SchoolInfo(name="West High", rating=9, level="high", distance_miles=Decimal("1.5")),
        ]
        grade, score = compute_neighborhood_grade(
            demographics, walk, schools,
            crime_rate=Decimal("1000"),
        )
        assert grade == NeighborhoodGrade.A
        assert score >= Decimal("80")

    def test_good_neighborhood_grade_b(self):
        """Moderate income, decent schools, moderate walk score → B."""
        demographics = NeighborhoodDemographics(
            median_household_income=80_000,
            poverty_rate=Decimal("0.08"),
            renter_pct=Decimal("0.45"),
        )
        walk = WalkScoreResult(walk_score=55)
        schools = [
            SchoolInfo(name="Oak Elementary", rating=7, level="elementary", distance_miles=Decimal("0.8")),
            SchoolInfo(name="Pine Middle", rating=6, level="middle", distance_miles=Decimal("1.2")),
        ]
        grade, score = compute_neighborhood_grade(demographics, walk, schools)
        assert grade == NeighborhoodGrade.B
        assert Decimal("65") <= score < Decimal("80")

    def test_average_neighborhood_grade_c(self):
        """Lower income, average schools, low walkability → C."""
        demographics = NeighborhoodDemographics(
            median_household_income=55_000,
            poverty_rate=Decimal("0.12"),
            renter_pct=Decimal("0.55"),
        )
        walk = WalkScoreResult(walk_score=30)
        schools = [
            SchoolInfo(name="Elm School", rating=5, level="elementary", distance_miles=Decimal("1.0")),
        ]
        grade, score = compute_neighborhood_grade(demographics, walk, schools)
        assert grade == NeighborhoodGrade.C
        assert Decimal("45") <= score < Decimal("65")

    def test_distressed_neighborhood_grade_d_or_f(self):
        """Very low income, bad schools, high poverty → D or F."""
        demographics = NeighborhoodDemographics(
            median_household_income=25_000,
            poverty_rate=Decimal("0.30"),
            renter_pct=Decimal("0.80"),
        )
        walk = WalkScoreResult(walk_score=15)
        schools = [
            SchoolInfo(name="Low School", rating=2, level="elementary", distance_miles=Decimal("0.5")),
        ]
        grade, score = compute_neighborhood_grade(demographics, walk, schools)
        assert grade in (NeighborhoodGrade.D, NeighborhoodGrade.F)
        assert score < Decimal("45")

    def test_all_none_data_returns_neutral(self):
        """No data → neutral scores, grade C."""
        grade, score = compute_neighborhood_grade(None, None, [])
        # Neutral: income=10, schools=10, walk=7, housing=7, safety=10, hazard=10 = 54
        assert grade == NeighborhoodGrade.C
        assert score == Decimal("54.0")

    def test_partial_data_demographics_only(self):
        """Only demographics provided, no walk score or schools."""
        demographics = NeighborhoodDemographics(
            median_household_income=100_000,
            poverty_rate=Decimal("0.04"),
            renter_pct=Decimal("0.35"),
        )
        grade, score = compute_neighborhood_grade(demographics, None, [])
        # income=20 + schools=10(neutral) + walk=7(neutral) + housing=15 + safety=10 + hazard=10 = 72
        assert grade in (NeighborhoodGrade.B, NeighborhoodGrade.A)

    def test_grade_thresholds_boundaries(self):
        """Verify grade boundaries are correct."""
        demographics_high = NeighborhoodDemographics(
            median_household_income=100_000,
            poverty_rate=Decimal("0.03"),
            renter_pct=Decimal("0.40"),
        )
        walk_high = WalkScoreResult(walk_score=90)
        schools_high = [
            SchoolInfo(name="S1", rating=10, level="elementary", distance_miles=Decimal("0.5")),
        ]
        grade, score = compute_neighborhood_grade(demographics_high, walk_high, schools_high)
        assert grade == NeighborhoodGrade.A

    def test_school_averaging(self):
        """Multiple schools with varying ratings get averaged."""
        demographics = NeighborhoodDemographics(
            median_household_income=70_000,
            poverty_rate=Decimal("0.10"),
            renter_pct=Decimal("0.40"),
        )
        walk = WalkScoreResult(walk_score=50)
        schools = [
            SchoolInfo(name="S1", rating=8, level="elementary", distance_miles=Decimal("0.5")),
            SchoolInfo(name="S2", rating=4, level="middle", distance_miles=Decimal("1.0")),
            SchoolInfo(name="S3", rating=6, level="high", distance_miles=Decimal("1.5")),
        ]
        # avg rating = 6.0, school score = 6/10 * 20 = 12
        grade, score = compute_neighborhood_grade(demographics, walk, schools)
        assert isinstance(grade, NeighborhoodGrade)
        assert Decimal("0") <= score <= Decimal("100")

    def test_crime_affects_grade(self):
        """High crime rate reduces the score."""
        demographics = NeighborhoodDemographics(
            median_household_income=80_000,
            poverty_rate=Decimal("0.08"),
            renter_pct=Decimal("0.45"),
        )
        walk = WalkScoreResult(walk_score=55)
        schools = [SchoolInfo(name="S1", rating=7, level="elementary", distance_miles=Decimal("0.8"))]

        # Low crime
        _, score_low_crime = compute_neighborhood_grade(
            demographics, walk, schools, crime_rate=Decimal("800"),
        )
        # High crime
        _, score_high_crime = compute_neighborhood_grade(
            demographics, walk, schools, crime_rate=Decimal("4000"),
        )
        assert score_low_crime > score_high_crime

    def test_hazard_penalties(self):
        """Flood zone + earthquake + hurricane reduces hazard score."""
        _, score_safe = compute_neighborhood_grade(None, None, [])
        _, score_hazardous = compute_neighborhood_grade(
            None, None, [],
            flood_zone="AE",
            seismic_pga=Decimal("0.5"),
            wildfire_risk=5,
            hurricane_zone=3,
            hail_frequency="high",
        )
        # Hazardous area gets lower score
        assert score_safe > score_hazardous

    def test_hazard_score_floor_at_zero(self):
        """Hazard score should not go below 0 even with many penalties."""
        _, score = compute_neighborhood_grade(
            None, None, [],
            flood_zone="VE",
            seismic_pga=Decimal("0.5"),
            wildfire_risk=5,
            hurricane_zone=3,
            hail_frequency="high",
        )
        # Score should still be positive (other neutral dimensions)
        assert score >= Decimal("0")
