"""After-tax IRR computation using scipy.

Pure functions. No I/O.
"""

from decimal import Decimal, ROUND_HALF_UP

from scipy.optimize import brentq

FOUR_PLACES = Decimal("0.0001")


def compute_irr(cash_flows: list[Decimal]) -> Decimal:
    """Compute IRR from a vector of annual cash flows.

    cash_flows[0] should be negative (initial investment).
    cash_flows[-1] should include sale proceeds.

    Uses Brent's method on NPV function.
    """
    if not cash_flows or len(cash_flows) < 2:
        return Decimal("0")

    # Convert to float for scipy
    cf_float = [float(cf) for cf in cash_flows]

    def npv(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cf_float))

    # Find IRR using Brent's method
    # Search between -50% and 1000%
    try:
        irr = brentq(npv, -0.5, 10.0, xtol=1e-8, maxiter=1000)
        return Decimal(str(irr)).quantize(FOUR_PLACES, ROUND_HALF_UP)
    except ValueError:
        # No IRR found in range (e.g., all-negative cash flows)
        return Decimal("0")


def compute_equity_multiple(
    total_cash_returned: Decimal, total_cash_invested: Decimal
) -> Decimal:
    """Equity multiple = total cash out / total cash in."""
    if total_cash_invested == 0:
        return Decimal("0")
    return (total_cash_returned / total_cash_invested).quantize(FOUR_PLACES, ROUND_HALF_UP)
