"""Property disposition (sale) analysis.

IRC 1250 depreciation recapture, IRC 1231 capital gains,
and IRC 469(g)(1)(A) suspended passive loss release.

Pure functions. No I/O.
"""

from decimal import Decimal, ROUND_HALF_UP

from src.models.assumptions import DealAssumptions
from src.models.investor import InvestorTaxProfile
from src.models.results import DispositionResult

TWO_PLACES = Decimal("0.01")

# Tax rates
RECAPTURE_RATE = Decimal("0.25")  # IRC 1250 unrecaptured Sec 1250 gain
LTCG_RATE = Decimal("0.20")  # IRC 1231 long-term capital gain (top bracket)


def compute_disposition(
    assumptions: DealAssumptions,
    investor: InvestorTaxProfile,
    sale_price: Decimal,
    loan_balance: Decimal,
    total_depreciation_taken: Decimal,
    cumulative_suspended_losses: Decimal,
) -> DispositionResult:
    """Compute after-tax proceeds from property sale.

    Args:
        assumptions: Deal assumptions (for basis calculation)
        investor: Tax profile
        sale_price: Gross sale price
        loan_balance: Remaining mortgage balance at time of sale
        total_depreciation_taken: Sum of all depreciation claimed
        cumulative_suspended_losses: Total passive losses suspended per IRC 469
    """
    # Sale proceeds
    selling_costs = (sale_price * assumptions.selling_costs_pct).quantize(
        TWO_PLACES, ROUND_HALF_UP
    )
    net_sale_proceeds = sale_price - selling_costs
    gross_equity_proceeds = net_sale_proceeds - loan_balance

    # Gain calculation
    adjusted_basis = assumptions.total_basis - total_depreciation_taken
    total_gain = net_sale_proceeds - adjusted_basis

    if total_gain <= 0:
        # Loss on sale - no tax, but suspended losses still release
        tax_benefit_from_release = (
            cumulative_suspended_losses * investor.combined_rate
        ).quantize(TWO_PLACES, ROUND_HALF_UP)

        return DispositionResult(
            sale_price=sale_price,
            selling_costs=selling_costs,
            net_sale_proceeds=net_sale_proceeds,
            loan_payoff=loan_balance,
            gross_equity_proceeds=gross_equity_proceeds,
            adjusted_basis=adjusted_basis,
            total_gain=total_gain,
            suspended_losses_released=cumulative_suspended_losses,
            tax_benefit_from_release=tax_benefit_from_release,
            total_tax_on_sale=-tax_benefit_from_release,
            after_tax_sale_proceeds=gross_equity_proceeds + tax_benefit_from_release,
        )

    # IRC 1250: depreciation recapture (taxed at max 25%)
    depreciation_recapture = min(total_depreciation_taken, total_gain)
    capital_gain = total_gain - depreciation_recapture

    # Tax computations
    recapture_tax = (depreciation_recapture * RECAPTURE_RATE).quantize(
        TWO_PLACES, ROUND_HALF_UP
    )
    capital_gains_tax = (capital_gain * LTCG_RATE).quantize(TWO_PLACES, ROUND_HALF_UP)

    # NIIT on total gain
    niit = (total_gain * investor.niit_rate).quantize(TWO_PLACES, ROUND_HALF_UP)

    # State tax on total gain
    state_tax = (total_gain * investor.marginal_state_rate).quantize(
        TWO_PLACES, ROUND_HALF_UP
    )

    # IRC 469(g)(1)(A): On full taxable disposition, all suspended passive
    # losses are released. Order of offset:
    # 1. Gain from this activity (reduces taxable gain)
    # 2. Other passive income
    # 3. Any remaining income (ordinary rates)
    #
    # For simplicity, we compute the tax benefit of releasing suspended
    # losses at the investor's combined marginal rate.
    suspended_losses_released = cumulative_suspended_losses

    # Suspended losses first offset the gain from this activity
    gain_offset = min(suspended_losses_released, total_gain)
    remaining_suspended = suspended_losses_released - gain_offset

    # Tax benefit: gain offset saves tax at gain rates,
    # remaining suspended losses save at ordinary rates
    benefit_from_gain_offset = (
        min(gain_offset, depreciation_recapture) * RECAPTURE_RATE
        + max(Decimal("0"), gain_offset - depreciation_recapture) * LTCG_RATE
        + gain_offset * investor.niit_rate
        + gain_offset * investor.marginal_state_rate
    ).quantize(TWO_PLACES, ROUND_HALF_UP)

    benefit_from_remaining = (
        remaining_suspended * investor.combined_rate
    ).quantize(TWO_PLACES, ROUND_HALF_UP)

    tax_benefit_from_release = benefit_from_gain_offset + benefit_from_remaining

    total_tax = recapture_tax + capital_gains_tax + niit + state_tax - tax_benefit_from_release
    after_tax_proceeds = gross_equity_proceeds - total_tax

    return DispositionResult(
        sale_price=sale_price,
        selling_costs=selling_costs,
        net_sale_proceeds=net_sale_proceeds,
        loan_payoff=loan_balance,
        gross_equity_proceeds=gross_equity_proceeds,
        adjusted_basis=adjusted_basis,
        total_gain=total_gain,
        depreciation_recapture=depreciation_recapture,
        capital_gain=capital_gain,
        recapture_tax=recapture_tax,
        capital_gains_tax=capital_gains_tax,
        niit_on_gain=niit,
        state_tax_on_gain=state_tax,
        suspended_losses_released=suspended_losses_released,
        tax_benefit_from_release=tax_benefit_from_release,
        total_tax_on_sale=total_tax,
        after_tax_sale_proceeds=after_tax_proceeds,
    )
