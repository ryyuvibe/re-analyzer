from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class YearlyProjection:
    year: int

    # Income
    gross_rent: Decimal = Decimal("0")
    vacancy_loss: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")
    effective_gross_income: Decimal = Decimal("0")

    # Expenses
    property_tax: Decimal = Decimal("0")
    insurance: Decimal = Decimal("0")
    maintenance: Decimal = Decimal("0")
    management: Decimal = Decimal("0")
    capex_reserve: Decimal = Decimal("0")
    hoa: Decimal = Decimal("0")
    total_expenses: Decimal = Decimal("0")

    # Operations
    noi: Decimal = Decimal("0")
    debt_service: Decimal = Decimal("0")
    cash_flow_before_tax: Decimal = Decimal("0")

    # Debt breakdown
    principal_paid: Decimal = Decimal("0")
    interest_paid: Decimal = Decimal("0")
    loan_balance: Decimal = Decimal("0")

    # Depreciation
    depreciation_27_5: Decimal = Decimal("0")
    depreciation_cost_seg: Decimal = Decimal("0")
    total_depreciation: Decimal = Decimal("0")

    # Tax
    taxable_income: Decimal = Decimal("0")
    passive_loss: Decimal = Decimal("0")  # Negative = loss
    suspended_loss: Decimal = Decimal("0")  # Cumulative suspended
    tax_benefit: Decimal = Decimal("0")  # Positive = tax saved
    cash_flow_after_tax: Decimal = Decimal("0")

    # Equity
    property_value: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")  # Value - loan balance

    # Metrics
    cap_rate: Decimal = Decimal("0")
    cash_on_cash: Decimal = Decimal("0")
    dscr: Decimal = Decimal("0")

    # Rehab
    rent_months: int = 12


@dataclass
class DispositionResult:
    sale_price: Decimal = Decimal("0")
    selling_costs: Decimal = Decimal("0")
    net_sale_proceeds: Decimal = Decimal("0")
    loan_payoff: Decimal = Decimal("0")
    gross_equity_proceeds: Decimal = Decimal("0")

    # Gain calculation
    adjusted_basis: Decimal = Decimal("0")
    total_gain: Decimal = Decimal("0")
    depreciation_recapture: Decimal = Decimal("0")  # IRC 1250, taxed at 25%
    capital_gain: Decimal = Decimal("0")  # IRC 1231, LTCG rate

    # Tax on sale
    recapture_tax: Decimal = Decimal("0")
    capital_gains_tax: Decimal = Decimal("0")
    niit_on_gain: Decimal = Decimal("0")
    state_tax_on_gain: Decimal = Decimal("0")

    # IRC 469(g)(1)(A) suspended loss release
    suspended_losses_released: Decimal = Decimal("0")
    tax_benefit_from_release: Decimal = Decimal("0")

    total_tax_on_sale: Decimal = Decimal("0")
    after_tax_sale_proceeds: Decimal = Decimal("0")


@dataclass
class AnalysisResult:
    yearly_projections: list[YearlyProjection] = field(default_factory=list)
    disposition: DispositionResult = field(default_factory=DispositionResult)

    # Summary metrics
    total_initial_investment: Decimal = Decimal("0")
    rehab_total_cost: Decimal = Decimal("0")
    rehab_months: int = 0
    before_tax_irr: Decimal = Decimal("0")
    after_tax_irr: Decimal = Decimal("0")
    equity_multiple: Decimal = Decimal("0")
    average_cash_on_cash: Decimal = Decimal("0")
    total_profit: Decimal = Decimal("0")

    # Tax alpha
    total_depreciation_taken: Decimal = Decimal("0")
    total_tax_benefit_operations: Decimal = Decimal("0")
    total_suspended_losses: Decimal = Decimal("0")
    net_tax_impact: Decimal = Decimal("0")  # Operations benefit - sale tax + release benefit


@dataclass
class EquityComparison:
    """Side-by-side comparison of RE investment vs S&P 500."""

    re_initial_equity: Decimal = Decimal("0")
    sp500_initial_equity: Decimal = Decimal("0")

    re_yearly_equity: list[Decimal] = field(default_factory=list)
    sp500_yearly_equity: list[Decimal] = field(default_factory=list)

    re_after_tax_irr: Decimal = Decimal("0")
    sp500_after_tax_irr: Decimal = Decimal("0")

    re_total_return: Decimal = Decimal("0")
    sp500_total_return: Decimal = Decimal("0")

    re_volatility: Decimal = Decimal("0")
    sp500_volatility: Decimal = Decimal("0")

    re_sharpe: Decimal = Decimal("0")
    sp500_sharpe: Decimal = Decimal("0")
