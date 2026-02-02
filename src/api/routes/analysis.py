"""Analysis routes — the primary API entry point."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import (
    AnalyzeRequest,
    RerunRequest,
    AnalysisResponse,
    YearlyProjectionResponse,
    DispositionResponse,
    PropertyResponse,
    RehabLineItemResponse,
    NeighborhoodReportResponse,
    DemographicsResponse,
    WalkScoreResponse,
    SchoolResponse,
)
from src.api.deps import get_resolver
from src.data.resolver import PropertyResolver
from src.models.assumptions import DealAssumptions, CostSegAllocation
from src.models.investor import InvestorTaxProfile, FilingStatus
from src.models.neighborhood import NeighborhoodReport
from src.models.rehab import ConditionGrade
from src.engine.proforma import run_proforma
from src.engine.rehab import estimate_rehab_budget
from src.engine.insurance import estimate_annual_insurance

router = APIRouter(prefix="/api/v1", tags=["analysis"])


def _build_investor(req: AnalyzeRequest) -> InvestorTaxProfile:
    """Build investor profile from request data."""
    return InvestorTaxProfile(
        filing_status=FilingStatus(req.filing_status or "married_filing_jointly"),
        agi=req.agi or Decimal("400000"),
        marginal_federal_rate=req.marginal_federal_rate or Decimal("0.37"),
        marginal_state_rate=req.marginal_state_rate or Decimal("0.133"),
        state=req.state or "CA",
        is_re_professional=req.is_re_professional,
    )


def _neighborhood_to_response(report: NeighborhoodReport) -> NeighborhoodReportResponse:
    """Convert engine NeighborhoodReport to API response."""
    demographics_resp = None
    if report.demographics:
        d = report.demographics
        demographics_resp = DemographicsResponse(
            median_household_income=d.median_household_income,
            median_home_value=d.median_home_value,
            poverty_rate=d.poverty_rate,
            population=d.population,
            renter_pct=d.renter_pct,
        )

    walk_resp = None
    if report.walk_score:
        w = report.walk_score
        walk_resp = WalkScoreResponse(
            walk_score=w.walk_score,
            transit_score=w.transit_score,
            bike_score=w.bike_score,
        )

    schools_resp = [
        SchoolResponse(
            name=s.name,
            rating=s.rating,
            level=s.level,
            distance_miles=s.distance_miles,
        )
        for s in report.schools
    ]

    return NeighborhoodReportResponse(
        grade=report.grade.value,
        grade_score=report.grade_score,
        demographics=demographics_resp,
        walk_score=walk_resp,
        schools=schools_resp,
        avg_school_rating=report.avg_school_rating,
        ai_narrative=report.ai_narrative,
    )


def _result_to_response(
    result, prop_detail, rehab_budget=None, estimated_insurance=None, neighborhood_report=None,
) -> AnalysisResponse:
    """Convert engine AnalysisResult to API response."""
    yearly = [
        YearlyProjectionResponse(
            year=p.year,
            gross_rent=p.gross_rent,
            effective_gross_income=p.effective_gross_income,
            total_expenses=p.total_expenses,
            noi=p.noi,
            debt_service=p.debt_service,
            cash_flow_before_tax=p.cash_flow_before_tax,
            cash_flow_after_tax=p.cash_flow_after_tax,
            total_depreciation=p.total_depreciation,
            taxable_income=p.taxable_income,
            suspended_loss=p.suspended_loss,
            tax_benefit=p.tax_benefit,
            property_value=p.property_value,
            equity=p.equity,
            cap_rate=p.cap_rate,
            cash_on_cash=p.cash_on_cash,
            dscr=p.dscr,
            rent_months=p.rent_months,
        )
        for p in result.yearly_projections
    ]

    d = result.disposition
    disposition = DispositionResponse(
        sale_price=d.sale_price,
        selling_costs=d.selling_costs,
        net_sale_proceeds=d.net_sale_proceeds,
        total_gain=d.total_gain,
        depreciation_recapture=d.depreciation_recapture,
        capital_gain=d.capital_gain,
        recapture_tax=d.recapture_tax,
        capital_gains_tax=d.capital_gains_tax,
        niit_on_gain=d.niit_on_gain,
        state_tax_on_gain=d.state_tax_on_gain,
        suspended_losses_released=d.suspended_losses_released,
        tax_benefit_from_release=d.tax_benefit_from_release,
        total_tax_on_sale=d.total_tax_on_sale,
        after_tax_sale_proceeds=d.after_tax_sale_proceeds,
    )

    addr = prop_detail.address
    prop_resp = PropertyResponse(
        street=addr.street,
        city=addr.city,
        state=addr.state,
        zip_code=addr.zip_code,
        bedrooms=prop_detail.bedrooms,
        bathrooms=prop_detail.bathrooms,
        sqft=prop_detail.sqft,
        year_built=prop_detail.year_built,
        estimated_value=prop_detail.estimated_value,
        estimated_rent=prop_detail.estimated_rent,
        annual_tax=prop_detail.annual_tax,
    )

    # Rehab details
    rehab_line_items = []
    condition_grade_str = None
    if rehab_budget is not None:
        condition_grade_str = rehab_budget.condition_grade.value
        rehab_line_items = [
            RehabLineItemResponse(
                category=item.category.value,
                estimated_cost=item.estimated_cost,
                override_cost=item.override_cost,
                cost=item.cost,
            )
            for item in rehab_budget.line_items
        ]

    neighborhood_resp = None
    if neighborhood_report is not None:
        neighborhood_resp = _neighborhood_to_response(neighborhood_report)

    return AnalysisResponse(
        property=prop_resp,
        total_initial_investment=result.total_initial_investment,
        before_tax_irr=result.before_tax_irr,
        after_tax_irr=result.after_tax_irr,
        equity_multiple=result.equity_multiple,
        average_cash_on_cash=result.average_cash_on_cash,
        total_profit=result.total_profit,
        total_depreciation_taken=result.total_depreciation_taken,
        total_tax_benefit_operations=result.total_tax_benefit_operations,
        net_tax_impact=result.net_tax_impact,
        rehab_total_cost=result.rehab_total_cost,
        rehab_months=result.rehab_months,
        condition_grade=condition_grade_str,
        rehab_line_items=rehab_line_items,
        yearly_projections=yearly,
        disposition=disposition,
        estimated_insurance=estimated_insurance,
        neighborhood=neighborhood_resp,
    )


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    req: AnalyzeRequest,
    resolver: PropertyResolver = Depends(get_resolver),
):
    """Primary endpoint: address string → full analysis.

    Orchestrates: resolve property → build assumptions → run proforma → return results.
    """
    # Resolve property data + neighborhood intelligence
    neighborhood_report = None
    try:
        prop, neighborhood_report = await resolver.resolve_with_neighborhood(req.address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build investor profile
    investor = _build_investor(req)

    # Determine purchase price: override > estimated value > last sale
    purchase_price = req.purchase_price_override or prop.estimated_value or prop.last_sale_price
    if not purchase_price:
        raise HTTPException(
            status_code=400,
            detail="Could not determine property value. Please provide purchase_price_override.",
        )

    # Estimate insurance
    insurance_estimate = estimate_annual_insurance(
        property_value=purchase_price,
        sqft=prop.sqft or 1500,
        year_built=prop.year_built or 2000,
        state=prop.address.state or "OH",
        property_type=prop.property_type,
    )

    # Build rehab budget if condition grade provided
    rehab_budget = None
    if req.condition_grade:
        grade = ConditionGrade(req.condition_grade)
        rehab_budget = estimate_rehab_budget(
            sqft=prop.sqft or 1500,
            year_built=prop.year_built or 2000,
            condition_grade=grade,
            rehab_months=req.rehab_months,
            line_item_overrides=req.rehab_line_item_overrides,
            total_override=req.rehab_total_override,
        )

    assumptions_kwargs = dict(
        purchase_price=purchase_price,
        monthly_rent=prop.estimated_rent or Decimal("0"),
        property_tax=prop.annual_tax or Decimal("0"),
        insurance=insurance_estimate,
    )
    if rehab_budget is not None:
        assumptions_kwargs["rehab_budget"] = rehab_budget

    assumptions = DealAssumptions(**assumptions_kwargs)

    # Run proforma
    result = run_proforma(assumptions, investor)
    return _result_to_response(
        result, prop,
        rehab_budget=rehab_budget,
        estimated_insurance=insurance_estimate,
        neighborhood_report=neighborhood_report,
    )


@router.post("/analyze/rerun", response_model=AnalysisResponse)
async def rerun_analysis(req: RerunRequest):
    """Re-run analysis with adjusted assumptions. No data re-fetch."""
    # In production, load the original analysis from DB and apply overrides.
    # For now, return 501.
    raise HTTPException(status_code=501, detail="Rerun not yet implemented — requires DB")
