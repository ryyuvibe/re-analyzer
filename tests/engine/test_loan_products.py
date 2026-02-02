"""Tests for loan product models."""

from decimal import Decimal

import pytest

from src.engine.loan_products import conventional_loan, dscr_loan
from src.models.smart_assumptions import MacroContext


@pytest.fixture
def macro_with_rate():
    return MacroContext(mortgage_rate_30y=Decimal("0.0685"))


@pytest.fixture
def macro_no_rate():
    return MacroContext()


class TestConventionalLoan:
    def test_excellent_credit(self, macro_with_rate):
        loan = conventional_loan(macro_with_rate, credit_score_tier="excellent")
        # 6.85% + 0.75% investor = 7.60%
        assert loan.interest_rate == Decimal("0.0760")
        assert loan.ltv == Decimal("0.80")
        assert loan.loan_term_years == 30
        assert loan.points == Decimal("0")
        assert loan.loan_type == "conventional"

    def test_good_credit(self, macro_with_rate):
        loan = conventional_loan(macro_with_rate, credit_score_tier="good")
        # 6.85% + 0.75% + 0.25% = 7.85%
        assert loan.interest_rate == Decimal("0.0785")

    def test_fair_credit(self, macro_with_rate):
        loan = conventional_loan(macro_with_rate, credit_score_tier="fair")
        # 6.85% + 0.75% + 0.75% = 8.35%
        assert loan.interest_rate == Decimal("0.0835")

    def test_fallback_rate(self, macro_no_rate):
        loan = conventional_loan(macro_no_rate)
        # 7.0% fallback + 0.75% = 7.75%
        assert loan.interest_rate == Decimal("0.0775")

    def test_rate_source_justification(self, macro_with_rate):
        loan = conventional_loan(macro_with_rate)
        assert "FRED" in loan.rate_source
        assert "6.85%" in loan.rate_source
        assert "investment property premium" in loan.rate_source


class TestDSCRLoan:
    def test_strong_dscr(self, macro_with_rate):
        loan = dscr_loan(macro_with_rate, estimated_dscr=Decimal("1.30"))
        # 6.85% + 0.75% + 1.0% = 8.60%
        assert loan.interest_rate == Decimal("0.0860")
        assert loan.ltv == Decimal("0.80")
        assert loan.points == Decimal("1")

    def test_marginal_dscr(self, macro_with_rate):
        loan = dscr_loan(macro_with_rate, estimated_dscr=Decimal("1.10"))
        # 6.85% + 0.75% + 1.75% = 9.35%
        assert loan.interest_rate == Decimal("0.0935")
        assert loan.ltv == Decimal("0.75")
        assert loan.points == Decimal("1.5")

    def test_weak_dscr(self, macro_with_rate):
        loan = dscr_loan(macro_with_rate, estimated_dscr=Decimal("0.90"))
        # 6.85% + 0.75% + 2.5% = 10.10%
        assert loan.interest_rate == Decimal("0.1010")
        assert loan.ltv == Decimal("0.65")
        assert loan.points == Decimal("2")

    def test_dscr_has_prepayment_penalty(self, macro_with_rate):
        loan = dscr_loan(macro_with_rate, estimated_dscr=Decimal("1.25"))
        assert loan.prepayment_penalty == "3-2-1 stepdown"
        assert loan.min_dscr == Decimal("1.0")

    def test_rate_spread_conventional_vs_dscr(self, macro_with_rate):
        conv = conventional_loan(macro_with_rate)
        dscr = dscr_loan(macro_with_rate, estimated_dscr=Decimal("1.30"))
        # DSCR should be higher
        assert dscr.interest_rate > conv.interest_rate
        # Spread should be about 100bps for 1.30x DSCR
        spread = dscr.interest_rate - conv.interest_rate
        assert Decimal("0.009") <= spread <= Decimal("0.011")
