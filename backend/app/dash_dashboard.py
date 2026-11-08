"""Interactive Plotly Dash analytics for BookJob application tracking."""
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html

from . import config as C


PAGE_STYLE = {
    "minHeight": "100vh",
    "padding": "32px clamp(16px, 4vw, 56px)",
    "backgroundColor": "#f3f6fb",
    "color": "#0f2444",
    "fontFamily": "system-ui, sans-serif",
}
CARD_STYLE = {
    "backgroundColor": "#ffffff",
    "border": "1px solid #e1e8f2",
    "borderRadius": "18px",
    "padding": "24px",
    "boxShadow": "0 10px 30px rgba(15, 36, 68, 0.06)",
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
        font={"family": "system-ui, sans-serif", "color": "#0f2444"},
        paper_bgcolor="white",
        plot_bgcolor="white",
        colorway=["#245da8", "#c8a652", "#1f8a5b", "#8170c7", "#df7b8e", "#4b82b7"],
        hoverlabel={"bgcolor": "#0f2444", "font": {"color": "white"}},
    )
    return figure


def _status_figure(data: pd.DataFrame):
    counts = data["Statut"].value_counts().rename_axis("Statut").reset_index(name="Candidatures")
    is_empty = counts.empty
    if counts.empty:
        counts = pd.DataFrame({"Statut": ["Aucune donnée"], "Candidatures": [0]})
    figure = px.pie(
        counts,
        names="Statut",
        values="Candidatures",
        hole=0.62,
        color_discrete_sequence=["#245da8", "#c8a652", "#1f8a5b", "#8170c7", "#df7b8e", "#4b82b7"],
    )
    figure.update_traces(
        textposition="inside",
        textfont={"color": "white", "size": 12},
        marker={"line": {"color": "white", "width": 3}},
        hovertemplate="%{label}<br>%{value} candidature(s) · %{percent}<extra></extra>",
    )
    if is_empty:
        figure.add_annotation(
            text="Aucune candidature",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 12, "color": "#65738b"},
        )
    return _chart_layout(figure, "Candidatures par statut")


def _timeline_figure(data: pd.DataFrame):
    dated = data.dropna(subset=["Date_candidature"]).copy()
    if dated.empty:
        counts = pd.DataFrame({"Mois": pd.Series(dtype="object"), "Candidatures": pd.Series(dtype="int64")})
    else:
        dated["Mois"] = dated["Date_candidature"].dt.to_period("M").dt.to_timestamp()
        counts = dated.groupby("Mois").size().reset_index(name="Candidatures")
    figure = px.line(counts, x="Mois", y="Candidatures", markers=True, color_discrete_sequence=["#245da8"])
    figure.update_traces(
        line={"width": 3},
        marker={"size": 8, "line": {"color": "white", "width": 2}},
        fill="tozeroy",
        fillcolor="rgba(36, 93, 168, 0.08)",
        hovertemplate="%{x|%B %Y}<br>%{y} candidature(s)<extra></extra>",
    )
    if dated.empty:
        figure.add_annotation(
            text="Vos candidatures envoyées apparaîtront ici",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 13, "color": "#65738b"},
        )
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
    figure = px.bar(counts, x="Entreprises", y="Secteur", orientation="h", color_discrete_sequence=["#245da8"])
    figure.update_traces(
        marker={"cornerradius": 8},
        hovertemplate="%{y}<br>%{x} entreprise(s)<extra></extra>",
    )
    if counts.empty:
        figure.add_annotation(
            text="Aucune entreprise disponible",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 13, "color": "#65738b"},
        )
    figure.update_xaxes(title="Nombre d'entreprises", rangemode="tozero")
    figure.update_yaxes(title=None)
    return _chart_layout(figure, "Entreprises par secteur (10 principaux)")


def create_dash_app(load_tracking, load_companies) -> Dash:
    app = Dash(
        __name__,
        requests_pathname_prefix="/api/dash/",
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
                html.Section(
                    [
                        html.Div(
                            [
                                html.Span("✦", className="dash-star dash-star-one", **{"aria-hidden": "true"}),
                                html.Span("✧", className="dash-star dash-star-two", **{"aria-hidden": "true"}),
                                html.Span("✦", className="dash-star dash-star-three", **{"aria-hidden": "true"}),
                                html.A("← Retour à BookJob", href="/", className="dash-back"),
                                html.P("VOTRE PARCOURS, EN UN COUP D’ŒIL", className="dash-eyebrow"),
                                html.H1("Analyse des candidatures", className="dash-title"),
                                html.P(
                                    "Suivez vos démarches, repérez les prochaines étapes et faites avancer votre recherche.",
                                    className="dash-subtitle",
                                ),
                            ],
                            className="dash-hero-content",
                        ),
                    ],
                    className="dash-hero",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.P("Candidatures suivies", className="dash-kpi-label"),
                                html.Strong(str(len(data)), id="kpi-tracked", className="dash-kpi-value"),
                                html.Span("dans votre suivi", className="dash-kpi-note"),
                            ],
                            className="dash-kpi dash-kpi-blue",
                        ),
                        html.Div(
                            [
                                html.P("Envoyées", className="dash-kpi-label"),
                                html.Strong(str(sent), id="kpi-sent", className="dash-kpi-value"),
                                html.Span("démarches réalisées", className="dash-kpi-note"),
                            ],
                            className="dash-kpi dash-kpi-gold",
                        ),
                        html.Div(
                            [
                                html.P("Entretiens / offres", className="dash-kpi-label"),
                                html.Strong(str(interviews), id="kpi-interviews", className="dash-kpi-value"),
                                html.Span("nouvelles opportunités", className="dash-kpi-note"),
                            ],
                            className="dash-kpi dash-kpi-green",
                        ),
                    ],
                    className="dash-kpis",
                ),
                html.Section(
                    [
                        html.Div(
                            [
                                html.Label("Filtrer les candidatures par statut", htmlFor="status-filter", className="dash-filter-label"),
                                dcc.Dropdown(
                                    id="status-filter",
                                    options=options,
                                    value="",
                                    clearable=False,
                                    className="dash-dropdown",
                                ),
                            ],
                            className="dash-filter",
                        ),
                        html.Div(
                            [
                                html.Div(dcc.Graph(id="status-chart", figure=_status_figure(data), config=GRAPH_CONFIG), className="dash-chart"),
                                html.Div(dcc.Graph(id="timeline-chart", figure=_timeline_figure(data), config=GRAPH_CONFIG), className="dash-chart"),
                                html.Div(dcc.Graph(id="sector-chart", figure=_sector_figure(load_companies), config=GRAPH_CONFIG), className="dash-chart dash-chart-wide"),
                            ],
                            className="dash-charts",
                        ),
                    ],
                    className="dash-analytics",
                ),
            ],
            className="dash-page",
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
