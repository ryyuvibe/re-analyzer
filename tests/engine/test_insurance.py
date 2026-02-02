"""Tests for insurance estimation engine."""

from decimal import Decimal

import pytest

from src.engine.insurance import estimate_annual_insurance


class TestInsuranceEstimator:
    def test_basic_ohio_sfr(self):
        """Standard Ohio SFR — base rate * value, no surcharges."""
        result = estimate_annual_insurance(
            property_value=Decimal("200000"),
            sqft=1500,
            year_built=2005,
            state="OH",
            property_type="SFR",
        )
        # 200000 * 0.0035 = $700 → below minimum → $800
        assert result == Decimal("800")

    def test_higher_value_ohio(self):
        """Higher value property in Ohio — above minimum."""
        result = estimate_annual_insurance(
            property_value=Decimal("350000"),
            sqft=2000,
            year_built=2010,
            state="OH",
            property_type="SFR",
        )
        # 350000 * 0.0035 = $1225
        assert result == Decimal("1225")

    def test_florida_hurricane_surcharge(self):
        """Florida gets 1.4x state multiplier."""
        result = estimate_annual_insurance(
            property_value=Decimal("300000"),
            sqft=1800,
            year_built=2000,
            state="FL",
            property_type="SFR",
        )
        # 300000 * 0.0035 * 1.4 = $1470
        assert result == Decimal("1470")

    def test_california_fire_surcharge(self):
        """California gets 1.3x state multiplier."""
        result = estimate_annual_insurance(
            property_value=Decimal("500000"),
            sqft=2000,
            year_built=2015,
            state="CA",
            property_type="SFR",
        )
        # 500000 * 0.0035 * 1.3 = $2275
        assert result == Decimal("2275")

    def test_pre_1950_age_surcharge(self):
        """Pre-1950 properties get 20% age surcharge."""
        result = estimate_annual_insurance(
            property_value=Decimal("300000"),
            sqft=1200,
            year_built=1940,
            state="OH",
            property_type="SFR",
        )
        # 300000 * 0.0035 * 1.0 * 1.20 = $1260
        assert result == Decimal("1260")

    def test_pre_1970_age_surcharge(self):
        """Pre-1970 properties get 10% age surcharge."""
        result = estimate_annual_insurance(
            property_value=Decimal("300000"),
            sqft=1200,
            year_built=1965,
            state="OH",
            property_type="SFR",
        )
        # 300000 * 0.0035 * 1.0 * 1.10 = $1155
        assert result == Decimal("1155")

    def test_multi_family_surcharge(self):
        """Multi-family gets 15% property type surcharge."""
        result = estimate_annual_insurance(
            property_value=Decimal("400000"),
            sqft=3000,
            year_built=2000,
            state="OH",
            property_type="Multi-Family",
        )
        # 400000 * 0.0035 * 1.15 = $1610
        assert result == Decimal("1610")

    def test_condo_discount(self):
        """Condo gets 20% discount (HOA covers structure)."""
        result = estimate_annual_insurance(
            property_value=Decimal("300000"),
            sqft=1000,
            year_built=2010,
            state="OH",
            property_type="Condo",
        )
        # 300000 * 0.0035 * 0.80 = $840
        assert result == Decimal("840")

    def test_minimum_floor(self):
        """Very cheap property still gets minimum $800."""
        result = estimate_annual_insurance(
            property_value=Decimal("50000"),
            sqft=800,
            year_built=2000,
            state="OH",
            property_type="SFR",
        )
        # 50000 * 0.0035 = $175 → minimum $800
        assert result == Decimal("800")

    def test_combined_surcharges(self):
        """Florida + pre-1950 + multi-family — all surcharges stack."""
        result = estimate_annual_insurance(
            property_value=Decimal("400000"),
            sqft=2500,
            year_built=1945,
            state="FL",
            property_type="Multi-Family",
        )
        # 400000 * 0.0035 * 1.4 * 1.20 * 1.15 — Decimal arithmetic gives $2705
        assert result == Decimal("2705")

    def test_state_case_insensitive(self):
        """State code should be case-insensitive."""
        result = estimate_annual_insurance(
            property_value=Decimal("300000"),
            sqft=1500,
            year_built=2010,
            state="fl",
            property_type="SFR",
        )
        assert result == Decimal("1470")
