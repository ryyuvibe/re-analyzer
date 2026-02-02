from decimal import Decimal

from src.engine.tax import (
    compute_passive_activity,
    build_passive_activity_ledger,
    taxable_rental_income,
)
from src.models.investor import InvestorTaxProfile, FilingStatus


class TestTaxableRentalIncome:
    def test_basic_calculation(self):
        """Taxable = NOI - interest - depreciation."""
        result = taxable_rental_income(
            noi=Decimal("20000"),
            interest_paid=Decimal("15000"),
            depreciation=Decimal("10000"),
        )
        assert result == Decimal("-5000")  # Loss

    def test_positive_taxable(self):
        result = taxable_rental_income(
            noi=Decimal("30000"),
            interest_paid=Decimal("10000"),
            depreciation=Decimal("5000"),
        )
        assert result == Decimal("15000")


class TestPassiveActivityHighIncome:
    """Scenario 1: AGI > $150K, all losses suspended."""

    def test_all_losses_suspended(self, canonical_investor):
        """High-income investor: no $25K exception, all losses suspended."""
        entry = compute_passive_activity(
            rental_income_or_loss=Decimal("-10000"),
            investor=canonical_investor,
            prior_suspended=Decimal("0"),
            year=1,
        )
        assert entry.suspended_amount == Decimal("10000")
        assert entry.deductible_amount == Decimal("0")
        assert entry.tax_benefit == Decimal("0")

    def test_multi_year_accumulation(self, canonical_investor):
        """Suspended losses accumulate across years."""
        losses = [Decimal("-10000")] * 3
        ledger = build_passive_activity_ledger(losses, canonical_investor)

        assert ledger.entries[0].cumulative_suspended == Decimal("10000")
        assert ledger.entries[1].cumulative_suspended == Decimal("20000")
        assert ledger.entries[2].cumulative_suspended == Decimal("30000")
        assert ledger.total_tax_benefit == Decimal("0")


class TestPassiveActivityLowIncome:
    """Scenario 2: AGI < $100K, $25K exception applies."""

    def test_25k_exception(self, low_income_investor):
        """Low-income investor can deduct up to $25K rental loss."""
        entry = compute_passive_activity(
            rental_income_or_loss=Decimal("-20000"),
            investor=low_income_investor,
            prior_suspended=Decimal("0"),
            year=1,
        )
        assert entry.deductible_amount == Decimal("-20000")
        assert entry.suspended_amount == Decimal("0")
        assert entry.tax_benefit > 0

    def test_25k_cap(self, low_income_investor):
        """Loss exceeding $25K: excess is suspended."""
        entry = compute_passive_activity(
            rental_income_or_loss=Decimal("-30000"),
            investor=low_income_investor,
            prior_suspended=Decimal("0"),
            year=1,
        )
        assert entry.deductible_amount == Decimal("-25000")
        assert entry.suspended_amount == Decimal("5000")


class TestPassiveActivityPhaseOut:
    """AGI between $100K and $150K: $25K exception phases out."""

    def test_phaseout(self):
        investor = InvestorTaxProfile(
            filing_status=FilingStatus.MFJ,
            agi=Decimal("120000"),
            marginal_federal_rate=Decimal("0.24"),
            marginal_state_rate=Decimal("0.06"),
            state="TX",
        )
        # At $120K AGI: allowance = 25000 - (120000-100000)/2 = 25000 - 10000 = $15000
        assert investor.rental_loss_allowance == Decimal("15000")

        entry = compute_passive_activity(
            rental_income_or_loss=Decimal("-20000"),
            investor=investor,
            prior_suspended=Decimal("0"),
            year=1,
        )
        assert entry.deductible_amount == Decimal("-15000")
        assert entry.suspended_amount == Decimal("5000")


class TestPassiveActivityREProfessional:
    """RE professional: all rental losses are fully deductible."""

    def test_full_deduction(self, re_professional_investor):
        entry = compute_passive_activity(
            rental_income_or_loss=Decimal("-50000"),
            investor=re_professional_investor,
            prior_suspended=Decimal("0"),
            year=1,
        )
        assert entry.deductible_amount == Decimal("-50000")
        assert entry.suspended_amount == Decimal("0")
        assert entry.tax_benefit > 0


class TestPassiveIncomeOffsetsLosses:
    """Passive income releases suspended losses."""

    def test_income_releases_suspended(self, canonical_investor):
        """Year 1: $10K loss suspended. Year 2: $15K passive income releases it."""
        losses = [Decimal("-10000"), Decimal("15000")]
        # Override investor to have no other passive income
        ledger = build_passive_activity_ledger(losses, canonical_investor)

        assert ledger.entries[0].cumulative_suspended == Decimal("10000")
        # Year 2: $15K income, $10K suspended released
        assert ledger.entries[1].cumulative_suspended == Decimal("0")
        assert ledger.entries[1].tax_benefit > 0
