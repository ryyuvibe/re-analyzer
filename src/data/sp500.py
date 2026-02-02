"""S&P 500 historical returns via yfinance."""

import logging
from decimal import Decimal
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

FALLBACK_CSV = Path(__file__).parent.parent.parent / "data" / "sp500_historical.csv"


async def get_sp500_annual_returns(years: int = 30) -> list[dict]:
    """Fetch S&P 500 annual returns.

    Tries yfinance first, falls back to bundled CSV.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker("^GSPC")
        end = date.today()
        start = end - timedelta(days=years * 365)
        hist = ticker.history(start=start.isoformat(), end=end.isoformat(), interval="1mo")

        if hist.empty:
            raise ValueError("No data from yfinance")

        # Compute annual returns from monthly close prices
        yearly = hist["Close"].resample("YE").last()
        returns = yearly.pct_change().dropna()

        return [
            {"year": idx.year, "return": Decimal(str(round(val, 4)))}
            for idx, val in returns.items()
        ]
    except Exception as e:
        logger.warning("yfinance failed, using fallback: %s", e)
        return _load_fallback()


def _load_fallback() -> list[dict]:
    """Load fallback S&P 500 data from CSV."""
    if not FALLBACK_CSV.exists():
        # Return reasonable defaults
        return [
            {"year": y, "return": Decimal("0.10")}
            for y in range(1994, 2025)
        ]

    import csv
    results = []
    with open(FALLBACK_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append({
                "year": int(row["year"]),
                "return": Decimal(row["return"]),
            })
    return results


async def get_average_annual_return(years: int = 30) -> Decimal:
    """Get average annual S&P 500 return over the specified period."""
    returns = await get_sp500_annual_returns(years)
    if not returns:
        return Decimal("0.10")
    avg = sum(r["return"] for r in returns) / len(returns)
    return avg.quantize(Decimal("0.0001"))
