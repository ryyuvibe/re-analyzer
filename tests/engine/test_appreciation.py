"""Tests for the dynamic appreciation estimator."""

from decimal import Decimal

import pytest

from src.engine.appreciation import estimate_appreciation
from src.models.neighborhood import NeighborhoodGrade


class TestAppreciation:
    def test_grade_a_with_walkability(self):
        """Grade-A walkable neighborhood → ~4-5% appreciation."""
        rate, detail = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.A,
            cpi_5yr_cagr=Decimal("0.035"),
            walk_score=85,
        )
        # 50% * 4.5% + 30% * 3.5% + 20% * 0.5% = 2.25 + 1.05 + 0.1 = 3.4%
        assert Decimal("0.030") <= rate <= Decimal("0.040")
        assert detail.field_name == "annual_appreciation"
        assert "grade a" in detail.justification.lower()

    def test_grade_d_low_appreciation(self):
        """Grade-D area → low appreciation ~1-2%."""
        rate, detail = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.D,
            cpi_5yr_cagr=Decimal("0.03"),
            walk_score=20,
        )
        # 50% * 1.5% + 30% * 3.0% + 20% * 0 = 0.75 + 0.9 + 0 = 1.65%
        assert Decimal("0.010") <= rate <= Decimal("0.025")

    def test_no_data_defaults(self):
        """No data at all → reasonable default."""
        rate, detail = estimate_appreciation()
        # Uses grade C, default CPI, no walkability
        assert Decimal("0.010") <= rate <= Decimal("0.030")
        assert detail.confidence.value == "low"

    def test_walkability_premium_only_above_80(self):
        """Walk score below 80 gets no premium."""
        rate_low, _ = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.B,
            cpi_5yr_cagr=Decimal("0.03"),
            walk_score=70,
        )
        rate_high, _ = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.B,
            cpi_5yr_cagr=Decimal("0.03"),
            walk_score=90,
        )
        assert rate_high > rate_low

    def test_cpi_affects_result(self):
        """Higher CPI → higher appreciation."""
        rate_low, _ = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.C,
            cpi_5yr_cagr=Decimal("0.02"),
        )
        rate_high, _ = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.C,
            cpi_5yr_cagr=Decimal("0.05"),
        )
        assert rate_high > rate_low

    def test_result_clamped(self):
        """Appreciation should be clamped between 0.5% and 6%."""
        rate, _ = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.F,
            cpi_5yr_cagr=Decimal("0.001"),
        )
        assert rate >= Decimal("0.005")

        rate_max, _ = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.A,
            cpi_5yr_cagr=Decimal("0.10"),
            walk_score=95,
        )
        assert rate_max <= Decimal("0.060")

    def test_detail_has_data_points(self):
        """AssumptionDetail should contain data_points dict."""
        _, detail = estimate_appreciation(
            neighborhood_grade=NeighborhoodGrade.B,
            cpi_5yr_cagr=Decimal("0.035"),
            walk_score=50,
        )
        assert "neighborhood_grade" in detail.data_points
        assert detail.data_points["cpi_5yr_cagr"] == 0.035
