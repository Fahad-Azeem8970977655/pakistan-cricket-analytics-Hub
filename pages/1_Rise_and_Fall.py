import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Rise & Fall", "How Pakistan's results, scoring rate and form have moved year by year")
if m.empty:
    st.warning("No matches for these filters."); st.stop()

o = D.overall(m)
ay = D.grouped_record(m, "year").sort_values("year")
best, worst = ay.loc[ay["Win %"].idxmax()], ay.loc[ay["Win %"].idxmin()]
T.kpis([("Overall win %", D.fmt_pct(o["Win %"]), f"{int(o.W)}W {int(o.L)}L", "green"),
        ("Best year", f"{int(best.year)}", f"{best['Win %']}% from {int(best.Completed)} matches", "green", "up"),
        ("Worst year", f"{int(worst.year)}", f"{worst['Win %']}% from {int(worst.Completed)} matches", "red", "down"),
        ("Latest year", f"{int(ay.iloc[-1].year)}", f"{ay.iloc[-1]['Win %']}% win rate", "gold")], per_row=4)

T.section("Win % by year")
g = D.grouped_record(m, ["year", "format"])
allg = D.grouped_record(m, "year")
f = px.line(g, x="year", y="Win %", color="format", markers=True, color_discrete_map=D.FMT_COLORS, hover_data=["P", "W", "L"])
f.add_trace(go.Scatter(x=allg.year, y=allg["Win %"], name="All formats", line=dict(dash="dash", color="#444", width=3)))
T.plot(f, "Win % by year and format (dashed = all formats)", "Year", "Win %", pct=True, ylim=[0, 100], hline=50, legend="Format", h=400)

c1, c2 = st.columns(2)
with c1:
    r = m.groupby(["year", "result"]).size().reset_index(name="n")
    T.plot(px.bar(r, x="year", y="n", color="result", color_discrete_map=D.RES_COLORS), "Results per year", "Year", "Matches", legend="Result")
with c2:
    p = g.pivot(index="format", columns="year", values="Win %")
    f = px.imshow(p, text_auto=".0f", color_continuous_scale=T.DIV, zmin=0, zmax=100, aspect="auto")
    T.plot(f, "Win % heatmap (format × year)", "Year", "Format", cbar="Win %")

T.section("Rolling form")
k1, k2 = st.columns(2)
n = k1.slider("Rolling window (completed matches)", 5, 40, 15)
fm = k2.selectbox("Format", ["All"] + sorted(m.format.unique()))
s = m[m.result.isin(["Won", "Lost", "Tied"])].sort_values("date")
if fm != "All": s = s[s.format == fm]
s = s.assign(win=(s.result == "Won").astype(int))
s["roll"] = s.win.rolling(n, min_periods=n).mean() * 100
if s["roll"].notna().any():
    f = px.area(s, x="date", y="roll", hover_data=["opponent", "result"])
    f.update_traces(line_color=T.GREEN, fillcolor="rgba(11,107,58,.15)")
    T.plot(f, f"Rolling win % over the last {n} completed matches ({fm})", "Date", "Win %", pct=True, ylim=[0, 100], hline=50)
else:
    st.info("Not enough matches for this window.")

T.section("Scoring rate and phases", "ODI & T20I")
lo = m[m.format != "Test"]
if lo.empty:
    st.info("Select ODI or T20I to see this section.")
else:
    d1, d2 = st.columns(2)
    rr = lo.groupby("year")[["pak_run_rate", "opp_run_rate"]].mean().reset_index().melt("year", var_name="side", value_name="rr")
    rr["side"] = rr.side.map({"pak_run_rate": "Pakistan batting", "opp_run_rate": "Opposition batting"})
    f = px.line(rr, x="year", y="rr", color="side", markers=True, color_discrete_sequence=[T.GREEN, "#D64545"])
    with d1: T.plot(f, "Average run rate per over", "Year", "Runs per over", legend="Side")
    ph = lo.groupby("year")[["pak_powerplay_runs", "pak_middle_runs", "pak_death_runs"]].mean().reset_index().melt("year")
    ph["variable"] = ph.variable.map({"pak_powerplay_runs": "Powerplay", "pak_middle_runs": "Middle overs", "pak_death_runs": "Death overs"})
    with d2: T.plot(px.bar(ph, x="year", y="value", color="variable", barmode="group"), "Pakistan: average runs per innings by phase", "Year", "Average runs", legend="Phase")

T.section("How reliable is each year's win %?")
ci = D.grouped_record(m, "year")
f = go.Figure()
f.add_trace(go.Scatter(x=list(ci.year) + list(ci.year[::-1]), y=list(ci["CI high"]) + list(ci["CI low"][::-1]), fill="toself",
                       fillcolor="rgba(11,107,58,0.18)", line=dict(width=0), hoverinfo="skip", name="95% interval"))
f.add_trace(go.Scatter(x=ci.year, y=ci["Win %"], mode="lines+markers", name="Win %", line=dict(color=T.GREEN),
                       customdata=ci[["Completed"]], hovertemplate="%{x}: %{y}% (n=%{customdata[0]})<extra></extra>"))
T.plot(f, "Win % per year with 95% confidence band (wide band = few matches)", "Year", "Win %", pct=True, ylim=[0, 100], hline=50)
small = ci[ci.Completed < 10]
if len(small): st.caption("Years with fewer than 10 completed matches in the current filter: " + ", ".join(map(str, small.year)))

if m.pak_captain.notna().any():
    T.section("Win % by captain")
    cg = D.grouped_record(m.dropna(subset=["pak_captain"]), ["pak_captain", "format"])
    T.plot(px.bar(cg, x="pak_captain", y="Win %", color="format", barmode="group", color_discrete_map=D.FMT_COLORS, hover_data=["P"]),
           "Win % under each captain", "Captain", "Win %", pct=True, ylim=[0, 100], legend="Format")
