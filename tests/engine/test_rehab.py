"""Unit tests for rehab cost estimator."""

from decimal import Decimal

import pytest

from src.models.rehab import ConditionGrade, RehabCategory, RehabBudget
from src.engine.rehab import estimate_rehab_budget, DEFAULT_REHAB_MONTHS


class TestRehabEstimator:
    def test_turnkey_zero_cost(self):
        budget = estimate_rehab_budget(
            sqft=1500, year_built=2005, condition_grade=ConditionGrade.TURNKEY
        )
        assert budget.total_cost == Decimal("0")
        assert budget.rehab_months == 0

    def test_cost_scales_with_sqft(self):
        small = estimate_rehab_budget(
            sqft=1000, year_built=2005, condition_grade=ConditionGrade.MEDIUM
        )
        large = estimate_rehab_budget(
            sqft=2000, year_built=2005, condition_grade=ConditionGrade.MEDIUM
        )
        # Exactly 2x since same age multiplier
        assert large.total_cost == small.total_cost * 2

    def test_older_properties_cost_more(self):
        new_build = estimate_rehab_budget(
            sqft=1500, year_built=2005, condition_grade=ConditionGrade.MEDIUM
        )
        old_build = estimate_rehab_budget(
            sqft=1500, year_built=1940, condition_grade=ConditionGrade.MEDIUM
        )
        assert old_build.total_cost > new_build.total_cost

    def test_age_brackets(self):
        """Verify each age bracket produces the expected multiplier."""
        base = estimate_rehab_budget(
            sqft=1000, year_built=2005, condition_grade=ConditionGrade.LIGHT
        )
        mid = estimate_rehab_budget(
            sqft=1000, year_built=1980, condition_grade=ConditionGrade.LIGHT
        )
        older = estimate_rehab_budget(
            sqft=1000, year_built=1960, condition_grade=ConditionGrade.LIGHT
        )
        oldest = estimate_rehab_budget(
            sqft=1000, year_built=1940, condition_grade=ConditionGrade.LIGHT
        )
        assert mid.total_cost > base.total_cost
        assert older.total_cost > mid.total_cost
        assert oldest.total_cost > older.total_cost

    def test_grade_ordering(self):
        """Each grade should produce >= cost of the previous grade."""
        grades = list(ConditionGrade)
        costs = [
            estimate_rehab_budget(
                sqft=1500, year_built=2005, condition_grade=g
            ).total_cost
            for g in grades
        ]
        for i in range(1, len(costs)):
            assert costs[i] >= costs[i - 1], f"{grades[i]} < {grades[i-1]}"

    def test_deterministic(self):
        """Same inputs produce same output."""
        a = estimate_rehab_budget(
            sqft=1500, year_built=1985, condition_grade=ConditionGrade.HEAVY
        )
        b = estimate_rehab_budget(
            sqft=1500, year_built=1985, condition_grade=ConditionGrade.HEAVY
        )
        assert a.total_cost == b.total_cost
        assert a.rehab_months == b.rehab_months

    def test_line_item_override(self):
        budget = estimate_rehab_budget(
            sqft=1500,
            year_built=2005,
            condition_grade=ConditionGrade.MEDIUM,
            line_item_overrides={"kitchen": Decimal("25000")},
        )
        kitchen_item = next(
            item for item in budget.line_items if item.category == RehabCategory.KITCHEN
        )
        assert kitchen_item.cost == Decimal("25000")
        assert kitchen_item.override_cost == Decimal("25000")
        # Estimated cost should still be calculated
        assert kitchen_item.estimated_cost != Decimal("25000")

    def test_total_override(self):
        budget = estimate_rehab_budget(
            sqft=1500,
            year_built=2005,
            condition_grade=ConditionGrade.HEAVY,
            total_override=Decimal("50000"),
        )
        assert budget.total_cost == Decimal("50000")
        # Line items are still generated for reference
        assert len(budget.line_items) == len(RehabCategory)

    def test_default_rehab_months_by_grade(self):
        for grade, expected_months in DEFAULT_REHAB_MONTHS.items():
            budget = estimate_rehab_budget(
                sqft=1500, year_built=2005, condition_grade=grade
            )
            assert budget.rehab_months == expected_months, f"{grade}: {budget.rehab_months} != {expected_months}"

    def test_custom_rehab_months(self):
        budget = estimate_rehab_budget(
            sqft=1500,
            year_built=2005,
            condition_grade=ConditionGrade.MEDIUM,
            rehab_months=5,
        )
        assert budget.rehab_months == 5

    def test_all_categories_present(self):
        budget = estimate_rehab_budget(
            sqft=1500, year_built=2005, condition_grade=ConditionGrade.HEAVY
        )
        categories = {item.category for item in budget.line_items}
        assert categories == set(RehabCategory)

    def test_medium_grade_per_sqft_range(self):
        """Medium grade should be roughly $15-25/sqft for post-2000 build."""
        budget = estimate_rehab_budget(
            sqft=1000, year_built=2005, condition_grade=ConditionGrade.MEDIUM
        )
        per_sqft = budget.total_cost / Decimal("1000")
        assert Decimal("15") <= per_sqft <= Decimal("25")

    def test_full_gut_per_sqft_range(self):
        """Full gut should be roughly $60-80/sqft for post-2000 build."""
        budget = estimate_rehab_budget(
            sqft=1000, year_built=2005, condition_grade=ConditionGrade.FULL_GUT
        )
        per_sqft = budget.total_cost / Decimal("1000")
        assert Decimal("60") <= per_sqft <= Decimal("80")
