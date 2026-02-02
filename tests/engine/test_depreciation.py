from decimal import Decimal

from src.engine.depreciation import (
    residential_depreciation,
    macrs_depreciation,
    compute_yearly_depreciation,
    total_depreciation_taken,
)


class TestResidentialDepreciation:
    def test_year_1_january(self, canonical_assumptions):
        """Mid-month convention: placed in service Jan, year 1 = 3.485%."""
        basis = canonical_assumptions.depreciable_basis
        dep = residential_depreciation(basis, 1, 1)
        expected = basis * Decimal("0.03485")
        assert abs(dep - expected) < Decimal("1")

    def test_year_2_full_year(self, canonical_assumptions):
        """Year 2 onward is 3.636% regardless of month."""
        basis = canonical_assumptions.depreciable_basis
        dep = residential_depreciation(basis, 1, 2)
        expected = basis * Decimal("0.03636")
        assert abs(dep - expected) < Decimal("1")

    def test_year_30_zero(self, canonical_assumptions):
        """No depreciation after year 29."""
        basis = canonical_assumptions.depreciable_basis
        dep = residential_depreciation(basis, 1, 30)
        assert dep == Decimal("0")


class TestMACRSDepreciation:
    def test_5_year_class(self):
        """5-year MACRS, year 1 = 20%."""
        dep = macrs_depreciation(Decimal("100000"), "5", 1)
        assert dep == Decimal("20000.00")

    def test_5_year_full_schedule(self):
        """5-year MACRS should sum to 100% of basis."""
        basis = Decimal("100000")
        total = sum(macrs_depreciation(basis, "5", y) for y in range(1, 7))
        assert abs(total - basis) < Decimal("1")

    def test_7_year_year_1(self):
        dep = macrs_depreciation(Decimal("100000"), "7", 1)
        assert dep == Decimal("14290.00")

    def test_15_year_year_1(self):
        dep = macrs_depreciation(Decimal("100000"), "15", 1)
        assert dep == Decimal("5000.00")


class TestCostSegDepreciation:
    def test_no_cost_seg_residential_only(self, canonical_assumptions):
        """Without cost seg, all depreciation is 27.5-year."""
        dep = compute_yearly_depreciation(canonical_assumptions, 1)
        assert dep.five_year == Decimal("0")
        assert dep.seven_year == Decimal("0")
        assert dep.fifteen_year == Decimal("0")
        assert dep.residential > 0

    def test_cost_seg_accelerates(
        self, canonical_assumptions, canonical_assumptions_with_cost_seg
    ):
        """Cost seg should produce more depreciation in year 1."""
        no_cs = compute_yearly_depreciation(canonical_assumptions, 1)
        with_cs = compute_yearly_depreciation(canonical_assumptions_with_cost_seg, 1)
        assert with_cs.total > no_cs.total

    def test_bonus_depreciation_year_1(self, canonical_assumptions_with_cost_seg):
        """With 2025 placement, bonus should be 100% on cost seg components."""
        dep = compute_yearly_depreciation(canonical_assumptions_with_cost_seg, 1)
        assert dep.bonus > 0


class TestTotalDepreciation:
    def test_seven_year_total(self, canonical_assumptions):
        total = total_depreciation_taken(canonical_assumptions, 7)
        # Should be meaningful but less than depreciable basis
        assert total > 0
        assert total < canonical_assumptions.depreciable_basis
