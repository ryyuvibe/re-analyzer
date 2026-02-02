"""Tax alpha page — year-by-year passive loss waterfall and depreciation breakdown."""

import dash
from dash import html, dcc
import plotly.graph_objects as go

dash.register_page(__name__, path="/tax-alpha", name="Tax Alpha")


def _placeholder_depreciation_chart():
    fig = go.Figure()
    years = list(range(1, 8))
    fig.add_trace(go.Bar(x=years, y=[14000] * 7, name="27.5-yr SL", marker_color="#1a1a2e"))
    fig.add_trace(go.Bar(x=years, y=[45000, 12000, 10000, 8000, 6000, 5000, 5000],
                         name="With Cost Seg", marker_color="#e94560"))
    fig.update_layout(title="Annual Depreciation", barmode="group",
                      xaxis_title="Year", yaxis_title="$")
    return fig


def _placeholder_passive_loss_chart():
    fig = go.Figure()
    years = list(range(1, 8))
    fig.add_trace(go.Scatter(
        x=years,
        y=[5000, 12000, 19000, 25000, 30000, 34000, 37000],
        mode="lines+markers",
        name="Cumulative Suspended",
        fill="tozeroy",
        line=dict(color="#e94560"),
    ))
    fig.update_layout(title="Suspended Passive Losses (IRC 469)",
                      xaxis_title="Year", yaxis_title="$")
    return fig


layout = html.Div([
    html.H2("Tax Alpha Analysis"),
    html.P("Run an analysis from the Analyze page to see tax alpha breakdown here."),

    # Placeholder charts (populated via shared state in production)
    html.Div([
        html.Div([
            html.H3("Depreciation Schedule"),
            html.P("Shows 27.5-year straight-line vs cost segregation accelerated depreciation."),
            dcc.Graph(id="depreciation-chart", figure=_placeholder_depreciation_chart()),
        ], style={"width": "50%"}),
        html.Div([
            html.H3("Passive Loss Waterfall"),
            html.P("Tracks suspended losses year-over-year per IRC 469."),
            dcc.Graph(id="passive-loss-chart", figure=_placeholder_passive_loss_chart()),
        ], style={"width": "50%"}),
    ], style={"display": "flex", "gap": "1rem"}),

    html.Div([
        html.H3("Tax Impact Summary"),
        html.Ul([
            html.Li("Depreciation creates paper losses that offset taxable income"),
            html.Li("For high-income W-2 earners (AGI > $150K), rental losses are suspended"),
            html.Li("Suspended losses are released on full taxable disposition (IRC 469(g)(1)(A))"),
            html.Li("Cost segregation accelerates depreciation via MACRS reclassification"),
            html.Li("Net tax impact = operations benefit + release benefit - sale taxes"),
        ]),
    ], style={"marginTop": "2rem"}),
])
