from decimal import Decimal

from src.engine.disposition import compute_disposition
from src.models.assumptions import DealAssumptions
from src.models.investor import InvestorTaxProfile, FilingStatus


class TestDisposition:
    def test_basic_sale(self, canonical_assumptions, canonical_investor):
        result = compute_disposition(
            assumptions=canonical_assumptions,
            investor=canonical_investor,
            sale_price=Decimal("615000"),
            loan_balance=Decimal("375000"),
            total_depreciation_taken=Decimal("90000"),
            cumulative_suspended_losses=Decimal("50000"),
        )

        assert result.sale_price == Decimal("615000")
        assert result.selling_costs == Decimal("36900.00")  # 6%
        assert result.net_sale_proceeds == Decimal("578100.00")
        assert result.loan_payoff == Decimal("375000")
        assert result.gross_equity_proceeds == Decimal("203100.00")

    def test_depreciation_recapture(self, canonical_assumptions, canonical_investor):
        """IRC 1250: recapture taxed at 25%."""
        result = compute_disposition(
            assumptions=canonical_assumptions,
            investor=canonical_investor,
            sale_price=Decimal("615000"),
            loan_balance=Decimal("375000"),
            total_depreciation_taken=Decimal("90000"),
            cumulative_suspended_losses=Decimal("0"),
        )
        # Total gain = 578100 - (505000 - 90000) = 578100 - 415000 = 163100
        assert result.total_gain == Decimal("163100.00")
        assert result.depreciation_recapture == Decimal("90000")
        assert result.capital_gain == Decimal("73100.00")
        assert result.recapture_tax == Decimal("22500.00")

    def test_suspended_loss_release(self, canonical_assumptions, canonical_investor):
        """IRC 469(g)(1)(A): suspended losses released on disposition."""
        result = compute_disposition(
            assumptions=canonical_assumptions,
            investor=canonical_investor,
            sale_price=Decimal("615000"),
            loan_balance=Decimal("375000"),
            total_depreciation_taken=Decimal("90000"),
            cumulative_suspended_losses=Decimal("50000"),
        )
        assert result.suspended_losses_released == Decimal("50000")
        assert result.tax_benefit_from_release > 0

    def test_loss_on_sale(self, canonical_assumptions, canonical_investor):
        """Sale at a loss: no capital gains tax, but suspended losses still release."""
        result = compute_disposition(
            assumptions=canonical_assumptions,
            investor=canonical_investor,
            sale_price=Decimal("400000"),
            loan_balance=Decimal("375000"),
            total_depreciation_taken=Decimal("90000"),
            cumulative_suspended_losses=Decimal("50000"),
        )
        assert result.total_gain < 0
        assert result.recapture_tax == Decimal("0")
        assert result.suspended_losses_released == Decimal("50000")
        assert result.tax_benefit_from_release > 0

    def test_after_tax_proceeds_positive(self, canonical_assumptions, canonical_investor):
        result = compute_disposition(
            assumptions=canonical_assumptions,
            investor=canonical_investor,
            sale_price=Decimal("615000"),
            loan_balance=Decimal("375000"),
            total_depreciation_taken=Decimal("90000"),
            cumulative_suspended_losses=Decimal("50000"),
        )
        assert result.after_tax_sale_proceeds > 0
