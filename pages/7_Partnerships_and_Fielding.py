import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
X = D.load_extra()
ids = set(m.match_id)
p, f = D.by_ids(X["parts"], ids), D.by_ids(X["field"], ids)
T.hero("Partnerships & Fielding", "Best batting pairs, stand sizes by wicket, catches, stumpings and run-outs")
if p.empty:
    st.warning("No data for these filters."); st.stop()

T.kpis([("Partnerships", f"{len(p):,}", "", "green"), ("Highest stand", int(p.runs.max()), "runs", "gold"),
        ("100+ stands", int((p.runs >= 100).sum()), "", "green"), ("Average stand", f"{p.runs.mean():.1f}", "runs", "blue")], per_row=4)

T.section("Partnerships")
p = p.assign(pair=p.batter1 + " & " + p.batter2.fillna(""), label=p.date.dt.strftime("%d %b %Y") + " v " + p.opponent)
c1, c2 = st.columns(2)
top = p.sort_values("runs", ascending=False).head(15)
with c1:
    f_ = px.bar(top, y="pair", x="runs", color="format", orientation="h", color_discrete_map=D.FMT_COLORS, hover_data=["label", "wicket_no", "balls"], text="runs")
    f_.update_yaxes(autorange="reversed"); f_.update_traces(textposition="outside")
    f_.update_xaxes(range=[0, float(top.runs.max()) * 1.18])      # headroom so the number on the longest bar is not cut off
    T.plot(f_, "Highest partnerships", "Runs", "Batting pair", legend="Format", h=480)
with c2:
    fm = st.selectbox("Format for wicket-wise view", sorted(p.format.unique()))
    pw = p[(p.format == fm) & (p.wicket_no <= 10)]
    T.plot(px.box(pw, x="wicket_no", y="runs", points="outliers", color_discrete_sequence=[T.GREEN]), f"{fm}: partnership runs by wicket", "Wicket number", "Partnership runs", h=420)

pairs = p[p.balls > 0].groupby("pair").agg(Partnerships=("runs", "size"), Runs=("runs", "sum"), Balls=("balls", "sum"), Best=("runs", "max")).reset_index()
pairs["Runs per 100 balls"] = (100 * pairs.Runs / pairs.Balls).round(1)
mn = st.slider("Minimum runs together", 100, 2000, 500, 50)
q = pairs[pairs.Runs >= mn].sort_values("Runs", ascending=False)
T.plot(px.scatter(q, x="Runs per 100 balls", y="Best", size="Runs", hover_name="pair", color="Partnerships", color_continuous_scale="Viridis"),
       "Pairs: scoring rate vs best stand (bubble = total runs)", "Scoring rate (runs per 100 balls)", "Best stand (runs)", cbar="Partnerships", h=450)
st.dataframe(q.head(30), hide_index=True, width="stretch")

T.section("Fielding")
if f.empty:
    st.info("No fielding data for these filters."); st.stop()
fl = f.groupby("player").agg(Catches=("catches", "sum"), Stumpings=("stumpings", "sum"), RunOutsDirect=("runouts_direct", "sum"),
                             RunOutsAssisted=("runouts_assisted", "sum"), CaughtAndBowled=("caught_and_bowled", "sum"), Matches=("match_id", "nunique")).reset_index()
cols = ["Catches", "Stumpings", "RunOutsDirect", "RunOutsAssisted", "CaughtAndBowled"]
fl["Total"] = fl[cols].sum(axis=1)
top = fl.sort_values("Total", ascending=False).head(15)
long = top.melt(["player", "Matches", "Total"], cols, var_name="type", value_name="n")
long["type"] = long.type.map({"Catches": "Catches", "Stumpings": "Stumpings", "RunOutsDirect": "Run-outs (direct)", "RunOutsAssisted": "Run-outs (assisted)", "CaughtAndBowled": "Caught & bowled"})
d1, d2 = st.columns(2)
with d1:
    f_ = px.bar(long, y="player", x="n", color="type", orientation="h"); f_.update_yaxes(autorange="reversed")
    # five legend entries wrap over the title when they sit above the chart: put them in one block under the plot instead
    f_.update_layout(legend=dict(orientation="h", x=0, xanchor="left", y=-0.2, yanchor="top", title_text=""), margin=dict(b=120))
    T.plot(f_, "Dismissals by fielder (top 15)", "Dismissals", "Fielder", h=500)
fl["Per match"] = (fl.Total / fl.Matches).round(2)
with d2:
    T.plot(px.scatter(fl[fl.Matches >= 20], x="Matches", y="Per match", size="Total", hover_name="player", color="Stumpings", color_continuous_scale=T.SEQ_ORANGE),
           "Fielding involvement per match (min 20 matches)", "Matches played", "Dismissals per match", cbar="Stumpings", h=470)
st.caption("Catches by the wicketkeeper are not separated from other catches (Cricsheet does not mark the keeper). Stumpings identify keepers.")
st.dataframe(fl.sort_values("Total", ascending=False), hide_index=True, width="stretch", height=300)
