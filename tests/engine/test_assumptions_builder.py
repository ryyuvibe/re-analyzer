"""Tests for the smart assumption builder."""

from decimal import Decimal

import pytest

from src.engine.assumptions_builder import build_smart_assumptions
from src.models.property import PropertyDetail, Address
from src.models.neighborhood import (
    NeighborhoodReport, NeighborhoodGrade, NeighborhoodDemographics,
    WalkScoreResult,
)
from src.models.smart_assumptions import (
    MacroContext, UserOverrides, AssumptionSource, Confidence,
)


@pytest.fixture
def sample_property():
    return PropertyDetail(
        address=Address(
            street="123 Main St", city="Columbus", state="OH", zip_code="43215",
        ),
        bedrooms=3,
        bathrooms=Decimal("2"),
        sqft=1500,
        year_built=1975,
        property_type="SFR",
        estimated_value=Decimal("250000"),
        estimated_rent=Decimal("1800"),
        annual_tax=Decimal("3000"),
    )


@pytest.fixture
def sample_neighborhood():
    return NeighborhoodReport(
        grade=NeighborhoodGrade.B,
        grade_score=Decimal("70"),
        demographics=NeighborhoodDemographics(
            median_household_income=65000,
            poverty_rate=Decimal("0.08"),
            renter_pct=Decimal("0.45"),
        ),
        walk_score=WalkScoreResult(walk_score=55),
    )


@pytest.fixture
def sample_macro():
    return MacroContext(
        mortgage_rate_30y=Decimal("0.0685"),
        cpi_5yr_cagr=Decimal("0.035"),
    )


class TestSmartAssumptionBuilder:
    def test_basic_build(self, sample_property, sample_neighborhood, sample_macro):
        """Builder produces valid DealAssumptions and manifest."""
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property,
            neighborhood=sample_neighborhood,
            macro=sample_macro,
        )
        assert assumptions.purchase_price == Decimal("250000")
        assert assumptions.monthly_rent == Decimal("1800")
        assert assumptions.property_tax == Decimal("3000")
        assert assumptions.loan_type == "conventional"
        assert assumptions.hold_years == 7
        assert len(manifest.details) > 10

    def test_purchase_price_from_avm(self, sample_property, sample_macro):
        """Purchase price should come from estimated_value."""
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property, macro=sample_macro,
        )
        assert assumptions.purchase_price == Decimal("250000")
        d = manifest.details["purchase_price"]
        assert d.source == AssumptionSource.API_FETCHED

    def test_purchase_price_override(self, sample_property, sample_macro):
        """User override should take precedence."""
        overrides = UserOverrides(purchase_price=Decimal("200000"))
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property, macro=sample_macro, overrides=overrides,
        )
        assert assumptions.purchase_price == Decimal("200000")
        d = manifest.details["purchase_price"]
        assert d.source == AssumptionSource.USER_OVERRIDE

    def test_no_price_raises(self):
        """Should raise if no price available and no override."""
        prop = PropertyDetail(
            address=Address(street="X", city="X", state="OH", zip_code="43215"),
            bedrooms=3, bathrooms=Decimal("1"), sqft=1000, year_built=2000,
        )
        with pytest.raises(ValueError, match="Purchase price required"):
            build_smart_assumptions(prop=prop)

    def test_interest_rate_from_macro(self, sample_property, sample_macro):
        """Interest rate should be derived from FRED mortgage rate."""
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property, macro=sample_macro,
        )
        # Should be mortgage_rate + investor premium
        assert assumptions.interest_rate > Decimal("0.07")
        d = manifest.details["interest_rate"]
        assert "FRED" in d.justification

    def test_dscr_loan_type(self, sample_property, sample_macro):
        """DSCR loan type should produce higher rate."""
        overrides = UserOverrides(loan_type="dscr")
        assumptions, _ = build_smart_assumptions(
            prop=sample_property, macro=sample_macro, overrides=overrides,
        )
        assert assumptions.loan_type == "dscr"
        assert assumptions.interest_rate > Decimal("0.08")

    def test_vacancy_from_renter_demand(self, sample_property, sample_neighborhood, sample_macro):
        """Vacancy should adjust based on renter %."""
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property, neighborhood=sample_neighborhood, macro=sample_macro,
        )
        # 45% renter → moderate demand → 5%
        assert assumptions.vacancy_rate == Decimal("0.05")
        d = manifest.details["vacancy_rate"]
        assert "renter" in d.justification.lower()

    def test_closing_costs_state_based(self, sample_property, sample_macro):
        """Closing costs should use state-level table."""
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property, macro=sample_macro,
        )
        assert assumptions.closing_costs > 0
        d = manifest.details["closing_costs"]
        assert "OH" in d.justification

    def test_all_overrides(self, sample_property, sample_macro):
        """All override fields should take effect."""
        overrides = UserOverrides(
            purchase_price=Decimal("300000"),
            ltv=Decimal("0.75"),
            interest_rate=Decimal("0.065"),
            monthly_rent=Decimal("2000"),
            vacancy_rate=Decimal("0.03"),
            annual_appreciation=Decimal("0.04"),
            hold_years=10,
        )
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property, macro=sample_macro, overrides=overrides,
        )
        assert assumptions.purchase_price == Decimal("300000")
        assert assumptions.ltv == Decimal("0.75")
        assert assumptions.interest_rate == Decimal("0.065")
        assert assumptions.monthly_rent == Decimal("2000")
        assert assumptions.vacancy_rate == Decimal("0.03")
        assert assumptions.annual_appreciation == Decimal("0.04")
        assert assumptions.hold_years == 10

    def test_manifest_all_fields_have_justification(self, sample_property, sample_macro):
        """Every manifest detail should have a non-empty justification."""
        _, manifest = build_smart_assumptions(
            prop=sample_property, macro=sample_macro,
        )
        for key, detail in manifest.details.items():
            assert detail.justification, f"Missing justification for {key}"
            assert detail.source is not None
            assert detail.confidence is not None

    def test_insurance_uses_composite_model(self, sample_property, sample_neighborhood, sample_macro):
        """Insurance should use the composite model when neighborhood data is available."""
        assumptions, manifest = build_smart_assumptions(
            prop=sample_property, neighborhood=sample_neighborhood, macro=sample_macro,
        )
        assert assumptions.insurance > 0
        d = manifest.details["insurance"]
        assert "replacement cost" in d.justification.lower() or "user override" in d.justification.lower()

    def test_maintenance_varies_by_age(self, sample_property, sample_macro):
        """Maintenance % should reflect property age."""
        # 1975 property → ~5-7% range
        assumptions, _ = build_smart_assumptions(
            prop=sample_property, macro=sample_macro,
        )
        assert Decimal("0.03") <= assumptions.maintenance_pct <= Decimal("0.10")

    def test_management_fee_multifamily(self, sample_macro):
        """Multi-family should get 6% management fee."""
        prop = PropertyDetail(
            address=Address(street="X", city="X", state="OH", zip_code="43215"),
            bedrooms=8, bathrooms=Decimal("4"), sqft=4000, year_built=2000,
            property_type="Multi-Family",
            estimated_value=Decimal("500000"), estimated_rent=Decimal("4000"),
        )
        assumptions, _ = build_smart_assumptions(prop=prop, macro=sample_macro)
        assert assumptions.management_pct == Decimal("0.06")
