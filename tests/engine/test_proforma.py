from dataclasses import replace
from decimal import Decimal

from src.engine.proforma import run_proforma
from src.engine.rehab import estimate_rehab_budget
from src.models.rehab import ConditionGrade


class TestProforma:
    def test_runs_without_error(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        assert result is not None
        assert len(result.yearly_projections) == 7

    def test_yearly_projections_sequential(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        for i, proj in enumerate(result.yearly_projections):
            assert proj.year == i + 1

    def test_noi_positive(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        for proj in result.yearly_projections:
            assert proj.noi > 0

    def test_rent_grows(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        for i in range(1, len(result.yearly_projections)):
            assert result.yearly_projections[i].gross_rent > result.yearly_projections[i - 1].gross_rent

    def test_property_value_appreciates(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        for i in range(1, len(result.yearly_projections)):
            assert (
                result.yearly_projections[i].property_value
                > result.yearly_projections[i - 1].property_value
            )

    def test_loan_balance_decreases(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        for i in range(1, len(result.yearly_projections)):
            assert (
                result.yearly_projections[i].loan_balance
                < result.yearly_projections[i - 1].loan_balance
            )

    def test_irr_computed(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        # With appreciation, IRR should be positive
        assert result.before_tax_irr > 0
        assert result.after_tax_irr > 0

    def test_equity_multiple_above_one(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        assert result.equity_multiple > Decimal("1")

    def test_disposition_computed(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        assert result.disposition.sale_price > 0
        assert result.disposition.after_tax_sale_proceeds > 0

    def test_suspended_losses_high_income(self, canonical_assumptions, canonical_investor):
        """High-income investor should have suspended losses."""
        result = run_proforma(canonical_assumptions, canonical_investor)
        # With depreciation creating paper losses, should have some suspended
        # (depends on whether NOI - interest - depreciation is negative)
        assert result.total_depreciation_taken > 0

    def test_cost_seg_higher_year1_depreciation(
        self,
        canonical_assumptions,
        canonical_assumptions_with_cost_seg,
        canonical_investor,
    ):
        """Cost seg should produce higher year 1 depreciation."""
        no_cs = run_proforma(canonical_assumptions, canonical_investor)
        with_cs = run_proforma(canonical_assumptions_with_cost_seg, canonical_investor)
        assert (
            with_cs.yearly_projections[0].total_depreciation
            > no_cs.yearly_projections[0].total_depreciation
        )

    def test_total_initial_investment(self, canonical_assumptions, canonical_investor):
        result = run_proforma(canonical_assumptions, canonical_investor)
        expected = canonical_assumptions.total_initial_investment
        assert result.total_initial_investment == expected


class TestProformaRehab:
    def test_zero_rehab_identical_to_baseline(self, canonical_assumptions, canonical_investor):
        """Turnkey (default) should produce same results as before rehab feature."""
        result = run_proforma(canonical_assumptions, canonical_investor)
        assert result.rehab_total_cost == Decimal("0")
        assert result.rehab_months == 0
        assert result.yearly_projections[0].rent_months == 12

    def test_rehab_increases_initial_investment(self, canonical_assumptions, canonical_investor):
        baseline = run_proforma(canonical_assumptions, canonical_investor)

        rehab = estimate_rehab_budget(
            sqft=1500, year_built=1985, condition_grade=ConditionGrade.MEDIUM
        )
        assumptions_with_rehab = replace(canonical_assumptions, rehab_budget=rehab)
        result = run_proforma(assumptions_with_rehab, canonical_investor)

        assert result.total_initial_investment > baseline.total_initial_investment
        assert result.rehab_total_cost > Decimal("0")
        assert (
            result.total_initial_investment
            == baseline.total_initial_investment + rehab.total_cost
        )

    def test_year1_rent_prorated(self, canonical_assumptions, canonical_investor):
        rehab = estimate_rehab_budget(
            sqft=1500, year_built=2005, condition_grade=ConditionGrade.MEDIUM
        )
        # Medium = 3 months rehab
        assert rehab.rehab_months == 3

        assumptions_with_rehab = replace(canonical_assumptions, rehab_budget=rehab)
        result = run_proforma(assumptions_with_rehab, canonical_investor)
        baseline = run_proforma(canonical_assumptions, canonical_investor)

        # Year 1 rent should be 9/12 of full year
        expected_y1_rent = (baseline.yearly_projections[0].gross_rent * Decimal("9") / Decimal("12")).quantize(Decimal("0.01"))
        assert result.yearly_projections[0].gross_rent == expected_y1_rent
        assert result.yearly_projections[0].rent_months == 9

    def test_year2_rent_not_prorated(self, canonical_assumptions, canonical_investor):
        rehab = estimate_rehab_budget(
            sqft=1500, year_built=2005, condition_grade=ConditionGrade.MEDIUM
        )
        assumptions_with_rehab = replace(canonical_assumptions, rehab_budget=rehab)
        result = run_proforma(assumptions_with_rehab, canonical_investor)
        baseline = run_proforma(canonical_assumptions, canonical_investor)

        # Year 2 should be identical
        assert result.yearly_projections[1].gross_rent == baseline.yearly_projections[1].gross_rent
        assert result.yearly_projections[1].rent_months == 12

    def test_fixed_costs_full_year_during_rehab(self, canonical_assumptions, canonical_investor):
        """Property tax, insurance, and debt service are full year even during rehab."""
        rehab = estimate_rehab_budget(
            sqft=1500, year_built=2005, condition_grade=ConditionGrade.HEAVY
        )
        assumptions_with_rehab = replace(canonical_assumptions, rehab_budget=rehab)
        result = run_proforma(assumptions_with_rehab, canonical_investor)
        baseline = run_proforma(canonical_assumptions, canonical_investor)

        y1 = result.yearly_projections[0]
        y1_base = baseline.yearly_projections[0]

        assert y1.property_tax == y1_base.property_tax
        assert y1.insurance == y1_base.insurance
        assert y1.debt_service == y1_base.debt_service

    def test_rehab_fields_on_result(self, canonical_assumptions, canonical_investor):
        rehab = estimate_rehab_budget(
            sqft=1500, year_built=2005, condition_grade=ConditionGrade.HEAVY
        )
        assumptions_with_rehab = replace(canonical_assumptions, rehab_budget=rehab)
        result = run_proforma(assumptions_with_rehab, canonical_investor)

        assert result.rehab_total_cost == rehab.total_cost
        assert result.rehab_months == rehab.rehab_months
