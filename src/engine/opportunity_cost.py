"""Opportunity cost comparison: RE investment vs S&P 500.

Pure functions. No I/O (historical data passed in as arguments).
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import math

from src.models.results import EquityComparison

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")

# Default assumptions for S&P 500
DEFAULT_SP500_ANNUAL_RETURN = Decimal("0.10")  # ~10% nominal historical average
DEFAULT_SP500_VOLATILITY = Decimal("0.15")  # ~15% annual std dev
DEFAULT_RE_VOLATILITY = Decimal("0.06")  # ~5-8% annual std dev for residential RE
DEFAULT_RISK_FREE_RATE = Decimal("0.04")  # 10-year treasury proxy
LTCG_RATE = Decimal("0.20")
NIIT_RATE = Decimal("0.038")


def sp500_equity_curve(
    initial_investment: Decimal,
    hold_years: int,
    annual_return: Decimal = DEFAULT_SP500_ANNUAL_RETURN,
) -> list[Decimal]:
    """Year-end equity values for S&P 500 buy-and-hold.

    Returns list of length hold_years + 1 (year 0 = initial).
    """
    curve = [initial_investment]
    value = initial_investment
    for _ in range(hold_years):
        value = (value * (1 + annual_return)).quantize(TWO_PLACES, ROUND_HALF_UP)
        curve.append(value)
    return curve


def sp500_after_tax_proceeds(
    initial_investment: Decimal,
    final_value: Decimal,
    state_tax_rate: Decimal,
    niit_applies: bool = True,
) -> Decimal:
    """After-tax proceeds from selling S&P 500 position.

    Assumes all gains are LTCG.
    """
    gain = final_value - initial_investment
    if gain <= 0:
        return final_value

    federal_tax = (gain * LTCG_RATE).quantize(TWO_PLACES, ROUND_HALF_UP)
    niit = (gain * NIIT_RATE).quantize(TWO_PLACES, ROUND_HALF_UP) if niit_applies else Decimal("0")
    state_tax = (gain * state_tax_rate).quantize(TWO_PLACES, ROUND_HALF_UP)

    return final_value - federal_tax - niit - state_tax


def sharpe_ratio(
    annual_return: Decimal,
    volatility: Decimal,
    risk_free_rate: Decimal = DEFAULT_RISK_FREE_RATE,
) -> Decimal:
    """Sharpe ratio = (return - risk_free) / volatility."""
    if volatility == 0:
        return Decimal("0")
    return ((annual_return - risk_free_rate) / volatility).quantize(
        FOUR_PLACES, ROUND_HALF_UP
    )


def build_comparison(
    initial_equity: Decimal,
    re_yearly_equity: list[Decimal],
    re_after_tax_irr: Decimal,
    re_total_cash_returned: Decimal,
    hold_years: int,
    state_tax_rate: Decimal,
    niit_applies: bool = True,
    sp500_annual_return: Decimal = DEFAULT_SP500_ANNUAL_RETURN,
    sp500_volatility: Decimal = DEFAULT_SP500_VOLATILITY,
    re_volatility: Decimal = DEFAULT_RE_VOLATILITY,
    risk_free_rate: Decimal = DEFAULT_RISK_FREE_RATE,
) -> EquityComparison:
    """Build full RE vs S&P 500 comparison."""
    sp500_curve = sp500_equity_curve(initial_equity, hold_years, sp500_annual_return)
    sp500_final = sp500_curve[-1]
    sp500_after_tax = sp500_after_tax_proceeds(
        initial_equity, sp500_final, state_tax_rate, niit_applies
    )

    # S&P 500 after-tax IRR (simple CAGR approach for buy-and-hold)
    if initial_equity > 0 and hold_years > 0:
        ratio = float(sp500_after_tax / initial_equity)
        sp500_irr = Decimal(str(ratio ** (1 / hold_years) - 1)).quantize(
            FOUR_PLACES, ROUND_HALF_UP
        )
    else:
        sp500_irr = Decimal("0")

    re_total_return = (
        (re_total_cash_returned / initial_equity - 1) if initial_equity > 0 else Decimal("0")
    )
    sp500_total_return = (
        (sp500_after_tax / initial_equity - 1) if initial_equity > 0 else Decimal("0")
    )

    re_annualized = re_after_tax_irr
    sp500_annualized = sp500_irr

    return EquityComparison(
        re_initial_equity=initial_equity,
        sp500_initial_equity=initial_equity,
        re_yearly_equity=re_yearly_equity,
        sp500_yearly_equity=sp500_curve,
        re_after_tax_irr=re_after_tax_irr,
        sp500_after_tax_irr=sp500_irr,
        re_total_return=Decimal(str(re_total_return)).quantize(FOUR_PLACES, ROUND_HALF_UP),
        sp500_total_return=Decimal(str(sp500_total_return)).quantize(FOUR_PLACES, ROUND_HALF_UP),
        re_volatility=re_volatility,
        sp500_volatility=sp500_volatility,
        re_sharpe=sharpe_ratio(re_annualized, re_volatility, risk_free_rate),
        sp500_sharpe=sharpe_ratio(sp500_annualized, sp500_volatility, risk_free_rate),
    )
