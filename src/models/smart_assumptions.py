"""Smart assumptions layer: estimated inputs with source tracking and override support."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class AssumptionSource(Enum):
    API_FETCHED = "api_fetched"
    ESTIMATED = "estimated"
    USER_OVERRIDE = "user_override"
    DEFAULT = "default"


class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class AssumptionDetail:
    field_name: str
    value: Decimal
    source: AssumptionSource
    confidence: Confidence
    justification: str
    data_points: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AssumptionManifest:
    details: dict[str, AssumptionDetail] = field(default_factory=dict)

    def get(self, field_name: str) -> AssumptionDetail | None:
        return self.details.get(field_name)


@dataclass(frozen=True)
class LoanOption:
    loan_type: str  # "conventional" or "dscr"
    interest_rate: Decimal
    ltv: Decimal
    loan_term_years: int
    points: Decimal
    rate_source: str
    min_dscr: Decimal | None = None
    prepayment_penalty: str | None = None


@dataclass(frozen=True)
class MacroContext:
    mortgage_rate_30y: Decimal | None = None
    treasury_10y: Decimal | None = None
    cpi_current: Decimal | None = None
    cpi_5yr_cagr: Decimal | None = None
    unemployment_rate: Decimal | None = None
    median_home_price_national: Decimal | None = None


@dataclass(frozen=True)
class UserOverrides:
    """Every field the user can override."""
    purchase_price: Decimal | None = None
    ltv: Decimal | None = None
    interest_rate: Decimal | None = None
    loan_term_years: int | None = None
    loan_type: str | None = None
    monthly_rent: Decimal | None = None
    annual_rent_growth: Decimal | None = None
    vacancy_rate: Decimal | None = None
    property_tax: Decimal | None = None
    insurance: Decimal | None = None
    maintenance_pct: Decimal | None = None
    management_pct: Decimal | None = None
    capex_reserve_pct: Decimal | None = None
    hoa: Decimal | None = None
    annual_appreciation: Decimal | None = None
    land_value_pct: Decimal | None = None
    annual_expense_growth: Decimal | None = None
    hold_years: int | None = None
    selling_costs_pct: Decimal | None = None
    closing_cost_pct: Decimal | None = None
