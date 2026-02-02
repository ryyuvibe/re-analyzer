from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class FilingStatus(Enum):
    SINGLE = "single"
    MFJ = "married_filing_jointly"
    MFS = "married_filing_separately"
    HOH = "head_of_household"


@dataclass(frozen=True)
class InvestorTaxProfile:
    filing_status: FilingStatus
    agi: Decimal  # Adjusted gross income
    marginal_federal_rate: Decimal  # e.g. Decimal("0.37")
    marginal_state_rate: Decimal  # e.g. Decimal("0.133") for CA
    state: str  # Two-letter state code for state tax conformity
    other_passive_income: Decimal = Decimal("0")
    is_re_professional: bool = False  # IRC 469(c)(7)

    @property
    def combined_rate(self) -> Decimal:
        # Simplified: federal + state (ignoring SALT deduction interactions)
        return self.marginal_federal_rate + self.marginal_state_rate

    @property
    def niit_applies(self) -> bool:
        """Net Investment Income Tax (3.8%) applies above AGI thresholds."""
        thresholds = {
            FilingStatus.SINGLE: Decimal("200000"),
            FilingStatus.MFJ: Decimal("250000"),
            FilingStatus.MFS: Decimal("125000"),
            FilingStatus.HOH: Decimal("200000"),
        }
        return self.agi > thresholds[self.filing_status]

    @property
    def niit_rate(self) -> Decimal:
        return Decimal("0.038") if self.niit_applies else Decimal("0")

    @property
    def qualifies_for_25k_exception(self) -> bool:
        """$25K rental loss exception phases out $100K-$150K AGI."""
        if self.is_re_professional:
            return False  # RE pros don't need the exception
        return self.agi < Decimal("150000")

    @property
    def rental_loss_allowance(self) -> Decimal:
        """Maximum deductible rental loss under $25K exception."""
        if not self.qualifies_for_25k_exception:
            return Decimal("0")
        if self.agi <= Decimal("100000"):
            return Decimal("25000")
        # Phase out: $1 for every $2 of AGI over $100K
        reduction = (self.agi - Decimal("100000")) / 2
        return max(Decimal("0"), Decimal("25000") - reduction)
