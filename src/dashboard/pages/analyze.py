"""Main analysis page — address input and results display."""

import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import plotly.graph_objects as go
import httpx
import json

dash.register_page(__name__, path="/", name="Analyze")

API_BASE = "http://localhost:8000"

layout = html.Div([
    # Address Input Section
    html.Div([
        html.H2("Property Analysis"),
        html.P("Enter any US address to get a complete investment analysis."),
        html.Div([
            dcc.Input(
                id="address-input",
                type="text",
                placeholder="123 Main St, Austin, TX 78701",
                style={"width": "60%", "padding": "0.75rem", "fontSize": "1rem"},
            ),
            html.Button(
                "Analyze",
                id="analyze-btn",
                n_clicks=0,
                style={
                    "padding": "0.75rem 2rem",
                    "fontSize": "1rem",
                    "backgroundColor": "#1a1a2e",
                    "color": "white",
                    "border": "none",
                    "cursor": "pointer",
                    "marginLeft": "0.5rem",
                },
            ),
        ], style={"display": "flex", "gap": "0.5rem"}),
        dcc.Loading(
            id="loading",
            children=[html.Div(id="loading-output")],
            type="circle",
        ),
    ], style={"marginBottom": "2rem"}),

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


@callback(
    [Output("results-container", "children"), Output("loading-output", "children")],
    Input("analyze-btn", "n_clicks"),
    [
        State("address-input", "value"),
        State("filing-status", "value"),
        State("agi-input", "value"),
        State("fed-rate", "value"),
        State("state-rate", "value"),
    ],
    prevent_initial_call=True,
)
def run_analysis(n_clicks, address, filing_status, agi, fed_rate, state_rate):
    if not address:
        return no_update, no_update

    try:
        resp = httpx.post(
            f"{API_BASE}/api/v1/analyze",
            json={
                "address": address,
                "filing_status": filing_status,
                "agi": agi,
                "marginal_federal_rate": fed_rate / 100 if fed_rate else 0.37,
                "marginal_state_rate": state_rate / 100 if state_rate else 0.133,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return html.Div(f"Error: {e}", style={"color": "red"}), ""

    return _build_results(data), ""


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
    prop_card = html.Div([
        html.H3(f"{prop['street']}, {prop['city']}, {prop['state']} {prop['zip_code']}"),
        html.P(f"{prop['bedrooms']}bd / {prop['bathrooms']}ba · {prop['sqft']:,} sqft · Built {prop['year_built']}"),
        html.P(f"Value: ${float(prop['estimated_value']):,.0f} · Rent: ${float(prop['estimated_rent']):,.0f}/mo"),
    ], style={"backgroundColor": "#f5f5f5", "padding": "1rem", "borderRadius": "8px", "marginBottom": "2rem"})

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

    return html.Div([
        summary,
        prop_card,
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
