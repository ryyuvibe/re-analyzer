"""Amortization schedule computation.

Pure functions: Decimal in, dataclass out. No I/O.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class AmortizationPayment:
    period: int
    payment: Decimal
    principal: Decimal
    interest: Decimal
    balance: Decimal


@dataclass(frozen=True)
class AmortizationSchedule:
    payments: list[AmortizationPayment]
    monthly_payment: Decimal
    total_interest: Decimal
    total_principal: Decimal


def monthly_payment(principal: Decimal, annual_rate: Decimal, term_years: int) -> Decimal:
    """Calculate fixed monthly mortgage payment."""
    if principal <= 0:
        return Decimal("0")
    if annual_rate <= 0:
        return (principal / (term_years * 12)).quantize(TWO_PLACES, ROUND_HALF_UP)

    r = annual_rate / 12
    n = term_years * 12
    # M = P * [r(1+r)^n] / [(1+r)^n - 1]
    factor = (1 + r) ** n
    payment = principal * (r * factor) / (factor - 1)
    return payment.quantize(TWO_PLACES, ROUND_HALF_UP)


def amortization_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    term_years: int,
    hold_years: int | None = None,
) -> AmortizationSchedule:
    """Generate full or partial amortization schedule.

    Args:
        principal: Loan amount
        annual_rate: Annual interest rate (e.g. 0.07 for 7%)
        term_years: Loan term in years
        hold_years: If provided, only generate schedule for this many years
    """
    pmt = monthly_payment(principal, annual_rate, term_years)
    r = annual_rate / 12
    n_periods = (hold_years or term_years) * 12

    payments: list[AmortizationPayment] = []
    balance = principal
    total_interest = Decimal("0")
    total_principal = Decimal("0")

    for period in range(1, n_periods + 1):
        interest = (balance * r).quantize(TWO_PLACES, ROUND_HALF_UP)
        principal_paid = pmt - interest

        # Final payment adjustment
        if principal_paid > balance:
            principal_paid = balance
            actual_payment = interest + principal_paid
        else:
            actual_payment = pmt

        balance -= principal_paid
        total_interest += interest
        total_principal += principal_paid

        payments.append(AmortizationPayment(
            period=period,
            payment=actual_payment,
            principal=principal_paid,
            interest=interest,
            balance=balance.quantize(TWO_PLACES, ROUND_HALF_UP),
        ))

    return AmortizationSchedule(
        payments=payments,
        monthly_payment=pmt,
        total_interest=total_interest,
        total_principal=total_principal,
    )


def yearly_debt_summary(schedule: AmortizationSchedule) -> list[dict[str, Decimal]]:
    """Aggregate amortization schedule by year.

    Returns list of dicts with keys: year, principal, interest, debt_service, ending_balance
    """
    yearly: list[dict[str, Decimal]] = []
    year_principal = Decimal("0")
    year_interest = Decimal("0")
    year_debt_service = Decimal("0")

    for p in schedule.payments:
        year_principal += p.principal
        year_interest += p.interest
        year_debt_service += p.payment

        if p.period % 12 == 0 or p.period == len(schedule.payments):
            year_num = (p.period - 1) // 12 + 1
            yearly.append({
                "year": Decimal(str(year_num)),
                "principal": year_principal,
                "interest": year_interest,
                "debt_service": year_debt_service,
                "ending_balance": p.balance,
            })
            year_principal = Decimal("0")
            year_interest = Decimal("0")
            year_debt_service = Decimal("0")

    return yearly
