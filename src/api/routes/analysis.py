"""Analysis routes — the primary API entry point."""

from dataclasses import replace
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
    AssumptionDetailResponse,
    AssumptionManifestResponse,
    RentEstimateResponse,
    RentTierResponse,
)
from src.api.deps import get_resolver
from src.data.resolver import PropertyResolver
from src.models.assumptions import DealAssumptions, CostSegAllocation
from src.models.investor import InvestorTaxProfile, FilingStatus
from src.models.neighborhood import NeighborhoodReport
from src.models.rent_estimate import RentEstimate
from src.models.smart_assumptions import UserOverrides, AssumptionManifest
from src.models.rehab import ConditionGrade
from src.engine.proforma import run_proforma
from src.engine.rehab import estimate_rehab_budget
from src.engine.assumptions_builder import build_smart_assumptions

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


def _build_overrides(req: AnalyzeRequest) -> UserOverrides:
    """Extract user overrides from request."""
    return UserOverrides(
        purchase_price=req.purchase_price_override,
        ltv=req.ltv,
        interest_rate=req.interest_rate,
        loan_term_years=req.loan_term_years,
        loan_type=req.loan_type,
        monthly_rent=req.monthly_rent,
        annual_rent_growth=req.annual_rent_growth,
        vacancy_rate=req.vacancy_rate,
        property_tax=req.property_tax,
        insurance=req.insurance,
        maintenance_pct=req.maintenance_pct,
        management_pct=req.management_pct,
        capex_reserve_pct=req.capex_reserve_pct,
        hoa=req.hoa,
        annual_appreciation=req.annual_appreciation,
        land_value_pct=req.land_value_pct,
        annual_expense_growth=req.annual_expense_growth,
        hold_years=req.hold_years,
        selling_costs_pct=req.selling_costs_pct,
        closing_cost_pct=req.closing_cost_pct,
    )


def _manifest_to_response(manifest: AssumptionManifest) -> AssumptionManifestResponse:
    """Convert engine AssumptionManifest to API response."""
    details = {}
    for key, d in manifest.details.items():
        details[key] = AssumptionDetailResponse(
            field_name=d.field_name,
            value=d.value,
            source=d.source.value,
            confidence=d.confidence.value,
            justification=d.justification,
            data_points=d.data_points,
        )
    return AssumptionManifestResponse(details=details)


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
        flood_zone=report.flood_zone,
        seismic_pga=report.seismic_pga,
        wildfire_risk=report.wildfire_risk,
        hurricane_zone=report.hurricane_zone,
        hail_frequency=report.hail_frequency,
        crime_rate=report.crime_rate,
        climate_zone=report.climate_zone,
        traffic_noise_score=report.traffic_noise_score,
    )


def _rent_estimate_to_response(rent_est: RentEstimate) -> RentEstimateResponse:
    """Convert engine RentEstimate to API response."""
    return RentEstimateResponse(
        estimated_rent=rent_est.estimated_rent,
        confidence=rent_est.confidence,
        confidence_score=rent_est.confidence_score,
        needs_review=rent_est.needs_review,
        tier_results=[
            RentTierResponse(
                tier=t.tier,
                estimate=t.estimate,
                confidence=t.confidence,
                reasoning=t.reasoning,
            )
            for t in rent_est.tier_results
        ],
        recommended_range=rent_est.recommended_range,
    )


def _result_to_response(
    result, prop_detail, rehab_budget=None, estimated_insurance=None,
    neighborhood_report=None, loan_type=None, rent_estimate=None, manifest=None,
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

    rent_est_resp = None
    if rent_estimate is not None:
        rent_est_resp = _rent_estimate_to_response(rent_estimate)

    manifest_resp = None
    if manifest is not None:
        manifest_resp = _manifest_to_response(manifest)

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
        loan_type=loan_type,
        rent_estimate=rent_est_resp,
        assumption_manifest=manifest_resp,
    )


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    req: AnalyzeRequest,
    resolver: PropertyResolver = Depends(get_resolver),
):
    """Primary endpoint: address string → full analysis.

    Orchestrates: resolve property → build smart assumptions → run proforma → return results.
    """
    # Resolve property data + neighborhood + macro
    neighborhood_report = None
    macro = None
    rent_estimate = None
    try:
        prop, neighborhood_report, macro, rent_estimate = await resolver.resolve_full(req.address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Apply property detail overrides (useful when RentCast is unavailable)
    if req.sqft and prop.sqft == 0:
        prop = replace(prop, sqft=req.sqft)
    if req.bedrooms is not None and prop.bedrooms == 0:
        prop = replace(prop, bedrooms=req.bedrooms)
    if req.bathrooms is not None and prop.bathrooms == Decimal("0"):
        prop = replace(prop, bathrooms=req.bathrooms)
    if req.year_built and prop.year_built == 0:
        prop = replace(prop, year_built=req.year_built)

    # Build investor profile
    investor = _build_investor(req)

    # Build overrides from request
    overrides = _build_overrides(req)

    # Build rehab budget if condition grade provided
    rehab_budget = None
    condition_grade = req.condition_grade or "turnkey"
    if condition_grade != "turnkey":
        grade = ConditionGrade(condition_grade)
        rehab_budget = estimate_rehab_budget(
            sqft=prop.sqft or 1500,
            year_built=prop.year_built or 2000,
            condition_grade=grade,
            rehab_months=req.rehab_months,
            line_item_overrides=req.rehab_line_item_overrides,
            total_override=req.rehab_total_override,
        )

    # Build smart assumptions with manifest
    try:
        assumptions, manifest = build_smart_assumptions(
            prop=prop,
            neighborhood=neighborhood_report,
            macro=macro,
            overrides=overrides,
            condition_grade=condition_grade,
            rehab_budget=rehab_budget,
            rent_estimate=rent_estimate,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Run proforma
    result = run_proforma(assumptions, investor)

    return _result_to_response(
        result, prop,
        rehab_budget=rehab_budget,
        estimated_insurance=assumptions.insurance,
        neighborhood_report=neighborhood_report,
        loan_type=assumptions.loan_type,
        rent_estimate=rent_estimate,
        manifest=manifest,
    )


@router.post("/analyze/rerun", response_model=AnalysisResponse)
async def rerun_analysis(req: RerunRequest):
    """Re-run analysis with adjusted assumptions. No data re-fetch."""
    # In production, load the original analysis from DB and apply overrides.
    # For now, return 501.
    raise HTTPException(status_code=501, detail="Rerun not yet implemented — requires DB")
