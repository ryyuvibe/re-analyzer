from decimal import Decimal

from src.engine.irr import compute_irr, compute_equity_multiple


class TestIRR:
    def test_simple_irr(self):
        """Invest $100, get $110 after 1 year = 10% IRR."""
        irr = compute_irr([Decimal("-100"), Decimal("110")])
        assert abs(irr - Decimal("0.10")) < Decimal("0.001")

    def test_multi_year(self):
        """Known cash flows with ~15% IRR."""
        cfs = [Decimal("-100000"), Decimal("10000"), Decimal("10000"),
               Decimal("10000"), Decimal("10000"), Decimal("130000")]
        irr = compute_irr(cfs)
        assert Decimal("0.10") < irr < Decimal("0.20")

    def test_negative_returns(self):
        """All-negative cash flows should return 0."""
        irr = compute_irr([Decimal("-100"), Decimal("-10"), Decimal("-10")])
        assert irr == Decimal("0")

    def test_empty_cash_flows(self):
        assert compute_irr([]) == Decimal("0")


class TestEquityMultiple:
    def test_basic(self):
        em = compute_equity_multiple(Decimal("200000"), Decimal("100000"))
        assert em == Decimal("2.0000")

    def test_zero_investment(self):
        em = compute_equity_multiple(Decimal("100000"), Decimal("0"))
        assert em == Decimal("0")
