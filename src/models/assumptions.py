from dataclasses import dataclass, field
from decimal import Decimal

from src.models.rehab import RehabBudget, ConditionGrade


@dataclass(frozen=True)
class CostSegAllocation:
    """Percentage of depreciable basis allocated to each MACRS class."""
    five_year: Decimal = Decimal("0")     # Personal property (appliances, carpet, etc.)
    seven_year: Decimal = Decimal("0")    # Office furniture, etc.
    fifteen_year: Decimal = Decimal("0")  # Land improvements (parking, landscaping)
    # Remainder stays on 27.5-year residential

    @property
    def reclassified_total(self) -> Decimal:
        return self.five_year + self.seven_year + self.fifteen_year

    @property
    def residential_pct(self) -> Decimal:
        return Decimal("1") - self.reclassified_total


@dataclass(frozen=True)
class DealAssumptions:
    # Purchase
    purchase_price: Decimal
    closing_costs: Decimal = Decimal("0")  # Buyer closing costs (added to basis)
    land_value_pct: Decimal = Decimal("0.20")  # Land is not depreciable

    # Financing
    ltv: Decimal = Decimal("0.80")
    interest_rate: Decimal = Decimal("0.07")  # Annual
    loan_term_years: int = 30
    loan_points: Decimal = Decimal("0")  # Points paid at closing

    # Income
    monthly_rent: Decimal = Decimal("0")
    annual_rent_growth: Decimal = Decimal("0.03")
    vacancy_rate: Decimal = Decimal("0.05")
    other_income: Decimal = Decimal("0")  # Laundry, parking, etc.

    # Expenses
    property_tax: Decimal = Decimal("0")  # Annual
    insurance: Decimal = Decimal("0")  # Annual
    maintenance_pct: Decimal = Decimal("0.05")  # % of gross rent
    management_pct: Decimal = Decimal("0.08")  # % of gross rent
    capex_reserve_pct: Decimal = Decimal("0.05")  # % of gross rent
    hoa: Decimal = Decimal("0")  # Monthly

    # Appreciation & Hold
    annual_appreciation: Decimal = Decimal("0.03")
    hold_years: int = 7
    selling_costs_pct: Decimal = Decimal("0.06")  # Agent fees + closing

    # Depreciation
    cost_seg: CostSegAllocation = field(default_factory=CostSegAllocation)
    placed_in_service_year: int = 2025
    placed_in_service_month: int = 1  # For mid-month convention

    # Expense growth
    annual_expense_growth: Decimal = Decimal("0.02")

    # Rehab
    rehab_budget: RehabBudget = field(
        default_factory=lambda: RehabBudget(condition_grade=ConditionGrade.TURNKEY)
    )

    @property
    def loan_amount(self) -> Decimal:
        return self.purchase_price * self.ltv

    @property
    def down_payment(self) -> Decimal:
        return self.purchase_price - self.loan_amount

    @property
    def total_initial_investment(self) -> Decimal:
        return self.down_payment + self.closing_costs + self.loan_points + self.rehab_budget.total_cost

    @property
    def total_basis(self) -> Decimal:
        """Cost basis for depreciation = purchase price + closing costs."""
        return self.purchase_price + self.closing_costs

    @property
    def depreciable_basis(self) -> Decimal:
        """Depreciable basis = (total basis - land value) + rehab costs.

        Rehab is 100% depreciable (all building improvement, no land).
        """
        return self.total_basis * (Decimal("1") - self.land_value_pct) + self.rehab_budget.total_cost

    @property
    def land_value(self) -> Decimal:
        return self.total_basis * self.land_value_pct
