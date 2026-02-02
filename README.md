# RE Analyzer

Real estate investment analysis engine. Takes a property address, resolves market data, and runs a full proforma with tax-aware returns.

## What it does

- **Property data resolution** — geocode an address, pull value/rent/tax estimates from RentCast and county assessor records
- **Cash flow projections** — gross rent, vacancy, operating expenses, NOI, debt service, CFBT/CFAT over a configurable hold period
- **Debt modeling** — full amortization schedule with yearly principal/interest breakdown
- **Depreciation** — 27.5-year residential straight-line + MACRS cost segregation (5/7/15-year classes with bonus depreciation)
- **Tax modeling** — passive activity rules (IRC 469), $25K rental loss exception, RE professional status, suspended loss tracking
- **Disposition analysis** — depreciation recapture (IRC 1250 at 25%), long-term capital gains, NIIT, state tax, suspended loss release
- **Rehab cost budgeting** — condition grade system (turnkey → full gut) with per-sqft cost tables, age multipliers, line item overrides, and rehab period modeling (year 1 rent pro-rated)
- **Return metrics** — IRR (before/after tax), equity multiple, cash-on-cash, cap rate, DSCR
- **Opportunity cost comparison** — side-by-side with S&P 500 after-tax returns

## Quick start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys (RENTCAST_API_KEY, CENSUS_API_KEY)

# Run API
uvicorn src.api.app:app --reload

# Run tests
pytest tests/engine/ -q
```

## API

Primary endpoint:

```
POST /api/v1/analyze
```

```json
{
  "address": "123 Main St, Columbus, OH 43201",
  "condition_grade": "medium",
  "rehab_months": 3
}
```

Returns full proforma: yearly projections, disposition analysis, rehab breakdown, and summary metrics (IRR, equity multiple, cash-on-cash, etc.).

## Project structure

```
src/
  engine/       Pure-function analysis modules (no I/O)
    cashflow.py, debt.py, depreciation.py, tax.py,
    disposition.py, irr.py, rehab.py, proforma.py
  models/       Frozen dataclasses
    assumptions.py, investor.py, rehab.py, results.py
  data/         External data resolution
    resolver.py, rentcast.py, geocode.py, county_assessor.py
  api/          FastAPI endpoints
  dashboard/    Plotly Dash UI
tests/
  engine/       93 unit/integration tests
```

## Tech stack

Python 3.11+ · FastAPI · Plotly Dash · SQLAlchemy · PostgreSQL · NumPy/SciPy
