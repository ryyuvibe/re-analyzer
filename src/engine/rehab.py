"""Rehab cost estimator.

Pure function: property attributes in, RehabBudget out. No I/O.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from src.models.rehab import (
    ConditionGrade,
    RehabCategory,
    RehabLineItem,
    RehabBudget,
)

TWO_PLACES = Decimal("0.01")

# Per-sqft cost by condition grade and category.
# Values represent $/sqft for a post-2000 build (age multiplier applied separately).
COST_TABLE: dict[ConditionGrade, dict[RehabCategory, Decimal]] = {
    ConditionGrade.TURNKEY: {cat: Decimal("0") for cat in RehabCategory},
    ConditionGrade.LIGHT: {
        RehabCategory.PAINT: Decimal("2.00"),
        RehabCategory.FLOORING: Decimal("2.50"),
        RehabCategory.KITCHEN: Decimal("0"),
        RehabCategory.BATHROOMS: Decimal("0"),
        RehabCategory.HVAC: Decimal("0"),
        RehabCategory.ELECTRICAL: Decimal("0"),
        RehabCategory.PLUMBING: Decimal("0"),
        RehabCategory.ROOF: Decimal("0"),
        RehabCategory.WINDOWS: Decimal("0"),
        RehabCategory.EXTERIOR: Decimal("0.50"),
        RehabCategory.CONTINGENCY: Decimal("1.00"),
    },
    ConditionGrade.MEDIUM: {
        RehabCategory.PAINT: Decimal("2.50"),
        RehabCategory.FLOORING: Decimal("4.00"),
        RehabCategory.KITCHEN: Decimal("5.00"),
        RehabCategory.BATHROOMS: Decimal("3.50"),
        RehabCategory.HVAC: Decimal("1.50"),
        RehabCategory.ELECTRICAL: Decimal("0"),
        RehabCategory.PLUMBING: Decimal("0"),
        RehabCategory.ROOF: Decimal("0"),
        RehabCategory.WINDOWS: Decimal("1.00"),
        RehabCategory.EXTERIOR: Decimal("1.00"),
        RehabCategory.CONTINGENCY: Decimal("2.50"),
    },
    ConditionGrade.HEAVY: {
        RehabCategory.PAINT: Decimal("3.00"),
        RehabCategory.FLOORING: Decimal("5.00"),
        RehabCategory.KITCHEN: Decimal("8.00"),
        RehabCategory.BATHROOMS: Decimal("6.00"),
        RehabCategory.HVAC: Decimal("4.00"),
        RehabCategory.ELECTRICAL: Decimal("3.00"),
        RehabCategory.PLUMBING: Decimal("2.50"),
        RehabCategory.ROOF: Decimal("3.00"),
        RehabCategory.WINDOWS: Decimal("2.50"),
        RehabCategory.EXTERIOR: Decimal("2.00"),
        RehabCategory.CONTINGENCY: Decimal("4.00"),
    },
    ConditionGrade.FULL_GUT: {
        RehabCategory.PAINT: Decimal("3.50"),
        RehabCategory.FLOORING: Decimal("7.00"),
        RehabCategory.KITCHEN: Decimal("12.00"),
        RehabCategory.BATHROOMS: Decimal("9.00"),
        RehabCategory.HVAC: Decimal("6.00"),
        RehabCategory.ELECTRICAL: Decimal("5.00"),
        RehabCategory.PLUMBING: Decimal("4.00"),
        RehabCategory.ROOF: Decimal("5.00"),
        RehabCategory.WINDOWS: Decimal("4.00"),
        RehabCategory.EXTERIOR: Decimal("3.50"),
        RehabCategory.CONTINGENCY: Decimal("6.00"),
    },
}

DEFAULT_REHAB_MONTHS: dict[ConditionGrade, int] = {
    ConditionGrade.TURNKEY: 0,
    ConditionGrade.LIGHT: 1,
    ConditionGrade.MEDIUM: 3,
    ConditionGrade.HEAVY: 6,
    ConditionGrade.FULL_GUT: 9,
}


def _age_multiplier(year_built: int) -> Decimal:
    if year_built >= 2000:
        return Decimal("1.00")
    if year_built >= 1970:
        return Decimal("1.10")
    if year_built >= 1950:
        return Decimal("1.20")
    return Decimal("1.30")


def estimate_rehab_budget(
    sqft: int,
    year_built: int,
    condition_grade: ConditionGrade,
    rehab_months: Optional[int] = None,
    line_item_overrides: Optional[dict[str, Decimal]] = None,
    total_override: Optional[Decimal] = None,
) -> RehabBudget:
    """Estimate rehab budget from property attributes and condition grade.

    Args:
        sqft: Property square footage.
        year_built: Year the property was built (for age multiplier).
        condition_grade: Overall condition assessment.
        rehab_months: Override default rehab duration.
        line_item_overrides: Dict of category name → override cost.
        total_override: Override the total rehab cost (bypasses line items).

    Returns:
        RehabBudget with estimated (or overridden) line items.
    """
    age_mult = _age_multiplier(year_built)
    sqft_dec = Decimal(str(sqft))
    cost_row = COST_TABLE[condition_grade]

    overrides = line_item_overrides or {}

    line_items: list[RehabLineItem] = []
    for category in RehabCategory:
        per_sqft = cost_row[category]
        estimated = (per_sqft * sqft_dec * age_mult).quantize(TWO_PLACES, ROUND_HALF_UP)
        override = None
        if category.value in overrides:
            override = overrides[category.value]
        line_items.append(
            RehabLineItem(
                category=category,
                estimated_cost=estimated,
                override_cost=override,
            )
        )

    months = rehab_months if rehab_months is not None else DEFAULT_REHAB_MONTHS[condition_grade]

    return RehabBudget(
        condition_grade=condition_grade,
        line_items=tuple(line_items),
        rehab_months=months,
        total_override=total_override,
    )
