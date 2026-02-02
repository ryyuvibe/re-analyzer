"""Tests for the data-driven maintenance cost estimator."""

from decimal import Decimal

import pytest

from src.engine.maintenance import estimate_maintenance_pct
from src.data.climate import ClimateZone


class TestMaintenance:
    def test_new_build_turnkey(self):
        """New turnkey property → low maintenance."""
        pct, detail = estimate_maintenance_pct(
            year_built=2020,
            condition_grade="turnkey",
            climate_zone=ClimateZone.MIXED_HUMID,
        )
        assert Decimal("0.03") <= pct <= Decimal("0.04")
        assert detail.field_name == "maintenance_pct"

    def test_old_property_heavy_wear(self):
        """Old property with heavy condition → high maintenance."""
        pct, _ = estimate_maintenance_pct(
            year_built=1940,
            condition_grade="heavy",
            climate_zone=ClimateZone.COLD,
        )
        assert pct >= Decimal("0.08")

    def test_hot_humid_climate_increases(self):
        """Hot/humid climate should increase maintenance."""
        pct_mild, _ = estimate_maintenance_pct(
            year_built=2000,
            condition_grade="turnkey",
            climate_zone=ClimateZone.MIXED_DRY,
        )
        pct_hot, _ = estimate_maintenance_pct(
            year_built=2000,
            condition_grade="turnkey",
            climate_zone=ClimateZone.HOT_HUMID,
        )
        assert pct_hot > pct_mild

    def test_renter_density_increases(self):
        """High renter density increases maintenance."""
        pct_low, _ = estimate_maintenance_pct(
            year_built=2000,
            condition_grade="turnkey",
            renter_pct=Decimal("0.30"),
        )
        pct_high, _ = estimate_maintenance_pct(
            year_built=2000,
            condition_grade="turnkey",
            renter_pct=Decimal("0.80"),
        )
        assert pct_high > pct_low

    def test_result_clamped(self):
        """Maintenance should be clamped between 3% and 15%."""
        pct_min, _ = estimate_maintenance_pct(
            year_built=2024,
            condition_grade="turnkey",
            climate_zone=ClimateZone.MIXED_DRY,
        )
        assert pct_min >= Decimal("0.03")

        pct_max, _ = estimate_maintenance_pct(
            year_built=1890,
            condition_grade="full_gut",
            climate_zone=ClimateZone.VERY_COLD,
            renter_pct=Decimal("0.90"),
        )
        assert pct_max <= Decimal("0.15")

    def test_detail_justification(self):
        """Detail justification should explain the factors."""
        _, detail = estimate_maintenance_pct(
            year_built=1960,
            condition_grade="medium",
            climate_zone=ClimateZone.HOT_HUMID,
            renter_pct=Decimal("0.55"),
        )
        assert "Age base" in detail.justification
        assert "Climate" in detail.justification
        assert "Renter wear" in detail.justification

    def test_condition_multipliers(self):
        """Full gut rehab should have higher multiplier than turnkey."""
        pct_turnkey, _ = estimate_maintenance_pct(year_built=2000, condition_grade="turnkey")
        pct_gut, _ = estimate_maintenance_pct(year_built=2000, condition_grade="full_gut")
        assert pct_gut > pct_turnkey
