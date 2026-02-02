"""Comparison page — RE vs S&P 500 equity curve."""

import dash
from dash import html, dcc
import plotly.graph_objects as go

dash.register_page(__name__, path="/compare", name="Compare")


def _placeholder_equity_curve():
    years = list(range(0, 8))
    re_equity = [100000, 115000, 132000, 150000, 170000, 192000, 216000, 243000]
    sp500_equity = [100000, 110000, 121000, 133100, 146410, 161051, 177156, 194872]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=re_equity,
        mode="lines+markers",
        name="Real Estate (Leveraged)",
        line=dict(color="#1a1a2e", width=3),
    ))
    fig.add_trace(go.Scatter(
        x=years, y=sp500_equity,
        mode="lines+markers",
        name="S&P 500 (Unleveraged)",
        line=dict(color="#e94560", width=3),
    ))
    fig.update_layout(
        title="After-Tax Equity Curve",
        xaxis_title="Year",
        yaxis_title="Portfolio Value ($)",
        hovermode="x unified",
    )
    return fig


layout = html.Div([
    html.H2("RE vs S&P 500 Comparison"),
    html.P("Compare leveraged real estate returns against S&P 500 buy-and-hold."),

    html.Div([
        html.Div([
            html.Label("S&P 500 Annual Return (%)"),
            dcc.Input(id="sp500-return", type="number", value=10, step=0.5),
        ], style={"width": "200px"}),
        html.Div([
            html.Label("Risk-Free Rate (%)"),
            dcc.Input(id="risk-free-rate", type="number", value=4, step=0.25),
        ], style={"width": "200px"}),
    ], style={"display": "flex", "gap": "1rem", "marginBottom": "2rem"}),

    dcc.Graph(id="equity-curve-chart", figure=_placeholder_equity_curve()),

    html.Div([
        html.H3("Key Insights"),
        html.Ul([
            html.Li("RE uses leverage (80% LTV): $100K controls a $500K asset"),
            html.Li("S&P 500 is unleveraged: $100K buys $100K of equities"),
            html.Li("RE has lower volatility (~5-8%) vs equities (~15%)"),
            html.Li("RE generates ongoing cash flow; S&P 500 generates dividends (~1.5%)"),
            html.Li("Both returns shown after-tax for apples-to-apples comparison"),
        ]),
    ]),
])
