"""Pydantic schemas for API request/response models."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Request schemas ----

class AnalyzeRequest(BaseModel):
    address: str = Field(..., description="Full US address string")
    investor_profile_id: UUID | None = Field(None, description="Saved investor profile ID")

    # Optional overrides (if no profile provided)
    filing_status: str | None = None
    agi: Decimal | None = None
    marginal_federal_rate: Decimal | None = None
    marginal_state_rate: Decimal | None = None
    state: str | None = None
    is_re_professional: bool = False

    # Purchase price override (address lookup mode)
    purchase_price_override: Decimal | None = None

    # Rehab
    condition_grade: str | None = None
    rehab_months: int | None = None
    rehab_line_item_overrides: dict[str, Decimal] | None = None
    rehab_total_override: Decimal | None = None


class RerunRequest(BaseModel):
    """Re-run analysis with adjusted assumptions (no re-fetch of property data)."""
    analysis_id: UUID

    # Adjustable assumptions
    purchase_price: Decimal | None = None
    ltv: Decimal | None = None
    interest_rate: Decimal | None = None
    loan_term_years: int | None = None
    monthly_rent: Decimal | None = None
    annual_rent_growth: Decimal | None = None
    vacancy_rate: Decimal | None = None
    annual_appreciation: Decimal | None = None
    hold_years: int | None = None
    management_pct: Decimal | None = None
    capex_reserve_pct: Decimal | None = None
    maintenance_pct: Decimal | None = None
    cost_seg_five_year: Decimal | None = None
    cost_seg_seven_year: Decimal | None = None
    cost_seg_fifteen_year: Decimal | None = None


class InvestorProfileCreate(BaseModel):
    name: str
    filing_status: str
    agi: Decimal
    marginal_federal_rate: Decimal
    marginal_state_rate: Decimal
    state: str
    other_passive_income: Decimal = Decimal("0")
    is_re_professional: bool = False


class ComparisonRequest(BaseModel):
    analysis_id: UUID
    sp500_annual_return: Decimal = Decimal("0.10")
    risk_free_rate: Decimal = Decimal("0.04")


# ---- Response schemas ----

class RehabLineItemResponse(BaseModel):
    category: str
    estimated_cost: Decimal
    override_cost: Decimal | None = None
    cost: Decimal


class YearlyProjectionResponse(BaseModel):
    year: int
    gross_rent: Decimal
    effective_gross_income: Decimal
    total_expenses: Decimal
    noi: Decimal
    debt_service: Decimal
    cash_flow_before_tax: Decimal
    cash_flow_after_tax: Decimal
    total_depreciation: Decimal
    taxable_income: Decimal
    suspended_loss: Decimal
    tax_benefit: Decimal
    property_value: Decimal
    equity: Decimal
    cap_rate: Decimal
    cash_on_cash: Decimal
    dscr: Decimal
    rent_months: int = 12


class DispositionResponse(BaseModel):
    sale_price: Decimal
    selling_costs: Decimal
    net_sale_proceeds: Decimal
    total_gain: Decimal
    depreciation_recapture: Decimal
    capital_gain: Decimal
    recapture_tax: Decimal
    capital_gains_tax: Decimal
    niit_on_gain: Decimal
    state_tax_on_gain: Decimal
    suspended_losses_released: Decimal
    tax_benefit_from_release: Decimal
    total_tax_on_sale: Decimal
    after_tax_sale_proceeds: Decimal


class PropertyResponse(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    bedrooms: int
    bathrooms: Decimal
    sqft: int
    year_built: int
    estimated_value: Decimal
    estimated_rent: Decimal
    annual_tax: Decimal


class DemographicsResponse(BaseModel):
    median_household_income: int | None = None
    median_home_value: int | None = None
    poverty_rate: Decimal | None = None
    population: int | None = None
    renter_pct: Decimal | None = None


class WalkScoreResponse(BaseModel):
    walk_score: int | None = None
    transit_score: int | None = None
    bike_score: int | None = None


class SchoolResponse(BaseModel):
    name: str
    rating: int
    level: str
    distance_miles: Decimal


class NeighborhoodReportResponse(BaseModel):
    grade: str
    grade_score: Decimal
    demographics: DemographicsResponse | None = None
    walk_score: WalkScoreResponse | None = None
    schools: list[SchoolResponse] = []
    avg_school_rating: Decimal | None = None
    ai_narrative: str | None = None


class AnalysisResponse(BaseModel):
    id: UUID | None = None
    property: PropertyResponse
    total_initial_investment: Decimal
    before_tax_irr: Decimal
    after_tax_irr: Decimal
    equity_multiple: Decimal
    average_cash_on_cash: Decimal
    total_profit: Decimal
    total_depreciation_taken: Decimal
    total_tax_benefit_operations: Decimal
    net_tax_impact: Decimal
    rehab_total_cost: Decimal = Decimal("0")
    rehab_months: int = 0
    condition_grade: str | None = None
    rehab_line_items: list[RehabLineItemResponse] = []
    yearly_projections: list[YearlyProjectionResponse]
    disposition: DispositionResponse
    estimated_insurance: Decimal | None = None
    neighborhood: NeighborhoodReportResponse | None = None


class ComparisonResponse(BaseModel):
    re_after_tax_irr: Decimal
    sp500_after_tax_irr: Decimal
    re_total_return: Decimal
    sp500_total_return: Decimal
    re_sharpe: Decimal
    sp500_sharpe: Decimal
    re_yearly_equity: list[Decimal]
    sp500_yearly_equity: list[Decimal]


class MacroResponse(BaseModel):
    treasury_10y: Decimal | None = None
    mortgage_30y: Decimal | None = None
    cpi: Decimal | None = None
    unemployment: Decimal | None = None


class InvestorProfileResponse(BaseModel):
    id: UUID
    name: str
    filing_status: str
    agi: Decimal
    marginal_federal_rate: Decimal
    marginal_state_rate: Decimal
    state: str
    is_re_professional: bool
