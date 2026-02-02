"""Tax Alpha page — dynamic visualizations driven by analysis-store data.

Four visualizations:
  1. Tax Savings Waterfall
  2. RE vs S&P 500 After-Tax Comparison
  3. Effective Tax Rate Comparison
  4. Year-by-Year Tax Lifecycle
"""

import dash
from dash import html, dcc, callback, Input, Output, no_update
import plotly.graph_objects as go

dash.register_page(__name__, path="/tax-alpha", name="Tax Alpha")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CARD_STYLE = {
    "backgroundColor": "white",
    "border": "1px solid #ddd",
    "borderRadius": "8px",
    "padding": "1rem 1.5rem",
    "minWidth": "180px",
    "textAlign": "center",
}

EMPTY_MSG_STYLE = {
    "textAlign": "center",
    "padding": "4rem 2rem",
    "color": "#888",
    "fontSize": "1.1rem",
}

SP500_ANNUAL_RETURN = 0.10
SP500_DIVIDEND_YIELD = 0.015
LTCG_RATE = 0.20
NIIT_RATE = 0.038
DEFAULT_STATE_RATE = 0.09

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div([
    html.H2("Tax Alpha Analysis"),
    html.Div(id="tax-alpha-content"),
])


# ---------------------------------------------------------------------------
# Main callback — reads analysis-store, renders everything
# ---------------------------------------------------------------------------


