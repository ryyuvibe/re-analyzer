"""Pro forma orchestrator: composes all engine sub-modules into a full analysis.

Pure computation. No I/O. Dataclasses in, AnalysisResult out.
"""

from decimal import Decimal, ROUND_HALF_UP

from src.models.assumptions import DealAssumptions
from src.models.investor import InvestorTaxProfile
from src.models.results import AnalysisResult, YearlyProjection, DispositionResult

from src.engine.debt import amortization_schedule, yearly_debt_summary
from src.engine.cashflow import (
    gross_rent,
    effective_gross_income,
    operating_expenses,
    noi,
    cap_rate,
    cash_on_cash,
    dscr,
    property_value,
)
from src.engine.depreciation import compute_yearly_depreciation, total_depreciation_taken
from src.engine.tax import (
    taxable_rental_income,
    compute_passive_activity,
    PassiveActivityLedger,
)
from src.engine.disposition import compute_disposition
from src.engine.irr import compute_irr, compute_equity_multiple

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def run_proforma(
    assumptions: DealAssumptions,
    investor: InvestorTaxProfile,
) -> AnalysisResult:
    """Run complete pro forma analysis.

    Returns AnalysisResult with yearly projections, disposition analysis,
    and summary metrics.
    """
    # Build amortization schedule
    amort = amortization_schedule(
        principal=assumptions.loan_amount,
        annual_rate=assumptions.interest_rate,
        term_years=assumptions.loan_term_years,
        hold_years=assumptions.hold_years,
    )
    yearly_debt = yearly_debt_summary(amort)

    # Build yearly projections
    projections: list[YearlyProjection] = []
    passive_ledger = PassiveActivityLedger()
    prior_suspended = Decimal("0")
    total_dep = Decimal("0")
    total_tax_benefit = Decimal("0")

    before_tax_cfs: list[Decimal] = [-assumptions.total_initial_investment]
    after_tax_cfs: list[Decimal] = [-assumptions.total_initial_investment]

    for year in range(1, assumptions.hold_years + 1):
        debt_year = yearly_debt[year - 1]
        annual_debt_service = debt_year["debt_service"]

        # Income
        gr = gross_rent(assumptions, year)
        egi = effective_gross_income(assumptions, year)
        vacancy_loss = gr - egi + assumptions.other_income

        # Expenses
        expenses = operating_expenses(assumptions, year)

        # NOI & cash flow
        year_noi = noi(assumptions, year)
        cfbt = year_noi - annual_debt_service

        # Depreciation
        dep = compute_yearly_depreciation(assumptions, year)
        total_dep += dep.total

        # Taxable income
        taxable = taxable_rental_income(
            noi=year_noi,
            interest_paid=debt_year["interest"],
            depreciation=dep.total,
        )

        # Passive activity
        pa_entry = compute_passive_activity(
            rental_income_or_loss=taxable,
            investor=investor,
            prior_suspended=prior_suspended,
            year=year,
        )
        passive_ledger.entries.append(pa_entry)
        prior_suspended = pa_entry.cumulative_suspended
        total_tax_benefit += pa_entry.tax_benefit

        # After-tax cash flow = CFBT + tax benefit
        cfat = cfbt + pa_entry.tax_benefit

        # Property value & equity
        prop_value = property_value(assumptions, year)
        equity = prop_value - debt_year["ending_balance"]

        # Metrics
        year_cap_rate = cap_rate(assumptions, year)
        year_coc = cash_on_cash(cfbt, assumptions.total_initial_investment)
        year_dscr = dscr(year_noi, annual_debt_service)

        # Rehab: compute rent months for year 1
        if year == 1 and assumptions.rehab_budget.rehab_months > 0:
            rent_months = 12 - min(assumptions.rehab_budget.rehab_months, 12)
        else:
            rent_months = 12

        proj = YearlyProjection(
            year=year,
            gross_rent=gr,
            vacancy_loss=vacancy_loss,
            other_income=assumptions.other_income,
            effective_gross_income=egi,
            property_tax=expenses["property_tax"],
            insurance=expenses["insurance"],
            maintenance=expenses["maintenance"],
            management=expenses["management"],
            capex_reserve=expenses["capex_reserve"],
            hoa=expenses["hoa"],
            total_expenses=expenses["total"],
            noi=year_noi,
            debt_service=annual_debt_service,
            cash_flow_before_tax=cfbt,
            principal_paid=debt_year["principal"],
            interest_paid=debt_year["interest"],
            loan_balance=debt_year["ending_balance"],
            depreciation_27_5=dep.residential,
            depreciation_cost_seg=dep.five_year + dep.seven_year + dep.fifteen_year + dep.bonus,
            total_depreciation=dep.total,
            taxable_income=taxable,
            passive_loss=pa_entry.rental_income_or_loss,
            suspended_loss=pa_entry.cumulative_suspended,
            tax_benefit=pa_entry.tax_benefit,
            cash_flow_after_tax=cfat,
            property_value=prop_value,
            equity=equity,
            cap_rate=year_cap_rate,
            cash_on_cash=year_coc,
            dscr=year_dscr,
            rent_months=rent_months,
        )
        projections.append(proj)
        before_tax_cfs.append(cfbt)
        after_tax_cfs.append(cfat)

    # Disposition
    final_year = assumptions.hold_years
    sale_price = property_value(assumptions, final_year)
    loan_balance = yearly_debt[final_year - 1]["ending_balance"]

    disposition = compute_disposition(
        assumptions=assumptions,
        investor=investor,
        sale_price=sale_price,
        loan_balance=loan_balance,
        total_depreciation_taken=total_dep,
        cumulative_suspended_losses=prior_suspended,
    )

    # Add sale proceeds to final year cash flows for IRR
    before_tax_cfs[-1] += disposition.gross_equity_proceeds
    after_tax_cfs[-1] += disposition.after_tax_sale_proceeds

    # IRR
    before_tax_irr = compute_irr(before_tax_cfs)
    after_tax_irr = compute_irr(after_tax_cfs)

    # Total cash returned (for equity multiple)
    total_cfbt = sum(p.cash_flow_before_tax for p in projections)
    total_cfat = sum(p.cash_flow_after_tax for p in projections)
    total_cash_returned = total_cfat + disposition.after_tax_sale_proceeds
    equity_multiple = compute_equity_multiple(
        total_cash_returned, assumptions.total_initial_investment
    )

    # Average cash on cash
    avg_coc = sum(p.cash_on_cash for p in projections) / len(projections) if projections else Decimal("0")

    # Net tax impact
    net_tax_impact = (
        total_tax_benefit
        + disposition.tax_benefit_from_release
        - (disposition.recapture_tax + disposition.capital_gains_tax
           + disposition.niit_on_gain + disposition.state_tax_on_gain)
    )

    return AnalysisResult(
        yearly_projections=projections,
        disposition=disposition,
        total_initial_investment=assumptions.total_initial_investment,
        rehab_total_cost=assumptions.rehab_budget.total_cost,
        rehab_months=assumptions.rehab_budget.rehab_months,
        before_tax_irr=before_tax_irr,
        after_tax_irr=after_tax_irr,
        equity_multiple=equity_multiple,
        average_cash_on_cash=avg_coc.quantize(FOUR_PLACES, ROUND_HALF_UP),
        total_profit=total_cash_returned - assumptions.total_initial_investment,
        total_depreciation_taken=total_dep,
        total_tax_benefit_operations=total_tax_benefit,
        total_suspended_losses=prior_suspended,
        net_tax_impact=net_tax_impact,
    )
