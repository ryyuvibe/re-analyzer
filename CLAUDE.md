# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RE Analyzer — a real estate investment analysis engine. Takes a property address, resolves data (value, rent, taxes), and runs a full proforma: cash flow projections, debt service, depreciation (with cost segregation), passive activity / tax modeling, disposition analysis, IRR, and equity multiple. Includes rehab cost budgeting with condition grades.

GitHub: https://github.com/ryyuvibe/re-analyzer

## Running the App

```bash
uvicorn src.api.app:app --reload
```

Requires Python 3.11+. Install dependencies:

```bash
pip install -e ".[dev]"
```

Environment variables go in `.env` (see `.env.example`). Key vars: `RENTCAST_API_KEY`, `CENSUS_API_KEY`, `DATABASE_URL`.

## Running Tests

```bash
pytest tests/engine/ -q
```

93 engine tests covering cash flow, debt, depreciation, disposition, IRR, opportunity cost, proforma, rehab, and tax modules. Test fixtures are in `tests/conftest.py` (canonical $500K property, high-income CA investor).

## Architecture

Python, FastAPI, no frontend build step. Pure-function engine with frozen dataclasses.

### Engine (`src/engine/`)
All pure functions — Decimal in, Decimal out. No I/O.

- **`cashflow.py`** — Gross rent, EGI, operating expenses, NOI, CFBT, cap rate, CoC, DSCR
- **`debt.py`** — Amortization schedule, yearly debt summary
- **`depreciation.py`** — 27.5-year residential + MACRS cost segregation (5/7/15-year classes, bonus depreciation)
- **`tax.py`** — Taxable rental income, passive activity rules (IRC 469), $25K rental loss exception
- **`disposition.py`** — Sale analysis: depreciation recapture (IRC 1250), capital gains, NIIT, suspended loss release
- **`irr.py`** — IRR via scipy, equity multiple
- **`rehab.py`** — Rehab cost estimator: per-sqft cost tables by condition grade, age multiplier, line item + total overrides
- **`opportunity_cost.py`** — S&P 500 comparison with after-tax returns
- **`proforma.py`** — Orchestrator: composes all sub-modules into `AnalysisResult`

### Models (`src/models/`)
Frozen dataclasses. Key types:

- **`DealAssumptions`** — All deal inputs (purchase, financing, income, expenses, depreciation, rehab)
- **`InvestorTaxProfile`** — Filing status, AGI, rates, RE professional status
- **`RehabBudget`** — Condition grade, line items with override support, rehab months
- **`AnalysisResult`** — Yearly projections, disposition, summary metrics

### Data (`src/data/`)
External data resolution — geocoding, RentCast API, county assessor tax estimates, FRED macro data, S&P 500 via yfinance.

- **`resolver.py`** — Orchestrates: raw address → geocode → property data → rent estimate → tax estimate

### API (`src/api/`)
FastAPI with 5 routers: analysis, properties, investor, market, comparison.

- **Primary endpoint**: `POST /api/v1/analyze` — address string → full proforma result
- Schemas in `src/api/schemas.py` (Pydantic v2)

### Dashboard (`src/dashboard/`)
Plotly Dash app (separate from FastAPI). Pages: analyze, compare, tax_alpha.

## Key Concepts

- **Condition grades**: `TURNKEY`, `LIGHT`, `MEDIUM`, `HEAVY`, `FULL_GUT` — drive rehab cost estimates and rehab period duration
- **Rehab period**: During rehab months, no rental income (year 1 pro-rated), but fixed costs (tax, insurance, debt) continue
- **Passive activity rules**: High-income investors get losses suspended; RE professionals can deduct fully
- **Cost segregation**: Reclassifies building components to shorter MACRS lives for accelerated depreciation
- **Disposition**: Models depreciation recapture at 25%, LTCG, NIIT, state tax, and suspended loss release on sale
