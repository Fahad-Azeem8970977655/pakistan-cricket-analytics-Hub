import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import analytics as A
from utils import data as D
from utils import insights as I
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Pakistan Cricket · Executive Overview", "Men's internationals: results, form, players and AI-driven predictions in one place.",
       chips=[f"{len(m)} matches in view", f"{m.year.min()} to {m.year.max()}", "Test · ODI · T20I", "Source: Cricsheet + manual additions"])
if m.empty:
    st.warning("No matches for these filters."); st.stop()

o = D.overall(m)
done = m[m.result.isin(["Won", "Lost", "Tied"])]
lo = m[m.format != "Test"]
home, _ = D.split_record(m.assign(h=m.location_type.str.startswith("Home")), "h", True)
away, _ = D.split_record(m, "location_type", "Away")
neut, _ = D.split_record(m, "location_type", "Neutral")
chase, _ = D.split_record(lo, "pak_batting_order", "Batting second")
setw, _ = D.split_record(lo, "pak_batting_order", "Batting first")
tw = m[m.pak_won_toss == True]
toss_conv = D.pct(int((tw.result == "Won").sum()), int(tw.result.isin(["Won", "Lost", "Tied"]).sum()))
last10 = D.last_results(m, 10)
l10w = sum(r == "Won" for r in last10)
form_pct = D.pct(l10w, sum(r in ("Won", "Lost", "Tied") for r in last10))
wl = o.W / o.L if o.L else None
tone_w = "green" if o["Win %"] >= 50 else "red"

T.section("Headline KPIs")
T.kpis([
    ("Matches played", int(o.P), f"{int(o.Completed)} completed", "green"),
    ("Won / Lost", f"{int(o.W)} / {int(o.L)}", f"Win/loss ratio {wl:.2f}" if wl else "", "green"),
    ("Win %", D.fmt_pct(o["Win %"]), f"95% CI {o['CI low']}% to {o['CI high']}%", tone_w, "up" if o["Win %"] >= 50 else "down"),
    ("Last 10 matches", f"{l10w} wins", f"{D.fmt_pct(form_pct)} win rate", "gold", "up" if (form_pct or 0) >= o["Win %"] else "down"),
    ("Home win %", D.fmt_pct(home), "Pakistan + UAE home games", "blue"),
    ("Away win %", D.fmt_pct(away), f"Neutral venues {D.fmt_pct(neut)}", "blue"),
])
T.kpis([
    ("Chasing win %", D.fmt_pct(chase), "ODI & T20I, batting second", "gold"),
    ("Defending win %", D.fmt_pct(setw), "ODI & T20I, batting first", "gold"),
    ("Toss-winner win %", D.fmt_pct(toss_conv), "Matches won after winning the toss", "grey"),
    ("Avg run rate (ODI/T20I)", f"{lo.pak_run_rate.mean():.2f}" if len(lo) else "n/a",
     f"Opposition {lo.opp_run_rate.mean():.2f}" if len(lo) else "", "green"),
    ("Centuries / 50s", f"{int(b.is_hundred.sum())} / {int(b.is_fifty.sum())}", "Pakistan batters", "green"),
    ("5-wicket hauls", int(w.is_five_wkts.sum()), f"{int(w.wickets.sum())} wickets taken", "green"),
])
st.markdown("**Recent form (oldest to newest):**")
T.form_strip(last10)

T.section("Key takeaways", "generated automatically from the current filters")
fb = A.batting_form(b) if len(b) else None
I.render(I.generate(m, b, w, fb))

T.section("Results and trend")
c1, c2, c3 = st.columns([1, 1, 1.2])
with c1:
    r = m.result.value_counts().reset_index()
    f = px.pie(r, names="result", values="count", hole=.58, color="result", color_discrete_map=D.RES_COLORS)
    f.update_layout(annotations=[dict(text=f"<b>{len(m)}</b><br>matches", showarrow=False, font_size=15, x=0.5, y=0.47, xref="paper", yref="paper")])
    T.plot(f, "Match results", h=340)
with c2:
    gf = D.grouped_record(m, "format")
    f = px.bar(gf, x="format", y="Win %", color="format", text="Win %", color_discrete_map=D.FMT_COLORS,
               hover_data={"P": True, "W": True, "L": True})
    f.update_traces(texttemplate="%{text}%", textposition="outside"); f.update_layout(showlegend=False)
    T.plot(f, "Win % by format", "Format", "Win % (completed matches)", h=340, pct=True, ylim=[0, 100], hline=50)
