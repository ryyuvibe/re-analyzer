from decimal import Decimal

from src.engine.opportunity_cost import (
    sp500_equity_curve,
    sp500_after_tax_proceeds,
    sharpe_ratio,
    build_comparison,
)


class TestSP500EquityCurve:
    def test_length(self):
        curve = sp500_equity_curve(Decimal("100000"), 7)
        assert len(curve) == 8  # year 0 + 7 years

    def test_grows(self):
        curve = sp500_equity_curve(Decimal("100000"), 7)
        for i in range(1, len(curve)):
            assert curve[i] > curve[i - 1]

    def test_year_0_is_initial(self):
        curve = sp500_equity_curve(Decimal("100000"), 7)
        assert curve[0] == Decimal("100000")


class TestSP500AfterTax:
    def test_gain_taxed(self):
        proceeds = sp500_after_tax_proceeds(
            Decimal("100000"), Decimal("200000"),
            state_tax_rate=Decimal("0.133"),
        )
        # Gain = 100K, taxed at 20% + 3.8% + 13.3% = 37.1%
        assert proceeds < Decimal("200000")
        assert proceeds > Decimal("100000")

    def test_no_gain_no_tax(self):
        proceeds = sp500_after_tax_proceeds(
            Decimal("100000"), Decimal("100000"),
            state_tax_rate=Decimal("0.133"),
        )
        assert proceeds == Decimal("100000")


class TestSharpeRatio:
    def test_basic(self):
        sr = sharpe_ratio(Decimal("0.10"), Decimal("0.15"), Decimal("0.04"))
        assert sr == Decimal("0.4000")

    def test_zero_volatility(self):
        sr = sharpe_ratio(Decimal("0.10"), Decimal("0"), Decimal("0.04"))
        assert sr == Decimal("0")


class TestBuildComparison:
    def test_comparison_structure(self, canonical_assumptions, canonical_investor):
        from src.engine.proforma import run_proforma

        result = run_proforma(canonical_assumptions, canonical_investor)
        re_equity = [p.equity for p in result.yearly_projections]

        total_cash = sum(p.cash_flow_after_tax for p in result.yearly_projections)
        total_cash += result.disposition.after_tax_sale_proceeds

        comparison = build_comparison(
            initial_equity=canonical_assumptions.total_initial_investment,
            re_yearly_equity=re_equity,
            re_after_tax_irr=result.after_tax_irr,
            re_total_cash_returned=total_cash,
            hold_years=canonical_assumptions.hold_years,
            state_tax_rate=canonical_investor.marginal_state_rate,
            niit_applies=canonical_investor.niit_applies,
        )

        assert len(comparison.sp500_yearly_equity) == 8
        assert comparison.sp500_after_tax_irr > 0
