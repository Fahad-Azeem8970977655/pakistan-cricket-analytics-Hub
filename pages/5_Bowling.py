import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Bowling", "Wicket-takers, economy, strike rates and phase wickets")
if w.empty:
    st.warning("No bowling data for these filters."); st.stop()

# dot balls are not recorded for the 15 hand-collected Afghanistan scorecards: divide only by balls that have dot data
wd = w.assign(_dbase=w.balls.where(w.dot_balls.notna(), 0))
p = wd.groupby("player").agg(Inns=("wickets", "size"), Balls=("balls", "sum"), Runs=("runs_conceded", "sum"), Wkts=("wickets", "sum"),
                            Maidens=("maidens", "sum"), Dots=("dot_balls", "sum"), DotBase=("_dbase", "sum"), FiveW=("is_five_wkts", "sum")).reset_index()
p["Overs"] = p.Balls.apply(lambda x: f"{x // 6}.{x % 6}")
p["Avg"] = (p.Runs / p.Wkts.where(p.Wkts > 0)).round(1)
p["Econ"] = (6 * p.Runs / p.Balls.where(p.Balls > 0)).round(2)
p["SR"] = (p.Balls / p.Wkts.where(p.Wkts > 0)).round(1)
p["Dot %"] = (100 * p.Dots / p.DotBase.where(p.DotBase > 0)).round(1)
tb, tr, tw = int(w.balls.sum()), int(w.runs_conceded.sum()), int(w.wickets.sum())
T.kpis([("Wickets", f"{tw:,}", f"{len(w):,} bowling spells", "green"), ("Bowling average", f"{tr / max(tw, 1):.1f}", "Runs per wicket", "green"),
        ("Economy", f"{6 * tr / max(tb, 1):.2f}", "Runs per over", "blue"), ("Strike rate", f"{tb / max(tw, 1):.1f}", "Balls per wicket", "blue"),
        ("Dot-ball %", f"{100 * w.dot_balls.sum() / max(int(wd._dbase.sum()), 1):.1f}%", "Balls with no run", "gold"), ("5-wicket hauls", int(w.is_five_wkts.sum()), "", "gold")])

mn = st.slider("Minimum wickets for leaderboards and charts", 0, 150, 30, 5)
q = p[p.Wkts >= mn].sort_values("Wkts", ascending=False)
c1, c2 = st.columns(2)
with c1:
    T.section("Leaderboard")
    st.dataframe(q[["player", "Inns", "Overs", "Wkts", "Avg", "Econ", "SR", "Dot %", "Maidens", "FiveW"]], hide_index=True, width="stretch", height=430)
with c2:
    T.section("Top wicket-takers")
    f = px.bar(q.head(15).sort_values("Wkts"), y="player", x="Wkts", color="Econ", orientation="h", color_continuous_scale=T.DIV_R, text="Wkts")
    f.update_traces(textposition="outside")
    T.plot(f, None, "Wickets", "Bowler", h=430, cbar="Economy")

T.section("Quality map")
T.plot(px.scatter(q, x="Econ", y="Avg", size="Wkts", color="Dot %", hover_name="player", color_continuous_scale="Viridis", text="player").update_traces(textposition="top center", textfont_size=9),
       "Economy vs bowling average (bubble = wickets, colour = dot-ball %)", "Economy (runs per over)", "Bowling average (runs per wicket)", h=480, cbar="Dot-ball %")

c3, c4 = st.columns(2)
wf = w.groupby(["year", "format"]).wickets.sum().reset_index()
with c3: T.plot(px.bar(wf, x="year", y="wickets", color="format", color_discrete_map=D.FMT_COLORS), "Wickets taken per year", "Year", "Wickets", legend="Format")
with c4: T.plot(px.histogram(w[w.format != "Test"], x="economy", nbins=40, color="format", color_discrete_map=D.FMT_COLORS, barmode="overlay", opacity=.75),
                "Economy rate per bowling spell (ODI & T20I)", "Economy (runs per over)", "Number of spells", legend="Format")

lo = m[m.format != "Test"]
if len(lo):
    ph = lo.groupby("year")[["pak_powerplay_wkts_taken", "pak_death_wkts_taken"]].sum().reset_index().melt("year")
    ph["variable"] = ph.variable.map({"pak_powerplay_wkts_taken": "Powerplay wickets", "pak_death_wkts_taken": "Death-over wickets"})
    T.plot(px.line(ph, x="year", y="value", color="variable", markers=True, color_discrete_sequence=[T.GREEN, "#D64545"]),
           "Wickets taken in powerplay vs death overs", "Year", "Wickets", legend="Phase")

T.section("Player profile")
who = st.selectbox("Bowler", p.sort_values("Wkts", ascending=False).player)
pw = w[w.player == who]
T.plot(px.scatter(pw, x="date", y="wickets", size="balls", color="format", color_discrete_map=D.FMT_COLORS, hover_data=["opponent", "runs_conceded", "economy"]),
       f"{who}: wickets in every spell (bubble = balls bowled)", "Date", "Wickets in spell", legend="Format")
T.section("Five-wicket hauls")
st.dataframe(w[w.is_five_wkts].sort_values("date", ascending=False)[["date", "player", "format", "opponent", "wickets", "runs_conceded", "venue"]], hide_index=True, width="stretch")
