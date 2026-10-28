"""Interactive Plotly Dash analytics for BookJob application tracking."""
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html

from . import config as C


PAGE_STYLE = {
    "minHeight": "100vh",
    "padding": "32px clamp(16px, 4vw, 56px)",
    "backgroundColor": "#f5f7fb",
    "color": "#17233b",
    "fontFamily": "system-ui, sans-serif",
}
CARD_STYLE = {
    "backgroundColor": "#ffffff",
    "border": "1px solid #e5eaf2",
    "borderRadius": "16px",
    "padding": "20px",
    "boxShadow": "0 4px 18px rgba(23, 35, 59, 0.05)",
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def _application_data(load_tracking) -> pd.DataFrame:
    try:
        data = load_tracking().copy()
    except Exception:  # base injoignable : ne pas faire planter le démarrage
        data = pd.DataFrame()
    if "Statut" not in data:
        data["Statut"] = pd.Series(dtype="object")
    data["Statut"] = data["Statut"].fillna("").replace("", "À contacter")
    if "Date_candidature" not in data:
        data["Date_candidature"] = pd.Series(dtype="object")
    if "Secteur" not in data:
        data["Secteur"] = pd.Series(dtype="object")
    if "Entreprise" not in data:
        data["Entreprise"] = pd.Series(dtype="object")
    data["Date_candidature"] = pd.to_datetime(data["Date_candidature"], errors="coerce")
    return data


def _chart_layout(figure, title: str):
    figure.update_layout(
        title={"text": title, "x": 0.03, "xanchor": "left"},
        template="plotly_white",
        margin={"l": 24, "r": 24, "t": 64, "b": 24},
        font={"family": "system-ui, sans-serif", "color": "#17233b"},
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return figure


def _status_figure(data: pd.DataFrame):
    counts = data["Statut"].value_counts().rename_axis("Statut").reset_index(name="Candidatures")
    if counts.empty:
        counts = pd.DataFrame({"Statut": ["Aucune donnée"], "Candidatures": [0]})
    figure = px.pie(counts, names="Statut", values="Candidatures", hole=0.58)
    return _chart_layout(figure, "Candidatures par statut")


def _timeline_figure(data: pd.DataFrame):
    dated = data.dropna(subset=["Date_candidature"]).copy()
    if dated.empty:
        counts = pd.DataFrame({"Mois": pd.Series(dtype="object"), "Candidatures": pd.Series(dtype="int64")})
    else:
        dated["Mois"] = dated["Date_candidature"].dt.to_period("M").dt.to_timestamp()
        counts = dated.groupby("Mois").size().reset_index(name="Candidatures")
    figure = px.line(counts, x="Mois", y="Candidatures", markers=True)
    figure.update_xaxes(title=None)
    figure.update_yaxes(title="Nombre de candidatures", rangemode="tozero")
    return _chart_layout(figure, "Évolution des candidatures envoyées")


def _sector_figure(load_companies):
    companies = load_companies()
    if "Secteur" in companies:
        counts = companies["Secteur"].fillna("").replace("", "Non précisé").value_counts()
        counts = counts.head(10).sort_values().rename_axis("Secteur").reset_index(name="Entreprises")
    else:
        counts = pd.DataFrame({"Secteur": pd.Series(dtype="object"), "Entreprises": pd.Series(dtype="int64")})
    figure = px.bar(counts, x="Entreprises", y="Secteur", orientation="h")
    figure.update_xaxes(title="Nombre d'entreprises", rangemode="tozero")
    figure.update_yaxes(title=None)
    return _chart_layout(figure, "Entreprises par secteur (10 principaux)")


def create_dash_app(load_tracking, load_companies) -> Dash:
    app = Dash(
        __name__,
        requests_pathname_prefix="/dash/",
        routes_pathname_prefix="/",
        title="BookJob — Analyse",
        update_title="Mise à jour…",
    )

    def layout():
        data = _application_data(load_tracking)
        sent = int((~data["Statut"].isin(C.STATUTS_NON_ENVOYES | {"À contacter"})).sum())
        interviews = int(data["Statut"].isin({"Entretien programmé", "Acceptée", "Entretien", "Accepté"}).sum())
        options = [{"label": "Tous les statuts", "value": ""}] + [
            {"label": status, "value": status} for status in C.STATUTS
        ]
        return html.Main(
            [
                html.A("← Retour à BookJob", href="/", style={"color": "#245da8", "textDecoration": "none"}),
                html.H1("Analyse des candidatures", style={"marginBottom": "8px"}),
                html.P(
                    "Vue interactive de ton suivi et des entreprises disponibles.",
                    style={"color": "#65738b", "marginTop": 0},
                ),
                html.Div(
                    [
                        html.Div([html.Div("Candidatures suivies"), html.Strong(str(len(data)), id="kpi-tracked")], style=CARD_STYLE),
                        html.Div([html.Div("Envoyées"), html.Strong(str(sent), id="kpi-sent")], style=CARD_STYLE),
                        html.Div([html.Div("Entretiens / offres"), html.Strong(str(interviews), id="kpi-interviews")], style=CARD_STYLE),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                        "gap": "16px",
                        "margin": "24px 0",
                    },
                ),
                html.Label("Filtrer les candidatures par statut", htmlFor="status-filter"),
                dcc.Dropdown(
                    id="status-filter",
                    options=options,
                    value="",
                    clearable=False,
                    style={"maxWidth": "420px", "marginTop": "8px"},
                ),
                html.Div(
                    [
                        dcc.Graph(id="status-chart", figure=_status_figure(data), config=GRAPH_CONFIG),
                        dcc.Graph(id="timeline-chart", figure=_timeline_figure(data), config=GRAPH_CONFIG),
                        dcc.Graph(id="sector-chart", figure=_sector_figure(load_companies), config=GRAPH_CONFIG),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(min(100%, 380px), 1fr))",
                        "gap": "16px",
                        "marginTop": "20px",
                    },
                ),
            ],
            style=PAGE_STYLE,
        )

    app.layout = layout

    @app.callback(
        Output("status-chart", "figure"),
        Output("timeline-chart", "figure"),
        Input("status-filter", "value"),
    )
    def update_application_charts(selected_status):
        data = _application_data(load_tracking)
        if selected_status:
            data = data[data["Statut"] == selected_status]
        return _status_figure(data), _timeline_figure(data)

    return app
