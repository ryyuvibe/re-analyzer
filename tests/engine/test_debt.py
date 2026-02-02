from decimal import Decimal

from src.engine.debt import monthly_payment, amortization_schedule, yearly_debt_summary


class TestMonthlyPayment:
    def test_standard_mortgage(self):
        """$400K loan at 7% for 30 years."""
        pmt = monthly_payment(Decimal("400000"), Decimal("0.07"), 30)
        # Expected: ~$2,661.21
        assert pmt == Decimal("2661.21")

    def test_zero_rate(self):
        pmt = monthly_payment(Decimal("360000"), Decimal("0"), 30)
        assert pmt == Decimal("1000.00")

    def test_zero_principal(self):
        pmt = monthly_payment(Decimal("0"), Decimal("0.07"), 30)
        assert pmt == Decimal("0")


class TestAmortizationSchedule:
    def test_payment_count(self):
        schedule = amortization_schedule(Decimal("400000"), Decimal("0.07"), 30)
        assert len(schedule.payments) == 360

    def test_partial_schedule(self):
        schedule = amortization_schedule(
            Decimal("400000"), Decimal("0.07"), 30, hold_years=7
        )
        assert len(schedule.payments) == 84

    def test_first_payment_mostly_interest(self):
        schedule = amortization_schedule(Decimal("400000"), Decimal("0.07"), 30)
        first = schedule.payments[0]
        # At 7%, first month interest = 400000 * 0.07/12 = $2,333.33
        assert first.interest == Decimal("2333.33")
        assert first.principal == Decimal("327.88")

    def test_balance_decreases(self):
        schedule = amortization_schedule(Decimal("400000"), Decimal("0.07"), 30)
        for i in range(1, len(schedule.payments)):
            assert schedule.payments[i].balance < schedule.payments[i - 1].balance

    def test_final_balance_near_zero(self):
        schedule = amortization_schedule(Decimal("400000"), Decimal("0.07"), 30)
        assert schedule.payments[-1].balance <= Decimal("1.00")


class TestYearlyDebtSummary:
    def test_seven_year_summary(self):
        schedule = amortization_schedule(
            Decimal("400000"), Decimal("0.07"), 30, hold_years=7
        )
        yearly = yearly_debt_summary(schedule)
        assert len(yearly) == 7

    def test_yearly_totals_match(self):
        schedule = amortization_schedule(
            Decimal("400000"), Decimal("0.07"), 30, hold_years=7
        )
        yearly = yearly_debt_summary(schedule)
        total_interest = sum(y["interest"] for y in yearly)
        total_principal = sum(y["principal"] for y in yearly)
        assert total_interest == schedule.total_interest
        assert total_principal == schedule.total_principal

    def test_debt_service_equals_12_payments(self):
        schedule = amortization_schedule(
            Decimal("400000"), Decimal("0.07"), 30, hold_years=7
        )
        yearly = yearly_debt_summary(schedule)
        for y in yearly:
            assert y["debt_service"] == schedule.monthly_payment * 12
