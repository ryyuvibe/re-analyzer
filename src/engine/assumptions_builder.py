"""Smart Assumption Builder: estimates every deal input from data with override support.

Sits between data resolution and the pure engine:
    PropertyDetail + NeighborhoodReport + MacroContext + UserOverrides
    → (DealAssumptions, AssumptionManifest)
"""

from decimal import Decimal

from src.models.assumptions import DealAssumptions, CostSegAllocation
from src.models.property import PropertyDetail
from src.models.neighborhood import NeighborhoodReport
from src.models.rehab import RehabBudget, ConditionGrade
from src.models.smart_assumptions import (
    AssumptionDetail,
    AssumptionManifest,
    AssumptionSource,
    Confidence,
    MacroContext,
    UserOverrides,
)
from src.engine.loan_products import conventional_loan, dscr_loan
from src.engine.insurance import estimate_insurance_composite
from src.engine.appreciation import estimate_appreciation
from src.engine.maintenance import estimate_maintenance_pct
from src.data.closing_costs import estimate_closing_costs
from src.data.climate import get_climate_zone
from src.data.noaa_hazards import get_hurricane_zone, get_hail_frequency
from src.data.fbi_crime import get_crime_rate
from src.models.rent_estimate import RentEstimate


def _detail(
    field: str,
    value: Decimal,
    source: AssumptionSource,
    confidence: Confidence,
    justification: str,
    data_points: dict | None = None,
) -> AssumptionDetail:
    return AssumptionDetail(
        field_name=field,
        value=value,
        source=source,
        confidence=confidence,
        justification=justification,
        data_points=data_points or {},
    )


def _override_or(
    field: str,
    override_value,
    estimate_value: Decimal,
    estimate_source: AssumptionSource,
    estimate_confidence: Confidence,
    estimate_justification: str,
    data_points: dict | None = None,
) -> tuple[Decimal, AssumptionDetail]:
    """Return override if set, otherwise the estimate."""
    if override_value is not None:
        val = Decimal(str(override_value))
        return val, _detail(
            field, val, AssumptionSource.USER_OVERRIDE, Confidence.HIGH,
            f"User override: {val}",
        )
    return estimate_value, _detail(
        field, estimate_value, estimate_source, estimate_confidence,
        estimate_justification, data_points,
    )


