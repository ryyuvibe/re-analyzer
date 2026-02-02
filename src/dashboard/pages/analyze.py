"""Main analysis page — manual entry + address lookup with Go/No-Go scorecard.

Features:
  - Assumption tooltips with confidence badges
  - Loan type selector (conventional / DSCR)
  - Override any assumption inline
  - Neighborhood intelligence panel with hazard data
"""

import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import plotly.graph_objects as go
import httpx
from decimal import Decimal

from src.engine.proforma import run_proforma
from src.engine.rehab import estimate_rehab_budget
from src.engine.insurance import estimate_annual_insurance
from src.engine.assumptions_builder import build_smart_assumptions
from src.models.assumptions import DealAssumptions
from src.models.property import PropertyDetail, Address
from src.models.investor import InvestorTaxProfile, FilingStatus
from src.models.rehab import ConditionGrade
from src.models.smart_assumptions import MacroContext, UserOverrides

dash.register_page(__name__, path="/", name="Analyze")

API_BASE = "http://localhost:8000"

# Go/No-Go thresholds for Ohio rental properties
SCORECARD_THRESHOLDS = {
    "after_tax_irr": {"green": 0.12, "yellow": 0.08},
    "cash_on_cash": {"green": 0.08, "yellow": 0.05},
    "dscr_yr1": {"green": 1.25, "yellow": 1.10},
    "equity_multiple": {"green": 2.0, "yellow": 1.5},
    "cap_rate_yr1": {"green": 0.07, "yellow": 0.05},
}

BTN_STYLE = {
    "padding": "0.75rem 2rem",
    "fontSize": "1rem",
    "backgroundColor": "#1a1a2e",
    "color": "white",
    "border": "none",
    "cursor": "pointer",
}

FIELD_STYLE = {"width": "100%", "padding": "0.5rem", "fontSize": "0.95rem"}

CONFIDENCE_COLORS = {
    "high": "#2ecc71",
    "medium": "#f39c12",
    "low": "#e94560",
}

CONFIDENCE_LABELS = {
    "high": "High",
    "medium": "Med",
    "low": "Low",
}

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def _field(label, component):
    return html.Div([
        html.Label(label, style={"fontSize": "0.85rem", "marginBottom": "0.25rem", "display": "block"}),
        component,
    ], style={"flex": "1", "minWidth": "140px"})


