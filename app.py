import pandas as pd
import numpy as np
import base64
from dash import Dash, dcc, html, callback_context
from dash.dependencies import Input, Output, State
import plotly.express as px
import pandas as pd
import requests
import io

# Direct download URL
google_drive_url = "https://drive.google.com/uc?id=1Jb4txZdbRpuQxfMKuxkYKWAl9Q47t-EZ"

# Download and read parquet
response = requests.get(google_drive_url)
eb_analytics_dataset = pd.read_parquet(io.BytesIO(response.content), engine="pyarrow")

def load_image(path):
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{encoded}"

indus_logo = load_image("indus.png")
kie_logo = load_image("kie.png")



df = eb_analytics_dataset.copy()

df["MONTH"] = pd.to_datetime(df["MONTH"])
df = df[df["MONTH"].dt.month.isin([7,8,9])]

df["ERR"] = df["FORECAST_TOTAL"] - df["ACTUAL_TOTAL"]
df["ABS_ERR"] = df["ERR"].abs()

df["CircleName"] = df["CircleName"].astype("category")
df["DISCOM_NAME"] = df["DISCOM_NAME"].astype("category")
df["SITE_ID"] = df["SITE_ID"].astype("category")



app = Dash(__name__)
server = app.server



app.layout = html.Div(style={
    "background":"#020617",
    "padding":"20px",
    "fontFamily":"Arial"
}, children=[

html.Div(
    style={
        "display": "grid",
        "gridTemplateColumns": "auto 1fr auto",
        "alignItems": "center",
        "width": "100%",
        "marginBottom": "10px"
    },
    children=[

        # LEFT — INDUS LOGO
        html.Div(
            html.Img(
                src=indus_logo,
                style={
                    "height": "70px",
                    "marginLeft": "0px"
                }
            ),
            style={"justifySelf": "start"}
        ),

        # CENTER — TITLE
        html.Div(
            html.H2(
                "⚡ EB FTM Forecast Performance Dashboard",
                style={
                    "color": "white",
                    "margin": "0",
                    "textAlign": "center",
                    "fontWeight": "600"
                }
            ),
            style={"textAlign": "center"}
        ),

        # RIGHT — KIE LOGO
        html.Div(
            html.Img(
                src=kie_logo,
                style={
                    "height": "40px",
                    "marginRight": "5px"
                }
            ),
            style={"justifySelf": "end"}
        ),
    ]
),

html.Hr(style={"border":"1px solid #1e293b"}),

dcc.Store(id="selected_circle_store", data=None),

html.Div([

    dcc.Dropdown(
        id="month_filter",
        options=[{"label":m.strftime("%b-%Y"),"value":m}
                 for m in sorted(df["MONTH"].unique())],
        multi=True, placeholder="Month"),

    dcc.Dropdown(
        id="circle_filter",
        options=[{"label":c,"value":c}
                 for c in sorted(df["CircleName"].dropna().unique())],
        multi=True, placeholder="Circle"),

    dcc.Dropdown(
        id="discom_filter",
        options=[{"label":d,"value":d}
                 for d in sorted(df["DISCOM_NAME"].dropna().unique())],
        multi=True, placeholder="DISCOM"),

],
style={"display":"grid","gridTemplateColumns":"repeat(3,1fr)","gap":"10px"}),

html.Br(),

dcc.RadioItems(
    id="accuracy_toggle",
    options=[
        {"label":"WMAPE","value":"wmape"},
        {"label":"Overall Accuracy","value":"simple"},
    ],
    value="wmape",
    inline=True,
    style={"color":"white","marginBottom":"10px"}
),

html.Button(
    "⬅ Reset View",
    id="reset_button",
    n_clicks=0,
    style={
        "background":"#1e293b",
        "color":"white",
        "padding":"10px 18px",
        "borderRadius":"8px",
        "border":"none"
    }
),

html.Br(), html.Br(),

html.Div(id="kpi_cards",
         style={"display":"grid",
                "gridTemplateColumns":"repeat(6,1fr)",
                "gap":"14px"}),

html.Hr(),

html.Div([
    dcc.Graph(id="accuracy_chart"),
    dcc.Graph(id="cost_chart")
],style={"display":"grid","gridTemplateColumns":"1fr 1fr"}),

html.Hr(),

dcc.Graph(id="sites_distribution"),

html.Hr(),

dcc.Graph(id="site_map")
])



