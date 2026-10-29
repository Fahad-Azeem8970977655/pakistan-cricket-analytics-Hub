import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Toss & Chase", "Does winning the toss, batting first or chasing really change Pakistan's results?")
if m.empty:
    st.warning("No matches for these filters."); st.stop()
x = m[m.is_completed].copy()
if x.empty:
    st.warning("No completed matches for these filters."); st.stop()


def wp(df, by):
    g = df.groupby(by).agg(P=("match_id", "count"), W=("is_win", "sum")).reset_index()
    g["Win %"] = (100 * g.W / g.P).round(1); return g


tw, tl = x[x.pak_won_toss], x[~x.pak_won_toss]
T.kpis([("Win % winning toss", f"{100 * tw.is_win.mean():.0f}%" if len(tw) else "n/a", f"{len(tw)} matches", "green"),
        ("Win % losing toss", f"{100 * tl.is_win.mean():.0f}%" if len(tl) else "n/a", f"{len(tl)} matches", "red"),
        ("Win % batting first", f"{100 * x[x.pak_batting_order == 'Batting first'].is_win.mean():.0f}%", f"{(x.pak_batting_order == 'Batting first').sum()} matches", "blue"),
        ("Win % chasing", f"{100 * x[x.pak_batting_order == 'Batting second'].is_win.mean():.0f}%", f"{(x.pak_batting_order == 'Batting second').sum()} matches", "gold")])

c1, c2 = st.columns(2)
a = wp(x.assign(Toss=x.pak_won_toss.map({True: "Won toss", False: "Lost toss"})), ["format", "Toss"])
with c1: T.plot(px.bar(a, x="format", y="Win %", color="Toss", barmode="group", text="Win %", hover_data=["P"], color_discrete_sequence=[T.GREEN, "#C3CBD0"])
                .update_traces(texttemplate="%{text:.0f}%"), "Win % by toss result", "Format", "Win %", pct=True, ylim=[0, 100], hline=50, h=360)
c2d = wp(x.rename(columns={"pak_batting_order": "Innings"}), ["format", "Innings"])
with c2: T.plot(px.bar(c2d, x="format", y="Win %", color="Innings", barmode="group", text="Win %", hover_data=["P"], color_discrete_sequence=[T.GREEN, T.GOLD])
                .update_traces(texttemplate="%{text:.0f}%"), "Win %: batting first vs chasing", "Format", "Win %", pct=True, ylim=[0, 100], hline=50, h=360)

T.section("What Pakistan chose after winning the toss")
cd = wp(x[x.pak_won_toss & x.toss_decision.notna()].assign(Decision=lambda d: d.toss_decision.map({"bat": "Chose to bat", "field": "Chose to field"})), ["format", "Decision"])
if not cd.empty:
    T.plot(px.bar(cd, x="format", y="Win %", color="Decision", barmode="group", text="Win %", hover_data=["P"], color_discrete_sequence=[T.GREEN, T.GOLD])
           .update_traces(texttemplate="%{text:.0f}%"), "Win % by toss decision", "Format", "Win %", pct=True, ylim=[0, 100], hline=50, h=340)

T.section("By venue type and by ground")
vt = wp(x.assign(Innings=x.pak_batting_order), ["location_type", "Innings"])
T.plot(px.bar(vt, x="location_type", y="Win %", color="Innings", barmode="group", text="Win %", hover_data=["P"], color_discrete_sequence=[T.GREEN, T.GOLD])
       .update_traces(texttemplate="%{text:.0f}%"), "Win % batting first vs chasing, by venue type", "Venue type", "Win %", pct=True, ylim=[0, 100], hline=50, h=340)
floor = st.slider("Minimum matches at a ground", 3, 20, 6)
vg = x.groupby("venue").agg(P=("match_id", "count")).reset_index(); keep = vg[vg.P >= floor].venue
vv = wp(x[x.venue.isin(keep)].assign(Innings=x.pak_batting_order), ["venue", "Innings"])
if not vv.empty:
    fg = px.bar(vv, y="venue", x="Win %", color="Innings", barmode="group", orientation="h", hover_data=["P"], color_discrete_sequence=[T.GREEN, T.GOLD])
    fg.update_xaxes(ticksuffix="%")
    T.plot(fg, "Ground-by-ground: batting first vs chasing", "Win %", "Ground", h=max(360, 48 * keep.nunique() + 120))
T.note("Completed matches only. Small samples swing a lot, so look at the match counts in the hover box before drawing conclusions.")