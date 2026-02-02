"""Canonical test fixtures used across all engine tests.

Fixture: $500K rental property, 80% LTV, 7% rate, 30yr fixed.
Investor: MFJ, $400K AGI, 37% federal, 13.3% CA state.
"""

import pytest
from decimal import Decimal

from src.models.assumptions import DealAssumptions, CostSegAllocation
from src.models.investor import InvestorTaxProfile, FilingStatus


@pytest.fixture
def canonical_assumptions() -> DealAssumptions:
    """$500K property with standard assumptions."""
    return DealAssumptions(
        purchase_price=Decimal("500000"),
        closing_costs=Decimal("5000"),
        land_value_pct=Decimal("0.20"),
        ltv=Decimal("0.80"),
        interest_rate=Decimal("0.07"),
        loan_term_years=30,
        monthly_rent=Decimal("2800"),
        annual_rent_growth=Decimal("0.03"),
        vacancy_rate=Decimal("0.05"),
        property_tax=Decimal("6000"),
        insurance=Decimal("1500"),
        maintenance_pct=Decimal("0.05"),
        management_pct=Decimal("0.08"),
        capex_reserve_pct=Decimal("0.05"),
        annual_appreciation=Decimal("0.03"),
        hold_years=7,
        selling_costs_pct=Decimal("0.06"),
        placed_in_service_year=2025,
        placed_in_service_month=1,
    )


@pytest.fixture
def canonical_assumptions_with_cost_seg() -> DealAssumptions:
    """$500K property with 20% reclassified to 5-year via cost seg."""
    return DealAssumptions(
        purchase_price=Decimal("500000"),
        closing_costs=Decimal("5000"),
        land_value_pct=Decimal("0.20"),
        ltv=Decimal("0.80"),
        interest_rate=Decimal("0.07"),
        loan_term_years=30,
        monthly_rent=Decimal("2800"),
        annual_rent_growth=Decimal("0.03"),
        vacancy_rate=Decimal("0.05"),
        property_tax=Decimal("6000"),
        insurance=Decimal("1500"),
        maintenance_pct=Decimal("0.05"),
        management_pct=Decimal("0.08"),
        capex_reserve_pct=Decimal("0.05"),
        annual_appreciation=Decimal("0.03"),
        hold_years=7,
        selling_costs_pct=Decimal("0.06"),
        cost_seg=CostSegAllocation(
            five_year=Decimal("0.20"),
            seven_year=Decimal("0"),
            fifteen_year=Decimal("0"),
        ),
        placed_in_service_year=2025,
        placed_in_service_month=1,
    )


@pytest.fixture
def canonical_investor() -> InvestorTaxProfile:
    """High-income W-2 earner in California."""
    return InvestorTaxProfile(
        filing_status=FilingStatus.MFJ,
        agi=Decimal("400000"),
        marginal_federal_rate=Decimal("0.37"),
        marginal_state_rate=Decimal("0.133"),
        state="CA",
        other_passive_income=Decimal("0"),
        is_re_professional=False,
    )


@pytest.fixture
def low_income_investor() -> InvestorTaxProfile:
    """Investor qualifying for $25K rental loss exception."""
    return InvestorTaxProfile(
        filing_status=FilingStatus.MFJ,
        agi=Decimal("90000"),
        marginal_federal_rate=Decimal("0.22"),
        marginal_state_rate=Decimal("0.06"),
        state="TX",
        other_passive_income=Decimal("0"),
        is_re_professional=False,
    )


@pytest.fixture
def re_professional_investor() -> InvestorTaxProfile:
    """Real estate professional (IRC 469(c)(7))."""
    return InvestorTaxProfile(
        filing_status=FilingStatus.MFJ,
        agi=Decimal("400000"),
        marginal_federal_rate=Decimal("0.37"),
        marginal_state_rate=Decimal("0.133"),
        state="CA",
        other_passive_income=Decimal("0"),
        is_re_professional=True,
    )
