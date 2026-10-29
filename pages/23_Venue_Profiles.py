import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Venue Profiles", "Scores, results and Pakistan's best performers at a single ground")
if m.empty:
    st.warning("No matches for these filters."); st.stop()
vc = m.venue.value_counts()
ven = st.selectbox("Ground", vc.index.tolist(), format_func=lambda v: f"{v}  ({vc[v]} matches)")
x = m[m.venue == ven].sort_values("date")
lo = x[x.format != "Test"].copy()
done = x[x.is_completed]
T.kpis([("Matches", len(x), f"{x.date.min():%Y} to {x.date.max():%Y}", "green"),
        ("Pakistan win %", f"{100 * done.is_win.mean():.0f}%" if len(done) else "n/a", f"{int(done.is_win.sum())} won of {len(done)} completed", "green"),
        ("Formats", ", ".join(sorted(x.format.unique())), "", "blue"),
        ("Home / away / neutral", " / ".join(str((x.location_type.str.startswith(k)).sum()) for k in ("Home", "Away", "Neutral")), "", "gold")])
if len(lo):
    lo["first_inns"] = lo.pak_runs.where(lo.pak_batting_order == "Batting first", lo.opp_runs)
    T.section("Scoring (ODI & T20I)")
    s = lo.groupby("format").agg(Matches=("match_id", "count"), AvgFirst=("first_inns", "mean"), AvgPak=("pak_runs", "mean"), AvgOpp=("opp_runs", "mean")).round(0).reset_index()
    st.dataframe(s.rename(columns={"AvgFirst": "Avg 1st-innings score", "AvgPak": "Avg Pakistan score", "AvgOpp": "Avg opposition score"}), hide_index=True, width="stretch")
    r = lo[lo.is_completed].groupby(["format", "pak_batting_order"]).agg(P=("match_id", "count"), W=("is_win", "sum")).reset_index()
    r["Win %"] = (100 * r.W / r.P).round(0)
    T.plot(px.bar(r, x="format", y="Win %", color="pak_batting_order", barmode="group", text="Win %", hover_data=["P"], color_discrete_sequence=[T.GREEN, T.GOLD])
           .update_traces(texttemplate="%{text:.0f}%"), "Win %: batting first vs chasing here", "Format", "Win %", pct=True, ylim=[0, 100], hline=50, h=320)
T.section("Pakistan's top performers here")
ids = set(x.match_id); bb = b[b.match_id.isin(ids)]; ww = w[w.match_id.isin(ids)]
c1, c2 = st.columns(2)
with c1:
    t = bb.groupby("player").agg(Inns=("match_id", "count"), Runs=("runs", "sum"), Outs=("is_out", "sum"), HS=("runs", "max")).reset_index()
    t["Avg"] = (t.Runs / t.Outs.where(t.Outs > 0)).round(1); st.markdown("**Top run-scorers**"); st.dataframe(t.sort_values("Runs", ascending=False).head(10), hide_index=True, width="stretch")
with c2:
    t = ww.groupby("player").agg(Inns=("match_id", "count"), Wkts=("wickets", "sum"), Runs=("runs_conceded", "sum"), Overs=("overs", "sum")).reset_index()
    t["Econ"] = (t.Runs / t.Overs.where(t.Overs > 0)).round(2); st.markdown("**Top wicket-takers**"); st.dataframe(t.sort_values("Wkts", ascending=False).head(10), hide_index=True, width="stretch")
T.section("Match list")
st.dataframe(x[["date", "format", "opponent", "result", "margin", "pak_score", "opp_score", "pak_captain", "pak_coach"]].assign(date=x.date.dt.date), hide_index=True, width="stretch")