with c3:
    ay = D.grouped_record(m, "year")
    f = go.Figure()
    f.add_bar(x=ay.year, y=ay.P, name="Matches played", marker_color="#CFE3D7", yaxis="y2")
    f.add_scatter(x=ay.year, y=ay["Win %"], name="Win %", mode="lines+markers", line=dict(color=T.GREEN, width=3),
                  hovertemplate="%{x}: %{y}% win<extra></extra>")
    f.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, showticklabels=False, range=[0, max(ay.P) * 3]))
    T.plot(f, "Win % and workload by year", "Year", "Win %", h=340, ylim=[0, 105], hline=50, pct=True)

c4, c5 = st.columns(2)
with c4:
    y = m.groupby(["year", "format"]).size().reset_index(name="matches")
    T.plot(px.bar(y, x="year", y="matches", color="format", color_discrete_map=D.FMT_COLORS), "Matches played per year", "Year", "Matches", legend="Format")
with c5:
    gl = D.grouped_record(m, ["format", "location_type"])
    f = px.bar(gl, x="location_type", y="Win %", color="format", barmode="group", color_discrete_map=D.FMT_COLORS, text="Win %", hover_data=["P"])
    f.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
    T.plot(f, "Win % by venue type and format", "Venue type", "Win %", pct=True, ylim=[0, 110], legend="Format", hline=50)

T.section("Opponents and key performers")
c6, c7 = st.columns(2)
with c6:
    go_ = D.grouped_record(m, "opponent")
    go_ = go_[go_.Completed >= 5].sort_values("Win %")
    f = px.bar(go_, y="opponent", x="Win %", orientation="h", color="Win %", color_continuous_scale=T.DIV, range_color=[0, 100],
               text="Win %", hover_data=["P", "W", "L"])
    f.update_traces(texttemplate="%{text:.0f}%", textposition="outside"); f.update_layout(coloraxis_showscale=False)
    f.update_xaxes(range=[0, 118], ticksuffix="%")
    T.plot(f, "Win % by opponent (min 5 completed matches)", "Win %", "Opponent", h=420)
with c7:
    s = m.assign(loc=m.location_type)
    f = px.sunburst(s, path=["format", "loc", "result"], color="result", color_discrete_map={**D.RES_COLORS, "(?)": "#ccc"})
    T.plot(f, "Format → venue type → result", h=420)

c8, c9 = st.columns(2)
with c8:
    top = b.groupby("player").agg(Runs=("runs", "sum"), Inns=("runs", "size"), Out=("is_out", "sum"), Balls=("balls", "sum")).reset_index()
    top["Avg"] = (top.Runs / top.Out.where(top.Out > 0)).round(1); top["SR"] = (100 * top.Runs / top.Balls).round(1)
    top = top.nlargest(10, "Runs").sort_values("Runs")
    f = px.bar(top, y="player", x="Runs", orientation="h", text="Runs", color="Avg", color_continuous_scale=T.SEQ_GREEN, hover_data=["Inns", "SR"])
    f.update_traces(textposition="outside")
    T.plot(f, "Top 10 run-scorers (colour = batting average)", "Runs", "Batter", h=400, cbar="Average")
with c9:
    tw_ = w.groupby("player").agg(Wkts=("wickets", "sum"), Balls=("balls", "sum"), Runs=("runs_conceded", "sum")).reset_index()
    tw_["Econ"] = (6 * tw_.Runs / tw_.Balls).round(2)
    tw_ = tw_.nlargest(10, "Wkts").sort_values("Wkts")
    f = px.bar(tw_, y="player", x="Wkts", orientation="h", text="Wkts", color="Econ", color_continuous_scale=T.DIV_R, hover_data=["Runs"])
    f.update_traces(textposition="outside")
    T.plot(f, "Top 10 wicket-takers (colour = economy)", "Wickets", "Bowler", h=400, cbar="Economy")

T.section("Latest 10 matches")
t = m.sort_values("date", ascending=False).head(10)[["date", "format", "opponent", "tournament", "pak_score", "opp_score", "result", "margin"]]
t = t.assign(date=t.date.dt.strftime("%d %b %Y")).rename(columns={"date": "Date", "format": "Format", "opponent": "Opponent", "tournament": "Tournament",
                                                                  "pak_score": "Pakistan", "opp_score": "Opposition", "result": "Result", "margin": "Margin"})
colr = {"Won": "background-color:#DDF3E7;color:#0B6B3A", "Lost": "background-color:#FBE0E0;color:#B53030", "Tied": "background-color:#FFF1CC", }
st.dataframe(t.style.map(lambda v: colr.get(v, ""), subset=["Result"]), hide_index=True, width="stretch")