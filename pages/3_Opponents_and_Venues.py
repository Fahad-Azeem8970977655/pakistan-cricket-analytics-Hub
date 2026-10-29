import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Opponents & Venues", "Records against each team, where Pakistan plays, and the influence of toss and batting order")
if m.empty:
    st.warning("No matches for these filters."); st.stop()

top = st.slider("Top N opponents (by matches)", 5, 20, 10)
go_ = D.grouped_record(m, "opponent").sort_values("P", ascending=False).head(top)
names = go_.opponent.tolist()

c1, c2 = st.columns(2)
long = go_.melt("opponent", ["W", "L", "T", "Other"], var_name="outcome", value_name="matches")
long["outcome"] = long.outcome.map({"W": "Won", "L": "Lost", "T": "Tied", "Other": "Draw / NR"})
with c1:
    T.plot(px.bar(long, y="opponent", x="matches", color="outcome", orientation="h", text="matches",
                  color_discrete_map={"Won": "#0B8A4B", "Lost": "#D64545", "Tied": "#E5A100", "Draw / NR": "#C3CBD0"},
                  category_orders={"opponent": names[::-1]}), "Record vs opponents", "Matches", "Opponent", legend="Outcome", h=430)
hy = D.grouped_record(m[m.opponent.isin(names)], ["opponent", "year"]).pivot(index="opponent", columns="year", values="Win %")
with c2:
    T.plot(px.imshow(hy.reindex(names), text_auto=".0f", color_continuous_scale=T.DIV, zmin=0, zmax=100, aspect="auto"),
           "Win % heatmap (opponent × year)", "Year", "Opponent", cbar="Win %", h=430)

c3, c4 = st.columns(2)
vt = D.grouped_record(m, ["format", "location_type"])
f = px.bar(vt, x="location_type", y="Win %", color="format", barmode="group", color_discrete_map=D.FMT_COLORS, hover_data=["P"], text="Win %")
f.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
with c3: T.plot(f, "Win % by venue type", "Venue type", "Win %", pct=True, ylim=[0, 110], legend="Format", hline=50)
cy = D.grouped_record(m, ["location_type", "city"]).dropna(subset=["city"])
with c4:
    T.plot(px.treemap(cy, path=["location_type", "city"], values="P", color="Win %", color_continuous_scale=T.DIV, range_color=[0, 100]),
           "Where Pakistan plays (size = matches, colour = win %)", cbar="Win %")

T.section("Toss and batting order")
c5, c6 = st.columns(2)
tg = D.grouped_record(m, ["format", "pak_toss"])
with c5:
    f = px.bar(tg, x="format", y="Win %", color="pak_toss", barmode="group", hover_data=["P"], text="Win %",
               color_discrete_map={"Won toss": T.GREEN, "Lost toss": "#9AA5AD"})
    f.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
    T.plot(f, "Win % by toss result", "Format", "Win %", pct=True, ylim=[0, 110], legend="Toss", hline=50)
lo = m[(m.format != "Test") & m.pak_batting_order.notna()]
if len(lo):
    bg = D.grouped_record(lo, ["format", "pak_batting_order"])
    f = px.bar(bg, x="format", y="Win %", color="pak_batting_order", barmode="group", hover_data=["P"], text="Win %",
               color_discrete_sequence=["#2A7AB9", "#C9A227"])
    f.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
    with c6: T.plot(f, "Batting first vs chasing", "Format", "Win %", pct=True, ylim=[0, 110], legend="Innings", hline=50)

T.section("Margin of victory and defeat")
mm = m[m.margin_type.isin(["runs", "wickets"]) & m.result.isin(["Won", "Lost"])]
if len(mm):
    T.plot(px.box(mm, x="margin_type", y="margin_value", color="result", color_discrete_map=D.RES_COLORS, points="all", hover_data=["opponent", "date"]),
           "Distribution of margins", "Margin type", "Margin (runs or wickets)", legend="Result")

if "rain_mm" in m and m.rain_mm.notna().any():
    T.section("Weather")
    wx = m.dropna(subset=["rain_mm"]).assign(rain=lambda d: (d.rain_mm > 1).map({True: "Rain > 1mm", False: "Dry"}))
    c7, c8 = st.columns(2)
    with c7: T.plot(px.bar(D.grouped_record(wx, ["format", "rain"]), x="format", y="Win %", color="rain", barmode="group"), "Win % on dry vs rainy days", "Format", "Win %", pct=True)
    with c8: T.plot(px.scatter(wx, x="weather_tmax_c", y="pak_run_rate", color="result", color_discrete_map=D.RES_COLORS), "Temperature vs Pakistan run rate", "Max temperature (°C)", "Run rate")