@callback(
    Output("tax-alpha-content", "children"),
    Input("analysis-store", "data"),
)
def render_tax_alpha(data):
    if not data:
        return html.Div(
            "Run an analysis from the Analyze page to see your property's "
            "tax alpha breakdown.",
            style=EMPTY_MSG_STYLE,
        )

    projections = data.get("yearly_projections", [])
    disposition = data.get("disposition", {})
    if not projections:
        return html.Div("No projection data available.", style=EMPTY_MSG_STYLE)

    return html.Div([
        _build_scorecards(data),
        html.Div([
            html.Div(
                dcc.Graph(figure=_build_waterfall(data)),
                style={"width": "50%"},
            ),
            html.Div(
                dcc.Graph(figure=_build_sp500_comparison(data)),
                style={"width": "50%"},
            ),
        ], style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem"}),
        html.Div([
            html.Div(
                dcc.Graph(figure=_build_effective_tax_rates(data)),
                style={"width": "50%"},
            ),
            html.Div(
                dcc.Graph(figure=_build_yearly_lifecycle(data)),
                style={"width": "50%"},
            ),
        ], style={"display": "flex", "gap": "1rem"}),
    ])


# ---------------------------------------------------------------------------
# Scorecards
# ---------------------------------------------------------------------------


def _build_scorecards(data):
    projections = data["yearly_projections"]
    disposition = data["disposition"]

    total_depreciation = sum(float(p["total_depreciation"]) for p in projections)
    net_tax_impact = float(data.get("net_tax_impact", 0))
    before_tax_irr = float(data.get("before_tax_irr", 0))
    after_tax_irr = float(data.get("after_tax_irr", 0))
    total_profit = float(data.get("total_profit", 0))

    tax_efficiency = after_tax_irr / before_tax_irr if before_tax_irr else 0
    effective_re_rate = (
        -net_tax_impact / total_profit if total_profit else 0
    )

    cards = [
        _kpi_card("Total Depreciation", f"${total_depreciation:,.0f}",
                   "Sheltered from tax over hold period"),
        _kpi_card("Net Tax Impact", f"${net_tax_impact:,.0f}",
                   "Positive = tax code helped you",
                   color="#2ecc71" if net_tax_impact > 0 else "#e94560"),
        _kpi_card("Tax Efficiency", f"{tax_efficiency:.2f}x",
                   "After-tax IRR / Before-tax IRR",
                   color="#2ecc71" if tax_efficiency >= 1 else "#e94560"),
        _kpi_card("Effective RE Tax Rate", f"{effective_re_rate * 100:.1f}%",
                   f"vs ~33% equities rate",
                   color="#2ecc71" if effective_re_rate < 0.33 else "#e94560"),
    ]

    return html.Div(cards, style={
        "display": "flex", "gap": "1rem", "marginBottom": "2rem", "flexWrap": "wrap",
    })


def _kpi_card(label, value, subtitle, color=None):
    value_style = {"fontSize": "1.5rem", "fontWeight": "bold"}
    if color:
        value_style["color"] = color
    return html.Div([
        html.Div(value, style=value_style),
        html.Div(label, style={"fontSize": "0.85rem", "color": "#666"}),
        html.Div(subtitle, style={"fontSize": "0.75rem", "color": "#999", "marginTop": "0.25rem"}),
    ], style=CARD_STYLE)


# ---------------------------------------------------------------------------
# Visualization 1: Tax Savings Waterfall
# ---------------------------------------------------------------------------


def _build_waterfall(data):
    projections = data["yearly_projections"]
    disposition = data["disposition"]

    total_depreciation = sum(float(p["total_depreciation"]) for p in projections)
    total_tax_benefit_ops = float(data.get("total_tax_benefit_operations", 0))

    # If the API didn't provide total_tax_benefit_operations, compute from yearly
    if total_tax_benefit_ops == 0:
        total_tax_benefit_ops = sum(float(p["tax_benefit"]) for p in projections)

    suspended_released = float(disposition.get("suspended_losses_released", 0))
    release_benefit = float(disposition.get("tax_benefit_from_release", 0))

    recapture_tax = float(disposition.get("recapture_tax", 0))
    cap_gains_tax = float(disposition.get("capital_gains_tax", 0))
    niit_tax = float(disposition.get("niit_on_gain", 0))
    state_tax = float(disposition.get("state_tax_on_gain", 0))
    total_sale_taxes = recapture_tax + cap_gains_tax + niit_tax + state_tax

    net_tax_impact = float(data.get("net_tax_impact", 0))

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "total"],
        x=[
            "Operations<br>Tax Benefit",
            "Suspended Loss<br>Release Benefit",
            "Sale Taxes<br>(Recapture 25%)",
            "Sale Taxes<br>(LTCG+NIIT+State)",
            "Net Tax<br>Impact",
        ],
        y=[
            total_tax_benefit_ops,
            release_benefit,
            -recapture_tax,
            -(cap_gains_tax + niit_tax + state_tax),
            0,  # total computed automatically
        ],
        connector={"line": {"color": "#ccc"}},
        increasing={"marker": {"color": "#2ecc71"}},
        decreasing={"marker": {"color": "#e94560"}},
        totals={"marker": {"color": "#1a1a2e"}},
        textposition="outside",
        text=[
            f"${total_tax_benefit_ops:,.0f}",
            f"${release_benefit:,.0f}",
            f"-${recapture_tax:,.0f}",
            f"-${cap_gains_tax + niit_tax + state_tax:,.0f}",
            f"${net_tax_impact:,.0f}",
        ],
    ))

    fig.update_layout(
        title="Tax Savings Waterfall",
        yaxis_title="$",
        showlegend=False,
        margin=dict(t=40, b=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Visualization 2: RE vs S&P 500 After-Tax Comparison
# ---------------------------------------------------------------------------


def _build_sp500_comparison(data):
    projections = data["yearly_projections"]
    disposition = data["disposition"]
    initial = float(data.get("total_initial_investment", 0))
    after_tax_proceeds = float(disposition.get("after_tax_sale_proceeds", 0))

    hold_years = len(projections)
    years = list(range(0, hold_years + 1))

    # RE equity curve: start with initial investment, then yearly equity
    re_equity = [initial] + [float(p["equity"]) for p in projections]
    # Replace final year with after-tax sale proceeds
    re_equity[-1] = after_tax_proceeds

    # S&P 500 curve
    sp_equity = [initial]
    combined_tax_rate = LTCG_RATE + NIIT_RATE + DEFAULT_STATE_RATE  # ~32.8%
    for yr in range(1, hold_years + 1):
        prev = sp_equity[-1]
        growth = prev * SP500_ANNUAL_RETURN
        # Annual dividend tax drag
        div_tax = prev * SP500_DIVIDEND_YIELD * combined_tax_rate
        sp_equity.append(prev + growth - div_tax)

    # S&P after-tax final (sell: pay LTCG on gains)
    sp_gain = sp_equity[-1] - initial
    sp_tax = sp_gain * combined_tax_rate if sp_gain > 0 else 0
    sp_after_tax_final = sp_equity[-1] - sp_tax

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=years, y=re_equity,
        mode="lines+markers",
        name="RE (Leveraged)",
        line=dict(color="#1a1a2e", width=3),
    ))

    fig.add_trace(go.Scatter(
        x=years, y=sp_equity,
        mode="lines+markers",
        name="S&P 500 (10%/yr)",
        line=dict(color="#e94560", width=2, dash="dash"),
    ))

    # Annotate final values
    gap = after_tax_proceeds - sp_after_tax_final
    gap_label = f"+${gap:,.0f}" if gap > 0 else f"-${abs(gap):,.0f}"
    fig.add_annotation(
        x=hold_years, y=max(after_tax_proceeds, sp_after_tax_final),
        text=f"RE advantage: {gap_label}",
        showarrow=True, arrowhead=2, ay=-40,
        font=dict(size=11, color="#1a1a2e"),
    )

    fig.update_layout(
        title=f"RE vs S&P 500 — {hold_years}-Year After-Tax",
        xaxis_title="Year",
        yaxis_title="$",
        legend=dict(x=0.02, y=0.98),
        margin=dict(t=40, b=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Visualization 3: Effective Tax Rate Comparison
# ---------------------------------------------------------------------------


def _build_effective_tax_rates(data):
    net_tax_impact = float(data.get("net_tax_impact", 0))
    total_profit = float(data.get("total_profit", 0))

    # RE effective rate: negative net_tax_impact means taxes helped you
    # Rate = taxes_paid / profit. net_tax_impact is benefit (positive = good),
    # so effective rate = -net_tax_impact / total_profit
    re_rate = -net_tax_impact / total_profit * 100 if total_profit else 0

    # S&P effective rate for high earners
    sp_rate = (LTCG_RATE + NIIT_RATE + DEFAULT_STATE_RATE) * 100  # ~32.8%

    # W-2 marginal context (use investor's rates if available, else typical high earner)
    w2_rate = 50.3  # 37% fed + 13.3% state (typical CA high earner)

    categories = ["Real Estate", "S&P 500 (Equities)", "W-2 Income"]
    rates = [re_rate, sp_rate, w2_rate]
    colors = [
        "#2ecc71" if re_rate < sp_rate else "#e94560",
        "#f39c12",
        "#e94560",
    ]

    fig = go.Figure(go.Bar(
        x=categories,
        y=rates,
        marker_color=colors,
        text=[f"{r:.1f}%" for r in rates],
        textposition="outside",
    ))

    fig.add_hline(y=0, line_dash="dot", line_color="#999")

    fig.update_layout(
        title="Effective Tax Rate Comparison",
        yaxis_title="Effective Rate (%)",
        yaxis=dict(range=[min(re_rate - 10, -5), max(w2_rate + 10, 55)]),
        showlegend=False,
        margin=dict(t=40, b=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Visualization 4: Year-by-Year Tax Lifecycle
# ---------------------------------------------------------------------------


def _build_yearly_lifecycle(data):
    projections = data["yearly_projections"]
    disposition = data["disposition"]

    years = [p["year"] for p in projections]
    depreciation = [float(p["total_depreciation"]) for p in projections]
    taxable_income = [float(p["taxable_income"]) for p in projections]
    suspended = [float(p["suspended_loss"]) for p in projections]
    tax_benefit = [float(p["tax_benefit"]) for p in projections]

    # Cumulative suspended losses
    cum_suspended = []
    running = 0
    for s in suspended:
        running += s
        cum_suspended.append(running)

    fig = go.Figure()

    # Bar: annual depreciation
    fig.add_trace(go.Bar(
        x=years,
        y=depreciation,
        name="Depreciation",
        marker_color="#1a1a2e",
        opacity=0.7,
    ))

    # Line: taxable income
    fig.add_trace(go.Scatter(
        x=years,
        y=taxable_income,
        mode="lines+markers",
        name="Taxable Income",
        line=dict(color="#e94560", width=2),
    ))

    # Area: cumulative suspended losses
    fig.add_trace(go.Scatter(
        x=years,
        y=cum_suspended,
        mode="lines",
        name="Cumulative Suspended",
        fill="tozeroy",
        line=dict(color="#f39c12", width=1),
        fillcolor="rgba(243, 156, 18, 0.2)",
    ))

    # Marker at final year: disposition release
    released = float(disposition.get("suspended_losses_released", 0))
    if released > 0:
        fig.add_trace(go.Scatter(
            x=[years[-1]],
            y=[released],
            mode="markers+text",
            name="Release on Sale",
            marker=dict(size=14, color="#2ecc71", symbol="diamond"),
            text=[f"Released: ${released:,.0f}"],
            textposition="top center",
        ))

    fig.update_layout(
        title="Year-by-Year Tax Lifecycle",
        xaxis_title="Year",
        yaxis_title="$",
        barmode="overlay",
        legend=dict(x=0.02, y=0.98),
        margin=dict(t=40, b=20),
    )
    return fig