@app.callback(
[
Output("kpi_cards","children"),
Output("accuracy_chart","figure"),
Output("cost_chart","figure"),
Output("sites_distribution","figure"),
Output("site_map","figure"),
Output("selected_circle_store","data"),
],
[
Input("month_filter","value"),
Input("circle_filter","value"),
Input("discom_filter","value"),
Input("accuracy_toggle","value"),
Input("accuracy_chart","clickData"),
Input("reset_button","n_clicks"),
],
[State("selected_circle_store","data")]
)
def update_dashboard(months,circles,discoms,
                     accuracy_mode,
                     click_circle,reset_clicks,
                     stored_circle):

    mask = pd.Series(True,index=df.index)

    if months:
        mask &= df["MONTH"].isin(pd.to_datetime(months))

    if circles:
        mask &= df["CircleName"].isin(circles)

    if discoms:
        mask &= df["DISCOM_NAME"].isin(discoms)

    dff = df.loc[mask]

    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger == "reset_button":
        selected_circle = None

    elif trigger == "accuracy_chart" and click_circle:
        selected_circle = click_circle["points"][0]["y"]

    elif circles and len(circles) == 1:
        selected_circle = circles[0]

    elif circles and len(circles) > 1:
        selected_circle = None

    else:
        selected_circle = stored_circle

    if selected_circle:
        dff = dff[dff["CircleName"] == selected_circle]

    act_total = dff["ACTUAL_TOTAL"].sum()
    fc_total = dff["FORECAST_TOTAL"].sum()
    total_sites = dff["SITE_ID"].nunique()

    wmape = dff["ABS_ERR"].sum()/(act_total+1e-9)
    wmape_acc = np.clip(1-wmape,0,1)

    simple_acc = np.clip(
        1-abs(fc_total-act_total)/(act_total+1e-9),0,1)

    def card(t,v):
        return html.Div([
            html.Div(t,style={"fontSize":"13px","opacity":"0.7"}),
            html.H3(v)
        ],style={"background":"#0f172a",
                 "padding":"18px",
                 "borderRadius":"12px",
                 "color":"white"})

    kpis=[
        card("WMAP Accuracy",f"{wmape_acc:.1%}"),
        card("Overal Accuracy",f"{simple_acc:.1%}"),
        card("Total Sites",f"{total_sites:,}"),
        card("Actual Cost",f"₹{act_total:,.0f}"),
        card("Forecast Cost",f"₹{fc_total:,.0f}"),
        card("Variance(Forecast- Actual)",f"₹{fc_total-act_total:,.0f}")
    ]

    group_level = "DISCOM_NAME" if selected_circle else "CircleName"

    agg = (dff.groupby(group_level, observed=True)
           .agg(
               Actual=("ACTUAL_TOTAL","sum"),
               Forecast=("FORECAST_TOTAL","sum"),
               AbsErr=("ABS_ERR","sum"),
               Sites=("SITE_ID","nunique")
           )
           .reset_index()
           .rename(columns={group_level:"Group"}))

    agg["WMAPE_ACC"]=(1-agg["AbsErr"]/
                      (agg["Actual"]+1e-9)).clip(0,1)

    agg["SIMPLE_ACC"]=(1-abs(agg["Forecast"]-
                             agg["Actual"])/
                       (agg["Actual"]+1e-9)).clip(0,1)

    metric="WMAPE_ACC" if accuracy_mode=="wmape" else "SIMPLE_ACC"

    level_name = (
        f"DISCOM — {selected_circle}"
        if selected_circle else "Circle"
    )

    acc_fig = px.bar(
    agg.sort_values(metric),
    x=metric,
    y="Group",
    orientation="h",
    template="plotly_dark",
    title=f"{level_name} Accuracy ({accuracy_mode.upper()})"
    )
    acc_fig.update_layout(height=600)

    cost_fig = px.bar(
        agg.sort_values("Actual").melt(
            id_vars="Group",
            value_vars=["Actual","Forecast"],
            var_name="Type",
            value_name="Cost"),
        x="Cost",
        y="Group",
        color="Type",
        orientation="h",
        barmode="group",
        template="plotly_dark",
        title=f"{level_name} Actual vs Forecast Cost"
        
    )
    cost_fig.update_layout(height=600)
    acc_fig.update_layout(height=600)

    # FIXED ACCURACY SCAL
    acc_fig.update_xaxes(range=[0.4,1])

    sites_fig = px.bar(
        agg.sort_values("Sites"),
        x="Sites",y="Group",
        orientation="h",
        template="plotly_dark",
        title=f"Sites by {level_name}"
    )

    geo = dff.dropna(subset=["Latitude","Longitude"]).copy()

    geo["WMAPE_ACC"]=(1-geo["ABS_ERR"]/
                      (geo["ACTUAL_TOTAL"]+1e-9)).clip(0,1)

    map_fig = px.scatter_mapbox(
        geo,
        lat="Latitude",
        lon="Longitude",
        color="WMAPE_ACC",
        size="ACTUAL_TOTAL",
        color_continuous_scale="RdYlGn",
        zoom=4 if not selected_circle else 6,
        height=650)

    map_fig.update_layout(
        mapbox_style="carto-darkmatter",
        template="plotly_dark",
        title="WMAP Accuracy Heatmap")

    return kpis,acc_fig,cost_fig,sites_fig,map_fig,selected_circle



if __name__ == "__main__":

    app.run_server(host="0.0.0.0", port=10000)

