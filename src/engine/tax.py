"""Passive activity loss tracking per IRC 469.

Tracks suspended losses year-over-year, handles the $25K rental exception,
RE professional status, and NIIT.

Pure functions: dataclasses in, dataclasses out. No I/O.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from src.models.investor import InvestorTaxProfile

TWO_PLACES = Decimal("0.01")


@dataclass
class PassiveActivityEntry:
    year: int
    rental_income_or_loss: Decimal  # Negative = loss
    other_passive_income: Decimal
    deductible_amount: Decimal  # Amount actually deducted this year
    suspended_amount: Decimal  # Amount suspended (carried forward)
    cumulative_suspended: Decimal  # Running total of suspended losses
    tax_benefit: Decimal  # Tax saved from deductible amount


@dataclass
class PassiveActivityLedger:
    entries: list[PassiveActivityEntry] = field(default_factory=list)

    @property
    def total_suspended(self) -> Decimal:
        if not self.entries:
            return Decimal("0")
        return self.entries[-1].cumulative_suspended

    @property
    def total_tax_benefit(self) -> Decimal:
        return sum((e.tax_benefit for e in self.entries), Decimal("0"))


def compute_passive_activity(
    rental_income_or_loss: Decimal,
    investor: InvestorTaxProfile,
    prior_suspended: Decimal,
    year: int,
) -> PassiveActivityEntry:
    """Compute passive activity result for one year.

    Args:
        rental_income_or_loss: Net rental income (positive) or loss (negative).
            This is NOI - debt service interest - depreciation (taxable income from rental).
        investor: Tax profile
        prior_suspended: Cumulative suspended losses from prior years
        year: Year number for tracking
    """
    net_passive = rental_income_or_loss + investor.other_passive_income

    if net_passive >= 0:
        # Passive income: can offset with suspended losses
        usable_suspended = min(prior_suspended, net_passive)
        deductible = net_passive - usable_suspended  # Remaining is taxable income
        # Actually, suspended losses offset passive income
        deductible = -usable_suspended  # This reduces taxable income
        new_suspended = prior_suspended - usable_suspended
        # Tax benefit from releasing suspended losses
        tax_benefit = (usable_suspended * investor.combined_rate).quantize(
            TWO_PLACES, ROUND_HALF_UP
        )
        return PassiveActivityEntry(
            year=year,
            rental_income_or_loss=rental_income_or_loss,
            other_passive_income=investor.other_passive_income,
            deductible_amount=deductible,
            suspended_amount=Decimal("0"),
            cumulative_suspended=new_suspended,
            tax_benefit=tax_benefit,
        )

    # Net passive loss
    loss = abs(net_passive)

    if investor.is_re_professional:
        # RE professional: all rental losses are non-passive (fully deductible)
        tax_benefit = (loss * investor.combined_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        return PassiveActivityEntry(
            year=year,
            rental_income_or_loss=rental_income_or_loss,
            other_passive_income=investor.other_passive_income,
            deductible_amount=-loss,
            suspended_amount=Decimal("0"),
            cumulative_suspended=prior_suspended,
            tax_benefit=tax_benefit,
        )

    # Check $25K exception
    allowance = investor.rental_loss_allowance
    deductible_loss = min(loss, allowance)
    suspended = loss - deductible_loss

    tax_benefit = (deductible_loss * investor.combined_rate).quantize(
        TWO_PLACES, ROUND_HALF_UP
    )
    new_suspended = prior_suspended + suspended

    return PassiveActivityEntry(
        year=year,
        rental_income_or_loss=rental_income_or_loss,
        other_passive_income=investor.other_passive_income,
        deductible_amount=-deductible_loss,
        suspended_amount=suspended,
        cumulative_suspended=new_suspended,
        tax_benefit=tax_benefit,
    )


def build_passive_activity_ledger(
    yearly_rental_income_or_loss: list[Decimal],
    investor: InvestorTaxProfile,
) -> PassiveActivityLedger:
    """Build complete passive activity ledger across all hold years."""
    ledger = PassiveActivityLedger()
    prior_suspended = Decimal("0")

    for i, income_or_loss in enumerate(yearly_rental_income_or_loss):
        entry = compute_passive_activity(
            rental_income_or_loss=income_or_loss,
            investor=investor,
            prior_suspended=prior_suspended,
            year=i + 1,
        )
        ledger.entries.append(entry)
        prior_suspended = entry.cumulative_suspended

    return ledger


def taxable_rental_income(
    noi: Decimal,
    interest_paid: Decimal,
    depreciation: Decimal,
) -> Decimal:
    """Compute taxable income from rental activity.

    Taxable income = NOI - mortgage interest - depreciation
    (Principal payments are NOT deductible.)
    """
    return noi - interest_paid - depreciation
