"""Loan product models: conventional vs DSCR with rate derivation from FRED data."""

from decimal import Decimal

from src.models.smart_assumptions import LoanOption, MacroContext

DEFAULT_MORTGAGE_RATE = Decimal("0.07")  # Fallback if FRED unavailable
INVESTOR_PREMIUM = Decimal("0.0075")     # +75bps for investment property


def _base_rate(macro: MacroContext) -> Decimal:
    """Get base 30yr rate from FRED, or use fallback."""
    return macro.mortgage_rate_30y if macro.mortgage_rate_30y is not None else DEFAULT_MORTGAGE_RATE


def conventional_loan(
    macro: MacroContext,
    credit_score_tier: str = "excellent",
) -> LoanOption:
    """Build a conventional investment loan option.

    Rate = FRED MORTGAGE30US + investment premium + credit adjustment + LTV adjustment.

    Credit tiers:
        excellent (720+): +0bps
        good (680-719):   +25bps
        fair (660-679):   +75bps
    """
    base = _base_rate(macro)

    credit_spreads = {
        "excellent": Decimal("0"),
        "good": Decimal("0.0025"),
        "fair": Decimal("0.0075"),
    }
    credit_adj = credit_spreads.get(credit_score_tier, Decimal("0"))

    rate = base + INVESTOR_PREMIUM + credit_adj

    # Build justification
    base_pct = f"{float(base) * 100:.2f}%"
    inv_pct = f"{float(INVESTOR_PREMIUM) * 100:.0f}bps"
    credit_pct = f"{float(credit_adj) * 100:.0f}bps"
    rate_pct = f"{float(rate) * 100:.2f}%"

    source = (
        f"FRED 30yr primary rate ({base_pct}) + {inv_pct} investment property premium"
        f" + {credit_pct} {credit_score_tier} credit = {rate_pct}"
    )

    return LoanOption(
        loan_type="conventional",
        interest_rate=rate.quantize(Decimal("0.0001")),
        ltv=Decimal("0.80"),
        loan_term_years=30,
        points=Decimal("0"),
        rate_source=source,
    )


def dscr_loan(
    macro: MacroContext,
    estimated_dscr: Decimal,
) -> LoanOption:
    """Build a DSCR loan option.

    Rate = FRED MORTGAGE30US + investment premium + DSCR spread.

    DSCR coverage determines spread and max LTV:
        >= 1.25: +100bps, 80% LTV
        1.00-1.24: +175bps, 75% LTV
        < 1.00:  +250bps, 65% LTV
    """
    base = _base_rate(macro)

    if estimated_dscr >= Decimal("1.25"):
        dscr_spread = Decimal("0.01")
        ltv = Decimal("0.80")
        points = Decimal("1")
    elif estimated_dscr >= Decimal("1.0"):
        dscr_spread = Decimal("0.0175")
        ltv = Decimal("0.75")
        points = Decimal("1.5")
    else:
        dscr_spread = Decimal("0.025")
        ltv = Decimal("0.65")
        points = Decimal("2")

    rate = base + INVESTOR_PREMIUM + dscr_spread

    base_pct = f"{float(base) * 100:.2f}%"
    inv_pct = f"{float(INVESTOR_PREMIUM) * 100:.0f}bps"
    dscr_pct = f"{float(dscr_spread) * 100:.0f}bps"
    rate_pct = f"{float(rate) * 100:.2f}%"

    source = (
        f"FRED 30yr primary rate ({base_pct}) + {inv_pct} investment premium"
        f" + {dscr_pct} DSCR spread ({float(estimated_dscr):.2f}x coverage) = {rate_pct}"
    )

    return LoanOption(
        loan_type="dscr",
        interest_rate=rate.quantize(Decimal("0.0001")),
        ltv=ltv,
        loan_term_years=30,
        points=points,
        rate_source=source,
        min_dscr=Decimal("1.0"),
        prepayment_penalty="3-2-1 stepdown",
    )
