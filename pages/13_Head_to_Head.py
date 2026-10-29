import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Head-to-Head", "Pakistan against one opponent: record, scoring, key players on both sides and recent meetings")
if m.empty:
    st.warning("No matches for these filters."); st.stop()

opps = m.opponent.value_counts().index.tolist()
opp = st.selectbox("Opponent", opps, help="Sorted by number of matches. Sidebar filters still apply.")
x = m[m.opponent == opp].sort_values("date")
ob, ow, _ = D.load_opp()
ids = set(x.match_id)
ob, ow = D.by_ids(ob, ids), D.by_ids(ow, ids)
xb, xw = b[b.match_id.isin(ids)], w[w.match_id.isin(ids)]

o = D.overall(x)
lo = x[x.format != "Test"]
T.kpis([
    ("Matches", int(o.P), f"{int(o.Completed)} completed", "green"),
    ("Pakistan won", int(o.W), f"{opp} won {int(o.L)}", "green"),
    ("Pakistan win %", D.fmt_pct(o["Win %"]), f"95% CI {o['CI low']}% to {o['CI high']}%", "green" if o["Win %"] >= 50 else "red", "up" if o["Win %"] >= 50 else "down"),
    ("Avg Pak score (ODI/T20I)", f"{lo.pak_runs.mean():.0f}" if len(lo) else "n/a", f"{opp}: {lo.opp_runs.mean():.0f}" if len(lo) else "", "blue"),
    ("Avg run rate", f"{lo.pak_run_rate.mean():.2f}" if len(lo) else "n/a", f"{opp}: {lo.opp_run_rate.mean():.2f}" if len(lo) else "", "blue"),
    ("Avg run difference", f"{x.run_diff.mean():+.0f}" if x.run_diff.notna().any() else "n/a", "Pakistan minus opposition, per match", "gold"),
])
st.markdown("**Last 10 meetings (oldest to newest):**"); T.form_strip(D.last_results(x, 10))

T.section("Record")
c1, c2, c3 = st.columns(3)
g = D.grouped_record(x, "format")
f = px.bar(g.melt("format", ["W", "L", "T", "Other"], var_name="o", value_name="n").assign(o=lambda d: d.o.map({"W": "Won", "L": "Lost", "T": "Tied", "Other": "Draw / NR"})),
           x="format", y="n", color="o", text="n", color_discrete_map={"Won": "#0B8A4B", "Lost": "#D64545", "Tied": "#E5A100", "Draw / NR": "#C3CBD0"})
with c1: T.plot(f, f"Record vs {opp} by format", "Format", "Matches", legend="Outcome", h=340)
gl = D.grouped_record(x, "location_type")
f = px.bar(gl, x="location_type", y="Win %", text="Win %", color="location_type", hover_data=["P"], color_discrete_sequence=T.COLORWAY)
f.update_traces(texttemplate="%{text:.0f}%", textposition="outside"); f.update_layout(showlegend=False)
with c2: T.plot(f, "Win % by venue type", "Venue type", "Win %", pct=True, ylim=[0, 110], hline=50, h=340)
gy = D.grouped_record(x, "year")
f = px.bar(gy, x="year", y="Win %", text="Win %", hover_data=["P"], color="Win %", color_continuous_scale=T.DIV, range_color=[0, 100])
f.update_traces(texttemplate="%{text:.0f}%", textposition="outside"); f.update_layout(coloraxis_showscale=False)
with c3: T.plot(f, "Win % by year", "Year", "Win %", pct=True, ylim=[0, 115], hline=50, h=340)