def build_smart_assumptions(
    prop: PropertyDetail,
    neighborhood: NeighborhoodReport | None = None,
    macro: MacroContext | None = None,
    overrides: UserOverrides | None = None,
    condition_grade: str = "turnkey",
    rehab_budget: RehabBudget | None = None,
    rent_estimate: RentEstimate | None = None,
) -> tuple[DealAssumptions, AssumptionManifest]:
    """Build DealAssumptions from property data + overrides, with full manifest.

    Every field is: check override → estimate from data → fallback to default.
    Returns (DealAssumptions, AssumptionManifest).
    """
    ov = overrides or UserOverrides()
    macro = macro or MacroContext()
    details: dict[str, AssumptionDetail] = {}
    state = prop.address.state or "OH"

    # ------------------------------------------------------------------
    # Purchase Price
    # ------------------------------------------------------------------
    est_price = prop.estimated_value or prop.last_sale_price
    if est_price and est_price > 0:
        price_source = AssumptionSource.API_FETCHED
        price_conf = Confidence.HIGH
        price_just = f"RentCast AVM: ${float(est_price):,.0f}"
    else:
        est_price = Decimal("0")
        price_source = AssumptionSource.DEFAULT
        price_conf = Confidence.LOW
        price_just = "No data available — user must provide"

    purchase_price, d = _override_or(
        "purchase_price", ov.purchase_price,
        est_price, price_source, price_conf, price_just,
    )
    details["purchase_price"] = d

    if purchase_price <= 0:
        raise ValueError("Purchase price required: no AVM data and no override provided.")

    # ------------------------------------------------------------------
    # Loan type & terms
    # ------------------------------------------------------------------
    loan_type = ov.loan_type or "conventional"

    # Need a rough DSCR estimate for DSCR loans
    rough_rent = ov.monthly_rent or prop.estimated_rent or Decimal("0")
    rough_annual_rent = rough_rent * 12
    rough_expenses_pct = Decimal("0.40")  # rough estimate
    rough_noi = rough_annual_rent * (1 - rough_expenses_pct)

    if loan_type == "dscr":
        loan = dscr_loan(macro, estimated_dscr=Decimal("1.2"))
    else:
        loan = conventional_loan(macro)

    interest_rate, d = _override_or(
        "interest_rate", ov.interest_rate,
        loan.interest_rate, AssumptionSource.ESTIMATED, Confidence.MEDIUM,
        loan.rate_source,
    )
    details["interest_rate"] = d

    ltv, d = _override_or(
        "ltv", ov.ltv,
        loan.ltv, AssumptionSource.ESTIMATED, Confidence.HIGH,
        f"{loan.loan_type.title()} default: {float(loan.ltv)*100:.0f}% LTV",
    )
    details["ltv"] = d

    loan_term, d_term = _override_or(
        "loan_term_years", ov.loan_term_years,
        Decimal(str(loan.loan_term_years)), AssumptionSource.DEFAULT, Confidence.HIGH,
        "Standard 30-year fixed",
    )
    details["loan_term_years"] = d_term

    details["loan_type"] = _detail(
        "loan_type", Decimal("0"),  # placeholder
        AssumptionSource.USER_OVERRIDE if ov.loan_type else AssumptionSource.DEFAULT,
        Confidence.HIGH,
        f"Loan type: {loan_type}",
    )

    # ------------------------------------------------------------------
    # Monthly Rent
    # ------------------------------------------------------------------
    est_rent = prop.estimated_rent or Decimal("0")
    if rent_estimate and rent_estimate.estimated_rent > 0:
        est_rent = Decimal(str(rent_estimate.estimated_rent))
        rent_source = AssumptionSource.API_FETCHED
        conf_map = {"high": Confidence.HIGH, "medium": Confidence.MEDIUM, "low": Confidence.LOW}
        rent_conf = conf_map.get(rent_estimate.confidence, Confidence.MEDIUM)
        tiers_used = ", ".join(
            t.tier.upper() for t in rent_estimate.tier_results if t.estimate
        )
        rent_just = f"Tiered estimate ${float(est_rent):,.0f}/mo ({tiers_used}, {rent_estimate.confidence} confidence)"
    elif est_rent > 0:
        rent_source = AssumptionSource.API_FETCHED
        rent_conf = Confidence.HIGH
        rent_just = f"RentCast rent AVM: ${float(est_rent):,.0f}/mo"
    else:
        rent_source = AssumptionSource.DEFAULT
        rent_conf = Confidence.LOW
        rent_just = "No rent data — user must provide"

    monthly_rent, d = _override_or(
        "monthly_rent", ov.monthly_rent,
        est_rent, rent_source, rent_conf, rent_just,
    )
    details["monthly_rent"] = d

    # ------------------------------------------------------------------
    # Rent Growth
    # ------------------------------------------------------------------
    cpi_cagr = macro.cpi_5yr_cagr or Decimal("0.03")
    grade_premium = Decimal("0")
    if neighborhood and neighborhood.grade:
        grade_premiums = {"A": "0.005", "B": "0.003", "C": "0", "D": "-0.005", "F": "-0.01"}
        grade_premium = Decimal(grade_premiums.get(neighborhood.grade.value, "0"))

    est_rent_growth = (
        cpi_cagr * Decimal("0.50")
        + grade_premium
        + cpi_cagr * Decimal("0.20")
    )
    est_rent_growth = max(Decimal("0.01"), min(Decimal("0.06"), est_rent_growth))
    est_rent_growth = est_rent_growth.quantize(Decimal("0.001"))

    annual_rent_growth, d = _override_or(
        "annual_rent_growth", ov.annual_rent_growth,
        est_rent_growth, AssumptionSource.ESTIMATED, Confidence.MEDIUM,
        f"50% CPI CAGR ({float(cpi_cagr)*100:.1f}%) + neighborhood grade premium + 20% local trend",
    )
    details["annual_rent_growth"] = d

    # ------------------------------------------------------------------
    # Vacancy Rate
    # ------------------------------------------------------------------
    est_vacancy = Decimal("0.05")
    vacancy_just = "Default 5% vacancy"
    vacancy_conf = Confidence.LOW
    if neighborhood and neighborhood.demographics and neighborhood.demographics.renter_pct is not None:
        rp = float(neighborhood.demographics.renter_pct)
        if rp > 0.60:
            est_vacancy = Decimal("0.04")  # High demand
            vacancy_just = f"High renter demand ({rp*100:.0f}% renters) → 4% vacancy"
        elif rp > 0.40:
            est_vacancy = Decimal("0.05")
            vacancy_just = f"Moderate renter demand ({rp*100:.0f}% renters) → 5% vacancy"
        elif rp > 0.20:
            est_vacancy = Decimal("0.06")
            vacancy_just = f"Lower renter demand ({rp*100:.0f}% renters) → 6% vacancy"
        else:
            est_vacancy = Decimal("0.08")
            vacancy_just = f"Low renter demand ({rp*100:.0f}% renters) → 8% vacancy"
        vacancy_conf = Confidence.MEDIUM

    vacancy_rate, d = _override_or(
        "vacancy_rate", ov.vacancy_rate,
        est_vacancy, AssumptionSource.ESTIMATED, vacancy_conf, vacancy_just,
    )
    details["vacancy_rate"] = d

    # ------------------------------------------------------------------
    # Property Tax
    # ------------------------------------------------------------------
    est_tax = prop.annual_tax or Decimal("0")
    if est_tax > 0:
        tax_source = AssumptionSource.API_FETCHED
        tax_conf = Confidence.HIGH
        tax_just = f"RentCast/county assessor: ${float(est_tax):,.0f}/yr"
    else:
        # Fallback: 1% of value
        est_tax = (purchase_price * Decimal("0.01")).quantize(Decimal("1"))
        tax_source = AssumptionSource.DEFAULT
        tax_conf = Confidence.LOW
        tax_just = f"Default 1% of value: ${float(est_tax):,.0f}/yr"

    property_tax, d = _override_or(
        "property_tax", ov.property_tax,
        est_tax, tax_source, tax_conf, tax_just,
    )
    details["property_tax"] = d

    # ------------------------------------------------------------------
    # Insurance (composite model)
    # ------------------------------------------------------------------
    flood_zone = neighborhood.flood_zone if neighborhood else None
    seismic_pga = neighborhood.seismic_pga if neighborhood else None
    wildfire_risk = neighborhood.wildfire_risk if neighborhood else None
    hurricane_zone_val = neighborhood.hurricane_zone if neighborhood else get_hurricane_zone(state)
    hail_freq = neighborhood.hail_frequency if neighborhood else get_hail_frequency(state)
    crime_rate_val = neighborhood.crime_rate if neighborhood else None
    if crime_rate_val is None:
        prop_crime, _ = get_crime_rate(state)
        crime_rate_val = prop_crime

    est_insurance, insurance_detail = estimate_insurance_composite(
        property_value=purchase_price,
        year_built=prop.year_built or 2000,
        property_type=prop.property_type,
        flood_zone=flood_zone,
        seismic_pga=seismic_pga,
        wildfire_risk=wildfire_risk,
        hurricane_zone=hurricane_zone_val or 0,
        hail_frequency=hail_freq or "low",
        crime_rate=crime_rate_val,
    )

    if ov.insurance is not None:
        insurance = ov.insurance
        details["insurance"] = _detail(
            "insurance", insurance, AssumptionSource.USER_OVERRIDE,
            Confidence.HIGH, f"User override: ${float(insurance):,.0f}/yr",
        )
    else:
        insurance = est_insurance
        details["insurance"] = insurance_detail

    # ------------------------------------------------------------------
    # Maintenance %
    # ------------------------------------------------------------------
    climate_zone = get_climate_zone(state)
    renter_pct = None
    if neighborhood and neighborhood.demographics:
        renter_pct = neighborhood.demographics.renter_pct

    est_maint, maint_detail = estimate_maintenance_pct(
        year_built=prop.year_built or 2000,
        condition_grade=condition_grade,
        climate_zone=climate_zone,
        renter_pct=renter_pct,
    )

    if ov.maintenance_pct is not None:
        maintenance_pct = ov.maintenance_pct
        details["maintenance_pct"] = _detail(
            "maintenance_pct", maintenance_pct, AssumptionSource.USER_OVERRIDE,
            Confidence.HIGH, f"User override: {float(maintenance_pct)*100:.1f}%",
        )
    else:
        maintenance_pct = est_maint
        details["maintenance_pct"] = maint_detail

    # ------------------------------------------------------------------
    # Management Fee
    # ------------------------------------------------------------------
    est_mgmt = Decimal("0.08")
    mgmt_just = "Default 8% SFR management"
    if prop.property_type.upper().replace("-", "").replace(" ", "") in ("MULTIFAMILY", "MULTI"):
        est_mgmt = Decimal("0.06")
        mgmt_just = "Multi-family: 6% management"

    management_pct, d = _override_or(
        "management_pct", ov.management_pct,
        est_mgmt, AssumptionSource.DEFAULT, Confidence.MEDIUM, mgmt_just,
    )
    details["management_pct"] = d

    # ------------------------------------------------------------------
    # CapEx Reserve
    # ------------------------------------------------------------------
    capex_reserve_pct, d = _override_or(
        "capex_reserve_pct", ov.capex_reserve_pct,
        Decimal("0.05"), AssumptionSource.DEFAULT, Confidence.MEDIUM,
        "Standard 5% capex reserve",
    )
    details["capex_reserve_pct"] = d

    # ------------------------------------------------------------------
    # HOA
    # ------------------------------------------------------------------
    est_hoa = Decimal("0")
    hoa_just = "No HOA"
    if prop.property_type.upper() in ("CONDO", "TOWNHOUSE"):
        est_hoa = Decimal("250")  # Rough default for condo/townhouse
        hoa_just = "Estimated condo/townhouse HOA: $250/mo"

    hoa, d = _override_or(
        "hoa", ov.hoa,
        est_hoa, AssumptionSource.DEFAULT, Confidence.LOW, hoa_just,
    )
    details["hoa"] = d

    # ------------------------------------------------------------------
    # Appreciation
    # ------------------------------------------------------------------
    walk_score_val = None
    if neighborhood and neighborhood.walk_score:
        walk_score_val = neighborhood.walk_score.walk_score

    est_appr, appr_detail = estimate_appreciation(
        neighborhood_grade=neighborhood.grade if neighborhood else None,
        cpi_5yr_cagr=macro.cpi_5yr_cagr,
        walk_score=walk_score_val,
    )

    if ov.annual_appreciation is not None:
        annual_appreciation = ov.annual_appreciation
        details["annual_appreciation"] = _detail(
            "annual_appreciation", annual_appreciation, AssumptionSource.USER_OVERRIDE,
            Confidence.HIGH, f"User override: {float(annual_appreciation)*100:.1f}%",
        )
    else:
        annual_appreciation = est_appr
        details["annual_appreciation"] = appr_detail

    # ------------------------------------------------------------------
    # Land Value %
    # ------------------------------------------------------------------
    est_land_pct = Decimal("0.20")
    land_just = "Default 20% land value"
    land_conf = Confidence.LOW
    if prop.assessed_value and prop.assessed_value > 0 and purchase_price > 0:
        # Some assessors break out land vs improvement
        # For now, use 20% as default; could enhance with county-level data
        pass

    land_value_pct, d = _override_or(
        "land_value_pct", ov.land_value_pct,
        est_land_pct, AssumptionSource.DEFAULT, land_conf, land_just,
    )
    details["land_value_pct"] = d

    # ------------------------------------------------------------------
    # Expense Growth
    # ------------------------------------------------------------------
    est_expense_growth = macro.cpi_5yr_cagr or Decimal("0.02")
    exp_just = f"CPI 5yr CAGR: {float(est_expense_growth)*100:.1f}%"
    exp_conf = Confidence.MEDIUM if macro.cpi_5yr_cagr else Confidence.LOW

    annual_expense_growth, d = _override_or(
        "annual_expense_growth", ov.annual_expense_growth,
        est_expense_growth, AssumptionSource.ESTIMATED, exp_conf, exp_just,
    )
    details["annual_expense_growth"] = d

    # ------------------------------------------------------------------
    # Hold Years
    # ------------------------------------------------------------------
    hold_years, d = _override_or(
        "hold_years", ov.hold_years,
        Decimal("7"), AssumptionSource.DEFAULT, Confidence.MEDIUM,
        "Default 7-year hold",
    )
    details["hold_years"] = d

    # ------------------------------------------------------------------
    # Selling Costs
    # ------------------------------------------------------------------
    selling_costs_pct, d = _override_or(
        "selling_costs_pct", ov.selling_costs_pct,
        Decimal("0.06"), AssumptionSource.DEFAULT, Confidence.HIGH,
        "Standard 6% selling costs (agent commission + closing)",
    )
    details["selling_costs_pct"] = d

    # ------------------------------------------------------------------
    # Closing Costs
    # ------------------------------------------------------------------
    est_closing, est_closing_pct = estimate_closing_costs(purchase_price, state)
    closing_just = f"State-level estimate ({state}): {float(est_closing_pct)*100:.1f}% = ${float(est_closing):,.0f}"

    if ov.closing_cost_pct is not None:
        closing_costs = (purchase_price * ov.closing_cost_pct).quantize(Decimal("1"))
        details["closing_costs"] = _detail(
            "closing_costs", closing_costs, AssumptionSource.USER_OVERRIDE,
            Confidence.HIGH, f"User override: {float(ov.closing_cost_pct)*100:.1f}%",
        )
    else:
        closing_costs = est_closing
        details["closing_costs"] = _detail(
            "closing_costs", closing_costs, AssumptionSource.ESTIMATED,
            Confidence.MEDIUM, closing_just,
        )

    # ------------------------------------------------------------------
    # Build DealAssumptions
    # ------------------------------------------------------------------
    assumptions = DealAssumptions(
        purchase_price=purchase_price,
        closing_costs=closing_costs,
        land_value_pct=land_value_pct,
        ltv=ltv,
        interest_rate=interest_rate,
        loan_term_years=int(loan_term),
        loan_points=loan.points,
        loan_type=loan_type,
        monthly_rent=monthly_rent,
        annual_rent_growth=annual_rent_growth,
        vacancy_rate=vacancy_rate,
        property_tax=property_tax,
        insurance=insurance,
        maintenance_pct=maintenance_pct,
        management_pct=management_pct,
        capex_reserve_pct=capex_reserve_pct,
        hoa=hoa,
        annual_appreciation=annual_appreciation,
        hold_years=int(hold_years),
        selling_costs_pct=selling_costs_pct,
        annual_expense_growth=annual_expense_growth,
        rehab_budget=rehab_budget or RehabBudget(condition_grade=ConditionGrade.TURNKEY),
    )

    manifest = AssumptionManifest(details=details)
    return assumptions, manifest