layout = html.Div([
    html.H2("Property Analysis"),

    # Mode toggle
    dcc.RadioItems(
        id="input-mode",
        options=[
            {"label": " Manual Entry", "value": "manual"},
            {"label": " Address Lookup", "value": "address"},
        ],
        value="manual",
        inline=True,
        style={"marginBottom": "1rem", "fontSize": "1rem"},
    ),

    # --- Manual Entry Section ---
    html.Div(id="manual-section", children=[
        html.Div([
            _field("Purchase Price ($)", dcc.Input(id="manual-price", type="number", placeholder="120000", style=FIELD_STYLE)),
            _field("Monthly Rent ($)", dcc.Input(id="manual-rent", type="number", placeholder="1100", style=FIELD_STYLE)),
            _field("Sqft", dcc.Input(id="manual-sqft", type="number", placeholder="1200", style=FIELD_STYLE)),
            _field("Year Built", dcc.Input(id="manual-year-built", type="number", placeholder="1955", style=FIELD_STYLE)),
        ], style={"display": "flex", "gap": "1rem", "marginBottom": "0.75rem"}),
        html.Div([
            _field("Annual Property Tax ($)", dcc.Input(id="manual-tax", type="number", placeholder="2400", style=FIELD_STYLE)),
            _field("Annual Insurance ($)", dcc.Input(id="manual-insurance", type="number", placeholder="1200", style=FIELD_STYLE)),
            _field("Bedrooms", dcc.Input(id="manual-beds", type="number", placeholder="3", style=FIELD_STYLE)),
            _field("Bathrooms", dcc.Input(id="manual-baths", type="number", placeholder="1.5", step=0.5, style=FIELD_STYLE)),
        ], style={"display": "flex", "gap": "1rem", "marginBottom": "0.75rem"}),
        html.Div([
            _field("Address (for display)", dcc.Input(id="manual-address", type="text", placeholder="123 Oak St, Columbus, OH 43215", style=FIELD_STYLE)),
            html.Div([
                html.Label("\u00a0", style={"fontSize": "0.85rem", "display": "block"}),
                html.Button("Analyze", id="manual-analyze-btn", n_clicks=0, style=BTN_STYLE),
            ], style={"flex": "0 0 auto"}),
        ], style={"display": "flex", "gap": "1rem", "alignItems": "end"}),
    ], style={"marginBottom": "1.5rem"}),

    # --- Address Lookup Section ---
    html.Div(id="address-section", children=[
        html.P("Enter any US address to get a complete investment analysis with smart assumptions."),
        html.Div([
            dcc.Input(
                id="address-input",
                type="text",
                placeholder="123 Main St, Columbus, OH 43215",
                style={"width": "40%", "padding": "0.75rem", "fontSize": "1rem"},
            ),
            dcc.Input(
                id="purchase-price-override",
                type="number",
                placeholder="Purchase price override ($)",
                style={"width": "20%", "padding": "0.75rem", "fontSize": "1rem"},
            ),
            html.Div([
                html.Label("Loan Type", style={"fontSize": "0.85rem"}),
                dcc.Dropdown(
                    id="loan-type-select",
                    options=[
                        {"label": "Conventional", "value": "conventional"},
                        {"label": "DSCR", "value": "dscr"},
                    ],
                    value="conventional",
                    clearable=False,
                    style={"width": "160px"},
                ),
            ]),
            html.Button("Analyze", id="analyze-btn", n_clicks=0, style=BTN_STYLE),
        ], style={"display": "flex", "gap": "0.5rem", "alignItems": "end"}),

        # Override fields (collapsible)
        html.Details([
            html.Summary("Override Assumptions", style={"cursor": "pointer", "fontWeight": "bold", "marginTop": "1rem"}),
            html.Div([
                html.Div([
                    _field("Interest Rate (%)", dcc.Input(id="ovr-rate", type="number", placeholder="auto", step=0.01, style=FIELD_STYLE)),
                    _field("LTV (%)", dcc.Input(id="ovr-ltv", type="number", placeholder="auto", step=1, style=FIELD_STYLE)),
                    _field("Monthly Rent ($)", dcc.Input(id="ovr-rent", type="number", placeholder="auto", style=FIELD_STYLE)),
                    _field("Vacancy (%)", dcc.Input(id="ovr-vacancy", type="number", placeholder="auto", step=0.5, style=FIELD_STYLE)),
                ], style={"display": "flex", "gap": "1rem", "marginBottom": "0.75rem"}),
                html.Div([
                    _field("Appreciation (%)", dcc.Input(id="ovr-appreciation", type="number", placeholder="auto", step=0.1, style=FIELD_STYLE)),
                    _field("Hold Years", dcc.Input(id="ovr-hold", type="number", placeholder="7", style=FIELD_STYLE)),
                    _field("Management (%)", dcc.Input(id="ovr-mgmt", type="number", placeholder="auto", step=0.5, style=FIELD_STYLE)),
                    _field("Maintenance (%)", dcc.Input(id="ovr-maint", type="number", placeholder="auto", step=0.5, style=FIELD_STYLE)),
                ], style={"display": "flex", "gap": "1rem"}),
            ], style={"marginTop": "0.75rem"}),
        ], style={"marginTop": "0.5rem"}),
    ], style={"display": "none", "marginBottom": "1.5rem"}),

    # --- Rehab Section (shared) ---
    html.Div([
        html.H4("Rehab", style={"marginBottom": "0.5rem"}),
        html.Div([
            html.Div([
                html.Label("Condition Grade"),
                dcc.Dropdown(
                    id="condition-grade",
                    options=[
                        {"label": "Turnkey (no rehab)", "value": "turnkey"},
                        {"label": "Light (~$6/sqft)", "value": "light"},
                        {"label": "Medium (~$21/sqft)", "value": "medium"},
                        {"label": "Heavy (~$43/sqft)", "value": "heavy"},
                        {"label": "Full Gut (~$65/sqft)", "value": "full_gut"},
                    ],
                    value="turnkey",
                    clearable=False,
                ),
            ], style={"width": "40%"}),
            html.Div([
                html.Label("Rehab Months (optional override)"),
                dcc.Input(id="rehab-months", type="number", placeholder="auto", style=FIELD_STYLE),
            ], style={"width": "20%"}),
        ], style={"display": "flex", "gap": "1rem"}),
    ], style={"marginBottom": "1.5rem"}),

    # Loading spinner
    dcc.Loading(
        id="loading",
        children=[html.Div(id="loading-output")],
        type="circle",
    ),

    # Investor Profile (collapsible)
    html.Details([
        html.Summary("Investor Profile", style={"cursor": "pointer", "fontWeight": "bold"}),
        html.Div([
            html.Div([
                html.Label("Filing Status"),
                dcc.Dropdown(
                    id="filing-status",
                    options=[
                        {"label": "Married Filing Jointly", "value": "married_filing_jointly"},
                        {"label": "Single", "value": "single"},
                        {"label": "Head of Household", "value": "head_of_household"},
                    ],
                    value="married_filing_jointly",
                ),
            ], style={"width": "30%"}),
            html.Div([
                html.Label("AGI ($)"),
                dcc.Input(id="agi-input", type="number", value=400000),
            ], style={"width": "20%"}),
            html.Div([
                html.Label("Federal Rate (%)"),
                dcc.Input(id="fed-rate", type="number", value=37, step=0.1),
            ], style={"width": "20%"}),
            html.Div([
                html.Label("State Rate (%)"),
                dcc.Input(id="state-rate", type="number", value=13.3, step=0.1),
            ], style={"width": "20%"}),
        ], style={"display": "flex", "gap": "1rem", "marginTop": "1rem"}),
    ], style={"marginBottom": "2rem"}),

    # Results Section
    html.Div(id="results-container"),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    [Output("address-section", "style"), Output("manual-section", "style")],
    Input("input-mode", "value"),
)
def toggle_input_mode(mode):
    if mode == "address":
        return {"display": "block", "marginBottom": "1.5rem"}, {"display": "none"}
    return {"display": "none"}, {"display": "block", "marginBottom": "1.5rem"}


@callback(
    [Output("results-container", "children"), Output("loading-output", "children")],
    [Input("analyze-btn", "n_clicks"), Input("manual-analyze-btn", "n_clicks")],
    [
        State("address-input", "value"),
        State("purchase-price-override", "value"),
        State("manual-price", "value"),
        State("manual-rent", "value"),
        State("manual-sqft", "value"),
        State("manual-year-built", "value"),
        State("manual-tax", "value"),
        State("manual-insurance", "value"),
        State("manual-beds", "value"),
        State("manual-baths", "value"),
        State("manual-address", "value"),
        State("condition-grade", "value"),
        State("rehab-months", "value"),
        State("filing-status", "value"),
        State("agi-input", "value"),
        State("fed-rate", "value"),
        State("state-rate", "value"),
        State("input-mode", "value"),
        State("loan-type-select", "value"),
        State("ovr-rate", "value"),
        State("ovr-ltv", "value"),
        State("ovr-rent", "value"),
        State("ovr-vacancy", "value"),
        State("ovr-appreciation", "value"),
        State("ovr-hold", "value"),
        State("ovr-mgmt", "value"),
        State("ovr-maint", "value"),
    ],
    prevent_initial_call=True,
)
def run_analysis(
    addr_clicks, manual_clicks,
    address, purchase_price_override,
    price, rent, sqft, year_built, prop_tax, insurance, beds, baths, manual_address,
    condition_grade, rehab_months,
    filing_status, agi, fed_rate, state_rate,
    input_mode, loan_type,
    ovr_rate, ovr_ltv, ovr_rent, ovr_vacancy,
    ovr_appreciation, ovr_hold, ovr_mgmt, ovr_maint,
):
    triggered = dash.ctx.triggered_id
    if triggered == "analyze-btn":
        return _run_address_mode(
            address, purchase_price_override, condition_grade, rehab_months,
            filing_status, agi, fed_rate, state_rate, loan_type,
            ovr_rate, ovr_ltv, ovr_rent, ovr_vacancy,
            ovr_appreciation, ovr_hold, ovr_mgmt, ovr_maint,
        )
    elif triggered == "manual-analyze-btn":
        return _run_manual_mode(
            price, rent, sqft, year_built, prop_tax, insurance, beds, baths, manual_address,
            condition_grade, rehab_months,
            filing_status, agi, fed_rate, state_rate,
        )
    return no_update, no_update


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------


def _run_address_mode(address, purchase_price_override, condition_grade, rehab_months,
                      filing_status, agi, fed_rate, state_rate, loan_type,
                      ovr_rate, ovr_ltv, ovr_rent, ovr_vacancy,
                      ovr_appreciation, ovr_hold, ovr_mgmt, ovr_maint):
    if not address:
        return no_update, no_update
    try:
        payload = {
            "address": address,
            "filing_status": filing_status,
            "agi": agi,
            "marginal_federal_rate": fed_rate / 100 if fed_rate else 0.37,
            "marginal_state_rate": state_rate / 100 if state_rate else 0.133,
        }
        if purchase_price_override:
            payload["purchase_price_override"] = float(purchase_price_override)
        if loan_type:
            payload["loan_type"] = loan_type
        if condition_grade and condition_grade != "turnkey":
            payload["condition_grade"] = condition_grade
        if rehab_months:
            payload["rehab_months"] = int(rehab_months)

        # Overrides
        if ovr_rate:
            payload["interest_rate"] = float(ovr_rate) / 100
        if ovr_ltv:
            payload["ltv"] = float(ovr_ltv) / 100
        if ovr_rent:
            payload["monthly_rent"] = float(ovr_rent)
        if ovr_vacancy:
            payload["vacancy_rate"] = float(ovr_vacancy) / 100
        if ovr_appreciation:
            payload["annual_appreciation"] = float(ovr_appreciation) / 100
        if ovr_hold:
            payload["hold_years"] = int(ovr_hold)
        if ovr_mgmt:
            payload["management_pct"] = float(ovr_mgmt) / 100
        if ovr_maint:
            payload["maintenance_pct"] = float(ovr_maint) / 100

        resp = httpx.post(f"{API_BASE}/api/v1/analyze", json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return html.Div(f"Error: {e}", style={"color": "red"}), ""

    children = [_build_scorecard(data), _build_results(data)]
    if data.get("assumption_manifest"):
        children.insert(1, _build_assumption_panel(data["assumption_manifest"]))
    if data.get("neighborhood"):
        children.append(_build_neighborhood_report(data["neighborhood"]))
    return html.Div(children), ""


def _run_manual_mode(price, rent, sqft, year_built, prop_tax, insurance,
                     beds, baths, manual_address,
                     condition_grade, rehab_months,
                     filing_status, agi, fed_rate, state_rate):
    if not price or not rent:
        return html.Div(
            "Purchase price and monthly rent are required.",
            style={"color": "red", "padding": "1rem"},
        ), ""

    try:
        sqft = int(sqft) if sqft else 1200
        year_built = int(year_built) if year_built else 1970

        grade = ConditionGrade(condition_grade or "turnkey")
        rehab_budget = estimate_rehab_budget(
            sqft=sqft,
            year_built=year_built,
            condition_grade=grade,
            rehab_months=int(rehab_months) if rehab_months else None,
        )

        # Auto-estimate insurance if not provided
        if insurance:
            insurance_val = Decimal(str(insurance))
        else:
            insurance_val = estimate_annual_insurance(
                property_value=Decimal(str(price)),
                sqft=sqft,
                year_built=year_built,
                state="OH",
            )

        assumptions = DealAssumptions(
            purchase_price=Decimal(str(price)),
            monthly_rent=Decimal(str(rent)),
            property_tax=Decimal(str(prop_tax or 0)),
            insurance=insurance_val,
            rehab_budget=rehab_budget,
        )

        investor = InvestorTaxProfile(
            filing_status=FilingStatus(filing_status or "married_filing_jointly"),
            agi=Decimal(str(agi or 400000)),
            marginal_federal_rate=Decimal(str((fed_rate or 37) / 100)),
            marginal_state_rate=Decimal(str((state_rate or 13.3) / 100)),
            state="OH",
        )

        result = run_proforma(assumptions, investor)
        data = _result_to_display_dict(
            result, manual_address, beds, baths, sqft, year_built, price, rent, prop_tax,
        )
    except Exception as e:
        return html.Div(f"Error: {e}", style={"color": "red", "padding": "1rem"}), ""

    return html.Div([_build_scorecard(data), _build_results(data)]), ""


# ---------------------------------------------------------------------------
# Engine result → display dict adapter
# ---------------------------------------------------------------------------


def _result_to_display_dict(result, address, beds, baths, sqft, year_built,
                            price, rent, prop_tax):
    return {
        "property": {
            "street": address or "Manual Entry",
            "city": "",
            "state": "OH",
            "zip_code": "",
            "bedrooms": int(beds) if beds else 0,
            "bathrooms": float(baths) if baths else 0,
            "sqft": int(sqft) if sqft else 0,
            "year_built": int(year_built) if year_built else 0,
            "estimated_value": float(price),
            "estimated_rent": float(rent),
            "annual_tax": float(prop_tax) if prop_tax else 0,
        },
        "total_initial_investment": float(result.total_initial_investment),
        "after_tax_irr": float(result.after_tax_irr),
        "before_tax_irr": float(result.before_tax_irr),
        "equity_multiple": float(result.equity_multiple),
        "average_cash_on_cash": float(result.average_cash_on_cash),
        "total_profit": float(result.total_profit),
        "net_tax_impact": float(result.net_tax_impact),
        "rehab_total_cost": float(result.rehab_total_cost),
        "rehab_months": result.rehab_months,
        "yearly_projections": [
            {
                "year": p.year,
                "gross_rent": float(p.gross_rent),
                "effective_gross_income": float(p.effective_gross_income),
                "total_expenses": float(p.total_expenses),
                "noi": float(p.noi),
                "debt_service": float(p.debt_service),
                "cash_flow_before_tax": float(p.cash_flow_before_tax),
                "cash_flow_after_tax": float(p.cash_flow_after_tax),
                "total_depreciation": float(p.total_depreciation),
                "taxable_income": float(p.taxable_income),
                "suspended_loss": float(p.suspended_loss),
                "tax_benefit": float(p.tax_benefit),
                "property_value": float(p.property_value),
                "equity": float(p.equity),
                "cap_rate": float(p.cap_rate),
                "cash_on_cash": float(p.cash_on_cash),
                "dscr": float(p.dscr),
                "rent_months": p.rent_months,
            }
            for p in result.yearly_projections
        ],
        "disposition": {
            "sale_price": float(result.disposition.sale_price),
            "selling_costs": float(result.disposition.selling_costs),
            "net_sale_proceeds": float(result.disposition.net_sale_proceeds),
            "total_gain": float(result.disposition.total_gain),
            "depreciation_recapture": float(result.disposition.depreciation_recapture),
            "capital_gain": float(result.disposition.capital_gain),
            "recapture_tax": float(result.disposition.recapture_tax),
            "capital_gains_tax": float(result.disposition.capital_gains_tax),
            "niit_on_gain": float(result.disposition.niit_on_gain),
            "state_tax_on_gain": float(result.disposition.state_tax_on_gain),
            "suspended_losses_released": float(result.disposition.suspended_losses_released),
            "tax_benefit_from_release": float(result.disposition.tax_benefit_from_release),
            "total_tax_on_sale": float(result.disposition.total_tax_on_sale),
            "after_tax_sale_proceeds": float(result.disposition.after_tax_sale_proceeds),
        },
    }


# ---------------------------------------------------------------------------
# Assumption Panel with Tooltips and Confidence Badges
# ---------------------------------------------------------------------------


def _confidence_badge(confidence):
    """Render a small colored badge showing confidence level."""
    color = CONFIDENCE_COLORS.get(confidence, "#999")
    label = CONFIDENCE_LABELS.get(confidence, "?")
    return html.Span(label, style={
        "backgroundColor": color,
        "color": "white",
        "fontSize": "0.7rem",
        "fontWeight": "bold",
        "padding": "2px 6px",
        "borderRadius": "4px",
        "marginLeft": "0.5rem",
        "verticalAlign": "middle",
    })


def _assumption_row(field_name, detail):
    """Render a single assumption row with value, source, and tooltip."""
    value = float(detail.get("value", 0))
    source = detail.get("source", "default")
    confidence = detail.get("confidence", "low")
    justification = detail.get("justification", "")

    # Format value based on field type
    if "pct" in field_name or field_name in ("ltv", "interest_rate", "vacancy_rate",
                                              "annual_rent_growth", "annual_appreciation",
                                              "annual_expense_growth", "selling_costs_pct"):
        display_val = f"{value * 100:.2f}%"
    elif field_name in ("purchase_price", "monthly_rent", "property_tax", "insurance",
                        "hoa", "closing_costs"):
        display_val = f"${value:,.0f}"
    elif field_name in ("hold_years", "loan_term_years"):
        display_val = f"{int(value)} yr"
    else:
        display_val = str(value)

    # Nice field label
    label = field_name.replace("_", " ").title()

    # Source icon
    source_icon = {"api_fetched": "API", "estimated": "Est", "user_override": "User", "default": "Def"}
    source_label = source_icon.get(source, "?")

    return html.Div([
        html.Div([
            html.Span(label, style={"fontWeight": "bold", "fontSize": "0.85rem"}),
            _confidence_badge(confidence),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div([
            html.Span(display_val, style={"fontSize": "1rem", "fontWeight": "bold"}),
            html.Span(f" ({source_label})", style={"fontSize": "0.75rem", "color": "#888"}),
        ]),
        html.Div(justification, style={
            "fontSize": "0.75rem", "color": "#666", "lineHeight": "1.3",
            "marginTop": "2px",
        }),
    ], style={
        "padding": "0.5rem 0.75rem",
        "borderBottom": "1px solid #eee",
    }, title=justification)


def _build_assumption_panel(manifest_data):
    """Build the assumption manifest panel with tooltips and confidence badges."""
    if not manifest_data:
        return html.Div()

    details = manifest_data.get("details", {})

    # Group assumptions
    key_fields = [
        "purchase_price", "monthly_rent", "interest_rate", "ltv",
        "vacancy_rate", "property_tax", "insurance", "maintenance_pct",
        "management_pct", "annual_appreciation", "annual_rent_growth",
        "annual_expense_growth", "closing_costs", "hold_years",
        "selling_costs_pct", "capex_reserve_pct", "hoa", "land_value_pct",
    ]

    rows = []
    for field in key_fields:
        if field in details:
            rows.append(_assumption_row(field, details[field]))

    return html.Div([
        html.H3("Smart Assumptions", style={"marginBottom": "0.5rem"}),
        html.P("Each assumption is estimated from data. Hover for details.",
               style={"fontSize": "0.85rem", "color": "#666", "marginBottom": "0.75rem"}),
        html.Div(rows, style={
            "display": "grid",
            "gridTemplateColumns": "1fr 1fr 1fr",
            "gap": "0",
            "backgroundColor": "white",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "overflow": "hidden",
        }),
    ], style={"marginBottom": "2rem"})


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------


def _traffic_color(value, thresholds):
    if value >= thresholds["green"]:
        return "#2ecc71"
    elif value >= thresholds["yellow"]:
        return "#f39c12"
    return "#e94560"


def _scorecard_metric(label, display_value, color):
    return html.Div([
        html.Div(style={
            "height": "4px", "backgroundColor": color,
            "borderRadius": "2px 2px 0 0",
        }),
        html.Div([
            html.Div(display_value, style={"fontSize": "1.3rem", "fontWeight": "bold"}),
            html.Div(label, style={"fontSize": "0.8rem", "color": "#666"}),
        ], style={"padding": "0.75rem 1rem", "textAlign": "center"}),
    ], style={
        "backgroundColor": "white", "border": "1px solid #ddd",
        "borderRadius": "8px", "minWidth": "140px", "overflow": "hidden",
    })


def _build_scorecard(data):
    irr = float(data["after_tax_irr"])
    coc = float(data["average_cash_on_cash"])
    projections = data["yearly_projections"]
    dscr_yr1 = float(projections[0]["dscr"]) if projections else 0
    cap_yr1 = float(projections[0]["cap_rate"]) if projections else 0
    eq_mult = float(data["equity_multiple"])

    metrics = [
        ("After-Tax IRR", irr, f"{irr * 100:.1f}%", SCORECARD_THRESHOLDS["after_tax_irr"]),
        ("Avg Cash-on-Cash", coc, f"{coc * 100:.1f}%", SCORECARD_THRESHOLDS["cash_on_cash"]),
        ("Year-1 DSCR", dscr_yr1, f"{dscr_yr1:.2f}", SCORECARD_THRESHOLDS["dscr_yr1"]),
        ("Equity Multiple", eq_mult, f"{eq_mult:.2f}x", SCORECARD_THRESHOLDS["equity_multiple"]),
        ("Year-1 Cap Rate", cap_yr1, f"{cap_yr1 * 100:.1f}%", SCORECARD_THRESHOLDS["cap_rate_yr1"]),
    ]

    colors = [_traffic_color(val, thresh) for _, val, _, thresh in metrics]
    red_count = colors.count("#e94560")
    green_count = colors.count("#2ecc71")

    if red_count >= 2:
        verdict, verdict_color = "PASS", "#e94560"
        verdict_text = "Too many metrics below threshold. Likely not worth pursuing."
    elif red_count == 0 and green_count >= 3:
        verdict, verdict_color = "GO", "#2ecc71"
        verdict_text = "Strong deal. Meets or exceeds targets on key metrics."
    else:
        verdict, verdict_color = "DIG DEEPER", "#f39c12"
        verdict_text = "Mixed signals. Worth a closer look before committing."

    # Loan type indicator
    loan_type = data.get("loan_type")
    loan_badge = None
    if loan_type:
        loan_badge = html.Span(loan_type.upper(), style={
            "backgroundColor": "#1a1a2e", "color": "white",
            "padding": "4px 10px", "borderRadius": "4px",
            "fontSize": "0.8rem", "fontWeight": "bold",
            "marginLeft": "1rem",
        })

    verdict_banner = html.Div([
        html.Div([
            html.Span(verdict, style={
                "fontSize": "2rem", "fontWeight": "bold", "color": verdict_color,
            }),
            loan_badge,
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
        html.Div(verdict_text, style={"fontSize": "0.95rem", "color": "#666"}),
    ], style={
        "textAlign": "center", "padding": "1rem",
        "border": f"3px solid {verdict_color}", "borderRadius": "12px",
        "marginBottom": "1rem",
    })

    metric_cards = html.Div([
        _scorecard_metric(label, display, _traffic_color(val, thresh))
        for label, val, display, thresh in metrics
    ], style={"display": "flex", "gap": "0.75rem", "flexWrap": "wrap", "marginBottom": "2rem"})

    return html.Div([verdict_banner, metric_cards])


# ---------------------------------------------------------------------------
# Detailed results
# ---------------------------------------------------------------------------


def _build_results(data):
    prop = data["property"]
    projections = data["yearly_projections"]
    disposition = data["disposition"]

    years = [p["year"] for p in projections]

    # Summary cards
    summary = html.Div([
        _metric_card("After-Tax IRR", f"{float(data['after_tax_irr']) * 100:.1f}%"),
        _metric_card("Equity Multiple", f"{float(data['equity_multiple']):.2f}x"),
        _metric_card("Avg Cash-on-Cash", f"{float(data['average_cash_on_cash']) * 100:.1f}%"),
        _metric_card("Total Profit", f"${float(data['total_profit']):,.0f}"),
        _metric_card("Net Tax Impact", f"${float(data['net_tax_impact']):,.0f}"),
    ], style={"display": "flex", "gap": "1rem", "marginBottom": "2rem", "flexWrap": "wrap"})

    # Property summary
    addr_parts = [prop.get("street", "")]
    if prop.get("city"):
        addr_parts.append(prop["city"])
    state_zip = " ".join(filter(None, [prop.get("state", ""), prop.get("zip_code", "")]))
    if state_zip:
        addr_parts.append(state_zip)
    addr_str = ", ".join(filter(None, addr_parts))

    detail_parts = []
    if prop.get("bedrooms"):
        detail_parts.append(f"{prop['bedrooms']}bd")
    if prop.get("bathrooms"):
        detail_parts.append(f"{prop['bathrooms']}ba")
    if prop.get("sqft"):
        detail_parts.append(f"{prop['sqft']:,} sqft")
    if prop.get("year_built"):
        detail_parts.append(f"Built {prop['year_built']}")

    prop_card = html.Div([
        html.H3(addr_str or "Property"),
        html.P(" · ".join(detail_parts)) if detail_parts else None,
        html.P(f"Value: ${float(prop.get('estimated_value', 0)):,.0f} · Rent: ${float(prop.get('estimated_rent', 0)):,.0f}/mo"),
    ], style={"backgroundColor": "#f5f5f5", "padding": "1rem", "borderRadius": "8px", "marginBottom": "2rem"})

    # Rehab info
    rehab_info = None
    rehab_cost = float(data.get("rehab_total_cost", 0))
    rehab_mo = data.get("rehab_months", 0)
    if rehab_cost > 0 or rehab_mo > 0:
        rehab_info = html.Div([
            html.P(f"Rehab Cost: ${rehab_cost:,.0f} · Rehab Period: {rehab_mo} months · Year 1 Rent: {12 - rehab_mo} months",
                   style={"fontWeight": "bold"}),
        ], style={
            "backgroundColor": "#fff3cd", "padding": "0.75rem 1rem",
            "borderRadius": "8px", "marginBottom": "1.5rem", "border": "1px solid #ffc107",
        })

    # Cash flow chart
    cf_fig = go.Figure()
    cf_fig.add_trace(go.Bar(
        x=years,
        y=[float(p["cash_flow_before_tax"]) for p in projections],
        name="Before Tax",
        marker_color="#1a1a2e",
    ))
    cf_fig.add_trace(go.Bar(
        x=years,
        y=[float(p["cash_flow_after_tax"]) for p in projections],
        name="After Tax",
        marker_color="#e94560",
    ))
    cf_fig.update_layout(title="Annual Cash Flow", barmode="group", xaxis_title="Year", yaxis_title="$")

    # Equity build chart
    equity_fig = go.Figure()
    equity_fig.add_trace(go.Scatter(
        x=years,
        y=[float(p["equity"]) for p in projections],
        mode="lines+markers",
        name="Equity",
        line=dict(color="#1a1a2e", width=3),
    ))
    equity_fig.add_trace(go.Scatter(
        x=years,
        y=[float(p["property_value"]) for p in projections],
        mode="lines+markers",
        name="Property Value",
        line=dict(color="#16213e", width=2, dash="dash"),
    ))
    equity_fig.update_layout(title="Equity Growth", xaxis_title="Year", yaxis_title="$")

    # Pro forma table
    table_header = html.Tr([
        html.Th("Year"), html.Th("Gross Rent"), html.Th("NOI"),
        html.Th("Debt Service"), html.Th("CFBT"), html.Th("CFAT"),
        html.Th("Cap Rate"), html.Th("CoC"), html.Th("DSCR"),
    ])
    table_rows = [
        html.Tr([
            html.Td(p["year"]),
            html.Td(f"${float(p['gross_rent']):,.0f}"),
            html.Td(f"${float(p['noi']):,.0f}"),
            html.Td(f"${float(p['debt_service']):,.0f}"),
            html.Td(f"${float(p['cash_flow_before_tax']):,.0f}"),
            html.Td(f"${float(p['cash_flow_after_tax']):,.0f}"),
            html.Td(f"{float(p['cap_rate']) * 100:.1f}%"),
            html.Td(f"{float(p['cash_on_cash']) * 100:.1f}%"),
            html.Td(f"{float(p['dscr']):.2f}"),
        ])
        for p in projections
    ]
    table = html.Table(
        [html.Thead(table_header), html.Tbody(table_rows)],
        style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.9rem"},
    )

    children = [
        summary,
        prop_card,
    ]
    if rehab_info:
        children.append(rehab_info)
    children.extend([
        html.Div([
            dcc.Graph(figure=cf_fig, style={"width": "50%"}),
            dcc.Graph(figure=equity_fig, style={"width": "50%"}),
        ], style={"display": "flex", "gap": "1rem"}),
        html.H3("Pro Forma", style={"marginTop": "2rem"}),
        table,
        html.H3("Disposition (Sale)", style={"marginTop": "2rem"}),
        html.Div([
            html.P(f"Sale Price: ${float(disposition['sale_price']):,.0f}"),
            html.P(f"Total Gain: ${float(disposition['total_gain']):,.0f}"),
            html.P(f"Depreciation Recapture Tax: ${float(disposition['recapture_tax']):,.0f}"),
            html.P(f"Capital Gains Tax: ${float(disposition['capital_gains_tax']):,.0f}"),
            html.P(f"Suspended Losses Released: ${float(disposition['suspended_losses_released']):,.0f}"),
            html.P(f"Tax Benefit from Release: ${float(disposition['tax_benefit_from_release']):,.0f}"),
            html.P(f"After-Tax Proceeds: ${float(disposition['after_tax_sale_proceeds']):,.0f}",
                   style={"fontWeight": "bold"}),
        ], style={"backgroundColor": "#f5f5f5", "padding": "1rem", "borderRadius": "8px"}),
    ])

    return html.Div(children)


def _metric_card(label, value):
    return html.Div([
        html.Div(value, style={"fontSize": "1.5rem", "fontWeight": "bold"}),
        html.Div(label, style={"fontSize": "0.85rem", "color": "#666"}),
    ], style={
        "backgroundColor": "white",
        "border": "1px solid #ddd",
        "borderRadius": "8px",
        "padding": "1rem 1.5rem",
        "minWidth": "150px",
        "textAlign": "center",
    })


# ---------------------------------------------------------------------------
# Neighborhood Report
# ---------------------------------------------------------------------------

GRADE_COLORS = {
    "A": "#2ecc71",
    "B": "#27ae60",
    "C": "#f39c12",
    "D": "#e67e22",
    "F": "#e94560",
}


def _score_bar(label, value, max_val=100):
    """Render a horizontal score bar."""
    if value is None:
        return html.Div([
            html.Span(label, style={"fontSize": "0.85rem", "color": "#666", "width": "100px", "display": "inline-block"}),
            html.Span("N/A", style={"fontSize": "0.85rem", "color": "#999"}),
        ], style={"marginBottom": "0.5rem"})
    pct = min(float(value) / max_val * 100, 100)
    color = "#2ecc71" if pct >= 70 else "#f39c12" if pct >= 40 else "#e94560"
    return html.Div([
        html.Span(label, style={"fontSize": "0.85rem", "color": "#666", "width": "100px", "display": "inline-block"}),
        html.Div(
            html.Div(style={"width": f"{pct}%", "height": "100%", "backgroundColor": color, "borderRadius": "4px"}),
            style={"flex": "1", "height": "12px", "backgroundColor": "#eee", "borderRadius": "4px", "display": "inline-block", "width": "60%", "verticalAlign": "middle"},
        ),
        html.Span(f" {int(value)}", style={"fontSize": "0.85rem", "fontWeight": "bold", "marginLeft": "0.5rem"}),
    ], style={"display": "flex", "alignItems": "center", "marginBottom": "0.5rem"})


def _hazard_item(label, value, risk_level="low"):
    """Render a single hazard data point."""
    if value is None:
        return None
    colors = {"low": "#2ecc71", "moderate": "#f39c12", "high": "#e94560"}
    color = colors.get(risk_level, "#999")
    return html.Div([
        html.Span(label, style={"fontSize": "0.85rem", "color": "#666", "width": "140px", "display": "inline-block"}),
        html.Span(str(value), style={
            "fontSize": "0.85rem", "fontWeight": "bold", "color": color,
        }),
    ], style={"marginBottom": "0.3rem"})


def _build_neighborhood_report(neighborhood):
    """Build the neighborhood intelligence panel from API response data."""
    grade = neighborhood.get("grade", "C")
    grade_score = float(neighborhood.get("grade_score", 0))
    grade_color = GRADE_COLORS.get(grade, "#999")

    # Grade badge
    badge = html.Div([
        html.Div(grade, style={
            "fontSize": "2.5rem", "fontWeight": "bold", "color": "white",
            "backgroundColor": grade_color, "width": "70px", "height": "70px",
            "borderRadius": "12px", "display": "flex", "alignItems": "center",
            "justifyContent": "center",
        }),
        html.Div([
            html.Div("Neighborhood Grade", style={"fontSize": "0.85rem", "color": "#666"}),
            html.Div(f"Score: {grade_score:.0f}/100", style={"fontSize": "1rem", "fontWeight": "bold"}),
        ], style={"marginLeft": "1rem"}),
    ], style={"display": "flex", "alignItems": "center", "marginBottom": "1.5rem"})

    sections = [badge]

    # Demographics
    demo = neighborhood.get("demographics")
    if demo:
        demo_items = []
        if demo.get("median_household_income") is not None:
            demo_items.append(html.P(f"Median Household Income: ${demo['median_household_income']:,}"))
        if demo.get("median_home_value") is not None:
            demo_items.append(html.P(f"Median Home Value: ${demo['median_home_value']:,}"))
        if demo.get("poverty_rate") is not None:
            demo_items.append(html.P(f"Poverty Rate: {float(demo['poverty_rate']) * 100:.1f}%"))
        if demo.get("renter_pct") is not None:
            demo_items.append(html.P(f"Renter Percentage: {float(demo['renter_pct']) * 100:.1f}%"))
        if demo.get("population") is not None:
            demo_items.append(html.P(f"Tract Population: {demo['population']:,}"))
        if demo_items:
            sections.append(html.Div([
                html.H4("Demographics", style={"marginBottom": "0.5rem"}),
                html.Div(demo_items),
            ], style={"marginBottom": "1rem"}))

    # Walk / Transit / Bike scores
    ws = neighborhood.get("walk_score")
    if ws:
        sections.append(html.Div([
            html.H4("Walkability", style={"marginBottom": "0.5rem"}),
            _score_bar("Walk", ws.get("walk_score")),
            _score_bar("Transit", ws.get("transit_score")),
            _score_bar("Bike", ws.get("bike_score")),
        ], style={"marginBottom": "1rem"}))

    # Hazard / Risk data
    hazard_items = []
    flood = neighborhood.get("flood_zone")
    if flood:
        risk = "high" if flood in ("V", "VE", "A", "AE") else "moderate" if flood == "X500" else "low"
        hazard_items.append(_hazard_item("Flood Zone", flood, risk))

    seismic = neighborhood.get("seismic_pga")
    if seismic is not None:
        pga = float(seismic)
        risk = "high" if pga >= 0.4 else "moderate" if pga >= 0.2 else "low"
        hazard_items.append(_hazard_item("Seismic PGA", f"{pga:.2f}g", risk))

    wildfire = neighborhood.get("wildfire_risk")
    if wildfire is not None:
        risk = "high" if wildfire >= 4 else "moderate" if wildfire >= 3 else "low"
        hazard_items.append(_hazard_item("Wildfire Risk", f"Class {wildfire}/5", risk))

    hurricane = neighborhood.get("hurricane_zone")
    if hurricane is not None and hurricane > 0:
        risk = "high" if hurricane >= 3 else "moderate"
        hazard_items.append(_hazard_item("Hurricane Zone", f"Cat {hurricane}", risk))

    hail = neighborhood.get("hail_frequency")
    if hail and hail != "low":
        risk = "high" if hail == "high" else "moderate"
        hazard_items.append(_hazard_item("Hail Frequency", hail.title(), risk))

    crime = neighborhood.get("crime_rate")
    if crime is not None:
        rate = float(crime)
        risk = "high" if rate > 3000 else "moderate" if rate > 2000 else "low"
        hazard_items.append(_hazard_item("Property Crime", f"{rate:,.0f}/100K", risk))

    climate = neighborhood.get("climate_zone")
    if climate:
        hazard_items.append(_hazard_item("Climate Zone", climate.replace("_", " ").title(), "low"))

    noise = neighborhood.get("traffic_noise_score")
    if noise is not None and noise > 0:
        risk = "high" if noise >= 7 else "moderate" if noise >= 4 else "low"
        hazard_items.append(_hazard_item("Traffic/Noise", f"{noise}/10", risk))

    hazard_items = [h for h in hazard_items if h is not None]
    if hazard_items:
        sections.append(html.Div([
            html.H4("Risk & Environment", style={"marginBottom": "0.5rem"}),
            html.Div(hazard_items),
        ], style={"marginBottom": "1rem"}))

    # Schools
    schools = neighborhood.get("schools", [])
    if schools:
        avg = neighborhood.get("avg_school_rating")
        avg_text = f" (avg {float(avg):.1f}/10)" if avg else ""
        school_rows = [
            html.Tr([
                html.Td(s["name"]),
                html.Td(s["level"].title()),
                html.Td(f"{s['rating']}/10", style={"fontWeight": "bold"}),
                html.Td(f"{float(s['distance_miles']):.1f} mi"),
            ])
            for s in schools[:8]
        ]
        sections.append(html.Div([
            html.H4(f"Nearby Schools{avg_text}", style={"marginBottom": "0.5rem"}),
            html.Table([
                html.Thead(html.Tr([html.Th("School"), html.Th("Level"), html.Th("Rating"), html.Th("Distance")])),
                html.Tbody(school_rows),
            ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.9rem"}),
        ], style={"marginBottom": "1rem"}))

    # AI narrative
    narrative = neighborhood.get("ai_narrative")
    if narrative:
        sections.append(html.Div([
            html.H4("Investment Assessment", style={"marginBottom": "0.5rem"}),
            html.P(narrative, style={"lineHeight": "1.6", "color": "#333"}),
        ], style={"marginBottom": "1rem"}))

    return html.Div(
        [html.H3("Neighborhood Intelligence", style={"marginBottom": "1rem"})] + sections,
        style={
            "backgroundColor": "#f8f9fa", "padding": "1.5rem",
            "borderRadius": "12px", "marginTop": "2rem",
            "border": "1px solid #dee2e6",
        },
    )
