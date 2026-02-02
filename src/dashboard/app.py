"""Plotly Dash application — multi-page layout."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work
# even when Dash's reloader spawns a child process.
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import dash
from dash import Dash, html, dcc, page_container

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="RE Analyzer",
)

app.layout = html.Div([
    # Global session store — persists analysis data across page navigation
    dcc.Store(id="analysis-store", storage_type="session"),

    # Navigation
    html.Nav([
        html.Div([
            html.H1("RE Analyzer", style={"fontSize": "1.5rem", "margin": "0"}),
            html.Div([
                dcc.Link("Analyze", href="/", style={"marginRight": "1rem"}),
                dcc.Link("Tax Alpha", href="/tax-alpha", style={"marginRight": "1rem"}),
                dcc.Link("Compare", href="/compare", style={"marginRight": "1rem"}),
            ]),
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "maxWidth": "1200px",
            "margin": "0 auto",
            "padding": "0 1rem",
        }),
    ], style={
        "backgroundColor": "#1a1a2e",
        "color": "white",
        "padding": "1rem 0",
        "marginBottom": "2rem",
    }),

    # Page content
    html.Div(
        page_container,
        style={"maxWidth": "1200px", "margin": "0 auto", "padding": "0 1rem"},
    ),
])


if __name__ == "__main__":
    app.run(debug=True, port=8050)
