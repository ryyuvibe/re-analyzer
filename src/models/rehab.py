"""Rehab cost budgeting data types."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class ConditionGrade(Enum):
    TURNKEY = "turnkey"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    FULL_GUT = "full_gut"


class RehabCategory(Enum):
    PAINT = "paint"
    FLOORING = "flooring"
    KITCHEN = "kitchen"
    BATHROOMS = "bathrooms"
    HVAC = "hvac"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    ROOF = "roof"
    WINDOWS = "windows"
    EXTERIOR = "exterior"
    CONTINGENCY = "contingency"


@dataclass(frozen=True)
class RehabLineItem:
    category: RehabCategory
    estimated_cost: Decimal
    override_cost: Optional[Decimal] = None

    @property
    def cost(self) -> Decimal:
        if self.override_cost is not None:
            return self.override_cost
        return self.estimated_cost


@dataclass(frozen=True)
class RehabBudget:
    condition_grade: ConditionGrade
    line_items: tuple[RehabLineItem, ...] = ()
    rehab_months: int = 0
    total_override: Optional[Decimal] = None

    @property
    def total_cost(self) -> Decimal:
        if self.total_override is not None:
            return self.total_override
        return sum((item.cost for item in self.line_items), Decimal("0"))