T.section("Scoring comparison", "ODI & T20I")
if len(lo):
    d1, d2 = st.columns(2)
    sc = lo.tail(20).assign(label=lambda d: d.date.dt.strftime("%b %y") + " " + d.format)
    f = go.Figure()
    f.add_bar(x=sc.label, y=sc.pak_runs, name="Pakistan", marker_color=T.SIDE_COLORS["Pakistan"])
    f.add_bar(x=sc.label, y=sc.opp_runs, name=opp, marker_color=T.SIDE_COLORS["Opposition"])
    f.update_layout(barmode="group"); f.update_xaxes(tickangle=60)
    with d1: T.plot(f, f"Team totals, last 20 limited-overs meetings: Pakistan vs {opp}", "Match", "Runs", legend="Side")
    ph = pd.DataFrame({"Phase": ["Powerplay", "Middle", "Death"] * 2, "Side": ["Pakistan"] * 3 + [opp] * 3,
                       "Avg runs": [lo.pak_powerplay_runs.mean(), lo.pak_middle_runs.mean(), lo.pak_death_runs.mean(),
                                    lo.opp_powerplay_runs.mean(), lo.opp_middle_runs.mean(), lo.opp_death_runs.mean()]})
    f = px.bar(ph, x="Phase", y="Avg runs", color="Side", barmode="group", text="Avg runs", color_discrete_map={"Pakistan": T.GREEN, opp: "#D64545"})
    f.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    with d2: T.plot(f, "Average runs by phase", "Phase of innings", "Average runs", legend="Side")
else:
    st.info("Include ODI or T20I matches to see the scoring comparison.")

T.section("Key players in this rivalry", "top performers in these matches only")


def side_bar(df, val, side, color, title, xlab, ylab):
    df = df.copy()
    df[val] = pd.to_numeric(df[val], errors="coerce")
    df = df.dropna(subset=[val])
    if df.empty:
        st.info(f"{title}: no scorecard data (matches added manually have no player rows).")
        return
    d = df.nlargest(8, val).sort_values(val)
    f = px.bar(d, y="player", x=val, orientation="h", text=val, color_discrete_sequence=[color])
    f.update_traces(textposition="outside"); f.update_xaxes(range=[0, (d[val].max() if len(d) else 1) * 1.2])
    T.plot(f, title, xlab, ylab, h=400)


pb = xb.groupby("player").agg(Runs=("runs", "sum"), Inns=("runs", "size")).reset_index()
ob_ = ob.groupby("player").agg(Runs=("runs", "sum"), Inns=("runs", "size")).reset_index() if len(ob) else pd.DataFrame(columns=["player", "Runs", "Inns"])
pw = xw.groupby("player").agg(Wkts=("wickets", "sum")).reset_index()
ow_ = ow.groupby("player").agg(Wkts=("wickets", "sum")).reset_index() if len(ow) else pd.DataFrame(columns=["player", "Wkts"])
c1, c2 = st.columns(2)
with c1: side_bar(pb, "Runs", "Pakistan", T.GREEN, "Pakistan: top run-scorers", "Runs", "Pakistan batter")
with c2: side_bar(ob_, "Runs", opp, "#D64545", f"{opp}: top run-scorers", "Runs", f"{opp} batter")
c3, c4 = st.columns(2)
with c3: side_bar(pw, "Wkts", "Pakistan", T.GREEN, "Pakistan: top wicket-takers", "Wickets", "Pakistan bowler")
with c4: side_bar(ow_, "Wkts", opp, "#D64545", f"{opp}: top wicket-takers", "Wickets", f"{opp} bowler")

T.section("Venues and recent meetings")
v = D.grouped_record(x, ["venue"]).sort_values("P", ascending=False).head(10).sort_values("P")
f = px.bar(v, y="venue", x="P", text="Win %", color="Win %", color_continuous_scale=T.DIV, range_color=[0, 100])
f.update_traces(texttemplate="%{text:.0f}% wins", textposition="outside"); f.update_layout(coloraxis_showscale=False)
f.update_xaxes(range=[0, v.P.max() * 1.3])
T.plot(f, "Most-used venues in this rivalry (label = Pakistan win %)", "Matches", "Venue", h=380)
t = x.sort_values("date", ascending=False).head(15)[["date", "format", "tournament", "venue", "pak_score", "opp_score", "result", "margin", "player_of_match"]]
st.dataframe(t.assign(date=t.date.dt.strftime("%d %b %Y")), hide_index=True, width="stretch")
