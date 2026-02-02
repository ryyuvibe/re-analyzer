"""Depreciation computation: straight-line 27.5yr with mid-month convention,
MACRS accelerated schedules, cost segregation, and bonus depreciation.

Pure functions. Validates against IRS Pub 946.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from src.models.assumptions import DealAssumptions, CostSegAllocation
from src.config import settings

TWO_PLACES = Decimal("0.01")

_MACRS_TABLES: dict | None = None


def _load_macrs_tables() -> dict:
    global _MACRS_TABLES
    if _MACRS_TABLES is None:
        path = Path(__file__).parent.parent.parent / "data" / "macrs_tables.json"
        with open(path) as f:
            _MACRS_TABLES = json.load(f)
    return _MACRS_TABLES


@dataclass(frozen=True)
class DepreciationComponent:
    """Depreciation for one MACRS class in one year."""
    macrs_class: str  # "27.5", "5", "7", "15"
    basis: Decimal
    year: int
    amount: Decimal
    is_bonus: bool = False


@dataclass(frozen=True)
class YearlyDepreciation:
    year: int
    residential: Decimal  # 27.5-year component
    five_year: Decimal
    seven_year: Decimal
    fifteen_year: Decimal
    bonus: Decimal
    total: Decimal


def _bonus_rate(placed_in_service_year: int) -> Decimal:
    """Get bonus depreciation rate for the year placed in service."""
    rates = settings.bonus_depreciation_rate
    rate = rates.get(placed_in_service_year, Decimal("0"))
    return Decimal(str(rate))


def residential_depreciation(
    depreciable_basis: Decimal,
    placed_in_service_month: int,
    year: int,
) -> Decimal:
    """27.5-year straight-line depreciation with mid-month convention.

    Args:
        depreciable_basis: Basis allocated to 27.5-year class
        placed_in_service_month: Month (1-12) property was placed in service
        year: Depreciation year (1-indexed)
    """
    tables = _load_macrs_tables()
    table = tables["residential_27_5"]["table"]

    year_key = str(year)
    if year_key not in table:
        return Decimal("0")

    month_index = placed_in_service_month - 1
    pct = Decimal(str(table[year_key][month_index])) / 100
    return (depreciable_basis * pct).quantize(TWO_PLACES, ROUND_HALF_UP)


def macrs_depreciation(
    basis: Decimal,
    macrs_class: str,
    year: int,
) -> Decimal:
    """MACRS depreciation for 5, 7, or 15-year property (half-year convention).

    Args:
        basis: Depreciable basis for this component (after bonus)
        macrs_class: "5", "7", or "15"
        year: Depreciation year (1-indexed)
    """
    tables = _load_macrs_tables()
    key = f"macrs_{macrs_class}_year"
    percentages = tables[key]["percentages"]

    if year < 1 or year > len(percentages):
        return Decimal("0")

    pct = Decimal(str(percentages[year - 1])) / 100
    return (basis * pct).quantize(TWO_PLACES, ROUND_HALF_UP)


def compute_yearly_depreciation(
    assumptions: DealAssumptions,
    year: int,
) -> YearlyDepreciation:
    """Compute total depreciation for a given year across all MACRS classes.

    Handles cost segregation allocation and bonus depreciation.
    """
    dep_basis = assumptions.depreciable_basis
    cost_seg = assumptions.cost_seg
    bonus_rate = _bonus_rate(assumptions.placed_in_service_year)

    # State non-conformity: CA does not allow bonus depreciation
    # For now, compute federal only; state override handled in tax.py
    state_allows_bonus = assumptions.placed_in_service_year > 0  # placeholder

    # Allocate basis to MACRS classes
    five_year_basis = dep_basis * cost_seg.five_year
    seven_year_basis = dep_basis * cost_seg.seven_year
    fifteen_year_basis = dep_basis * cost_seg.fifteen_year
    residential_basis = dep_basis * cost_seg.residential_pct

    bonus = Decimal("0")
    five_yr_dep = Decimal("0")
    seven_yr_dep = Decimal("0")
    fifteen_yr_dep = Decimal("0")

    if year == 1 and bonus_rate > 0:
        # Bonus depreciation applies to 5, 7, and 15-year property in year 1
        bonus_five = (five_year_basis * bonus_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        bonus_seven = (seven_year_basis * bonus_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        bonus_fifteen = (fifteen_year_basis * bonus_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        bonus = bonus_five + bonus_seven + bonus_fifteen

        # Remaining basis gets regular MACRS
        remaining_five = five_year_basis - bonus_five
        remaining_seven = seven_year_basis - bonus_seven
        remaining_fifteen = fifteen_year_basis - bonus_fifteen

        five_yr_dep = macrs_depreciation(remaining_five, "5", year)
        seven_yr_dep = macrs_depreciation(remaining_seven, "7", year)
        fifteen_yr_dep = macrs_depreciation(remaining_fifteen, "15", year)
    else:
        # After year 1, no bonus; regular MACRS on post-bonus basis
        if bonus_rate > 0:
            remaining_five = five_year_basis * (1 - bonus_rate)
            remaining_seven = seven_year_basis * (1 - bonus_rate)
            remaining_fifteen = fifteen_year_basis * (1 - bonus_rate)
        else:
            remaining_five = five_year_basis
            remaining_seven = seven_year_basis
            remaining_fifteen = fifteen_year_basis

        five_yr_dep = macrs_depreciation(remaining_five, "5", year)
        seven_yr_dep = macrs_depreciation(remaining_seven, "7", year)
        fifteen_yr_dep = macrs_depreciation(remaining_fifteen, "15", year)

    res_dep = residential_depreciation(
        residential_basis, assumptions.placed_in_service_month, year
    )

    total = res_dep + five_yr_dep + seven_yr_dep + fifteen_yr_dep + bonus

    return YearlyDepreciation(
        year=year,
        residential=res_dep,
        five_year=five_yr_dep,
        seven_year=seven_yr_dep,
        fifteen_year=fifteen_yr_dep,
        bonus=bonus,
        total=total,
    )


def total_depreciation_taken(
    assumptions: DealAssumptions,
    through_year: int,
) -> Decimal:
    """Sum of all depreciation taken from year 1 through given year."""
    total = Decimal("0")
    for y in range(1, through_year + 1):
        total += compute_yearly_depreciation(assumptions, y).total
    return total
