from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

DATA = Path(__file__).resolve().parent.parent / "data"
D.setup()
m, b, w = D.filters()
T.hero("Match One-Pager", "Scorecard, run-rate worm, partnerships, captain and coach for any match")
if m.empty:
    st.warning("No matches for these filters."); st.stop()
x = m.sort_values("date", ascending=False)
lab = x.apply(lambda r: f"{r.date:%d %b %Y} | {r.format} | v {r.opponent} | {r.result}", axis=1)
pick = st.selectbox("Match", lab.index, format_func=lambda i: lab[i])
r = x.loc[pick]; mid = r.match_id
st.subheader(f"Pakistan v {r.opponent}, {r.format}")
st.caption(f"{r.venue}, {r.city} | {r.tournament} {('| ' + str(r.stage_detail)) if pd.notna(r.stage_detail) else ''}")
T.kpis([("Result", r.result, str(r.margin) if pd.notna(r.margin) else "", "green" if r.is_win else "red" if r.is_loss else "grey"),
        ("Pakistan", str(r.pak_score), "", "green"), (r.opponent, str(r.opp_score), "", "blue"),
        ("Captain", str(r.pak_captain) if pd.notna(r.pak_captain) else "n/a", "", "gold"),
        ("Coach", str(r.pak_coach) if pd.notna(r.pak_coach) else "n/a", "", "gold")], per_row=5)
st.write(f"**Toss:** {r.toss_winner} chose to {r.toss_decision}.  **Player of the match:** {r.player_of_match if pd.notna(r.player_of_match) else 'n/a'}")

T.section("Pakistan scorecard")
c1, c2 = st.columns(2)
bb = b[b.match_id == mid].sort_values(["innings_no", "batting_position"]) if "batting_position" in b else b[b.match_id == mid]
bw_ = w[w.match_id == mid]
with c1:
    st.markdown("**Batting**"); st.dataframe(bb[[c for c in ["innings_no", "batting_position", "player", "runs", "balls", "fours", "sixes", "strike_rate", "dismissal"] if c in bb]], hide_index=True, width="stretch")
with c2:
    st.markdown("**Bowling**"); st.dataframe(bw_[[c for c in ["innings_no", "player", "overs", "maidens", "runs_conceded", "wickets", "economy"] if c in bw_]], hide_index=True, width="stretch")

T.section("Run-rate worm")
try:
    ov = pd.read_csv(DATA / "pak_overs.csv"); ov = ov[ov.match_id.astype(str) == str(mid)]
    if ov.empty: st.caption("No over-by-over data for this match.")
    else:
        ov["Innings"] = "Inns " + ov.innings_no.astype(str) + " - " + ov.side
        f = px.line(ov, x="over", y="cum_runs", color="Innings", markers=len(ov) < 120, color_discrete_sequence=T.COLORWAY)
        wk = ov[ov.wickets > 0]
        f.add_scatter(x=wk.over, y=wk.cum_runs, mode="markers", marker=dict(symbol="x", size=9, color="#D64545"), name="Wicket", hovertext=wk.wickets.astype(str) + " wkt(s)")
        T.plot(f, "Cumulative runs by over (red x = wicket)", "Over", "Runs", h=380)
except FileNotFoundError:
    st.caption("data/pak_overs.csv not found.")

T.section("Partnerships")
try:
    pt = pd.read_csv(DATA / "pak_partnerships.csv"); pt = pt[pt.match_id.astype(str) == str(mid)]
    if pt.empty: st.caption("No partnership data.")
    else:
        pt["Pair"] = pt.batter1 + " & " + pt.batter2
        T.plot(px.bar(pt, x="wicket_no", y="runs", text="runs", hover_data=["Pair", "balls"], color="innings_no", color_continuous_scale=T.SEQ_GREEN),
               "Partnership runs by wicket", "Wicket", "Runs", h=320)
        st.dataframe(pt[["innings_no", "wicket_no", "Pair", "runs", "balls", "unbroken"]], hide_index=True, width="stretch")
except FileNotFoundError:
    st.caption("data/pak_partnerships.csv not found.")
