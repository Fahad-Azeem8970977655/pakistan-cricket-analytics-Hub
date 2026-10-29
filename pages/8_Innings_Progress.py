import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
o = D.by_ids(D.load_extra()["overs"], set(m.match_id))
T.hero("Innings Progress", "Over-by-over scoring patterns, wicket timing and individual match worms")
lo = o[o.format != "Test"]
if lo.empty:
    st.warning("No limited-overs data for these filters."); st.stop()

fm = st.radio("Format", sorted(lo.format.unique()), horizontal=True)
x = lo[lo.format == fm]
T.section("Average scoring pattern")
avg = x.groupby(["side", "over"]).agg(runs=("runs", "mean"), cum=("cum_runs", "mean"), wk=("wickets", "mean")).reset_index()
c1, c2 = st.columns(2)
with c1: T.plot(px.line(avg, x="over", y="cum", color="side", color_discrete_map=T.SIDE_COLORS), f"{fm}: average cumulative runs", "Over", "Cumulative runs", legend="Side")
with c2: T.plot(px.bar(avg, x="over", y="runs", color="side", barmode="group", color_discrete_map=T.SIDE_COLORS), f"{fm}: average runs per over", "Over", "Average runs in the over", legend="Side")
yr = x[x.side == "Pakistan"].groupby(["year", "over"]).runs.mean().reset_index().pivot(index="year", columns="over", values="runs")
T.plot(px.imshow(yr, color_continuous_scale=T.SEQ_BLUE, aspect="auto"), "Pakistan: average runs per over by year", "Over", "Year", cbar="Runs per over", h=420)
wk = x.groupby(["side", "over"]).wickets.sum().reset_index()
T.plot(px.area(wk, x="over", y="wickets", color="side", color_discrete_map=T.SIDE_COLORS), "When do wickets fall? (total wickets by over)", "Over", "Wickets", legend="Side")

T.section("Match worm")
mm = m[m.format == fm].sort_values("date", ascending=False)
lab = mm.apply(lambda r: f"{r.date:%d %b %Y} v {r.opponent} ({r.result})", axis=1)
pick = st.selectbox("Match", range(len(mm)), format_func=lambda i: lab.iloc[i])
r = mm.iloc[pick]
mo = x[x.match_id == r.match_id]
f = go.Figure()
for (side, inn), g in mo.groupby(["side", "innings_no"]):
    f.add_trace(go.Scatter(x=g.over, y=g.cum_runs, mode="lines", name=f"{side} (innings {inn})", line=dict(color=T.SIDE_COLORS.get(side, "#888"), width=3)))
    wk_ = g[g.wickets > 0]
    f.add_trace(go.Scatter(x=wk_.over, y=wk_.cum_runs, mode="markers", marker=dict(symbol="x", size=9, color="black"), showlegend=False, hovertemplate="Wicket in over %{x}<extra></extra>"))
T.plot(f, f"{r.date:%d %b %Y} v {r.opponent}: {r.pak_score} vs {r.opp_score} (x = wicket)", "Over", "Runs", legend="Innings")
T.plot(px.bar(mo, x="over", y="runs", color="side", facet_row="innings_no", color_discrete_map=T.SIDE_COLORS), "Runs per over in this match", "Over", "Runs", legend="Side", h=480)
