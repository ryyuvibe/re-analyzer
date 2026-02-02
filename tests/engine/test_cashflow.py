from decimal import Decimal

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


class TestGrossRent:
    def test_year_1(self, canonical_assumptions):
        gr = gross_rent(canonical_assumptions, 1)
        assert gr == Decimal("33600.00")  # 2800 * 12

    def test_year_2_with_growth(self, canonical_assumptions):
        gr = gross_rent(canonical_assumptions, 2)
        expected = Decimal("33600") * Decimal("1.03")
        assert gr == expected.quantize(Decimal("0.01"))


class TestEffectiveGrossIncome:
    def test_vacancy_deduction(self, canonical_assumptions):
        egi = effective_gross_income(canonical_assumptions, 1)
        gr = Decimal("33600.00")
        vacancy = gr * Decimal("0.05")
        assert egi == gr - vacancy  # No other income by default


class TestOperatingExpenses:
    def test_year_1_itemized(self, canonical_assumptions):
        expenses = operating_expenses(canonical_assumptions, 1)
        assert expenses["property_tax"] == Decimal("6000.00")
        assert expenses["insurance"] == Decimal("1500.00")
        # Maintenance = 5% of gross rent
        assert expenses["maintenance"] == Decimal("1680.00")
        # Management = 8% of gross rent
        assert expenses["management"] == Decimal("2688.00")

    def test_expenses_grow(self, canonical_assumptions):
        e1 = operating_expenses(canonical_assumptions, 1)
        e2 = operating_expenses(canonical_assumptions, 2)
        assert e2["property_tax"] > e1["property_tax"]


class TestNOI:
    def test_positive_noi(self, canonical_assumptions):
        n = noi(canonical_assumptions, 1)
        assert n > 0


class TestCapRate:
    def test_cap_rate_calculation(self, canonical_assumptions):
        cr = cap_rate(canonical_assumptions, 1)
        year1_noi = noi(canonical_assumptions, 1)
        expected = year1_noi / Decimal("500000")
        assert abs(cr - expected) < Decimal("0.001")


class TestCashOnCash:
    def test_positive_return(self):
        coc = cash_on_cash(Decimal("5000"), Decimal("100000"))
        assert coc == Decimal("0.0500")

    def test_zero_investment(self):
        coc = cash_on_cash(Decimal("5000"), Decimal("0"))
        assert coc == Decimal("0")


class TestDSCR:
    def test_above_one(self):
        d = dscr(Decimal("30000"), Decimal("25000"))
        assert d > Decimal("1")

    def test_zero_debt_service(self):
        d = dscr(Decimal("30000"), Decimal("0"))
        assert d == Decimal("0")


class TestPropertyValue:
    def test_appreciation(self, canonical_assumptions):
        pv = property_value(canonical_assumptions, 7)
        expected = Decimal("500000") * Decimal("1.03") ** 7
        assert abs(pv - expected) < Decimal("1")
