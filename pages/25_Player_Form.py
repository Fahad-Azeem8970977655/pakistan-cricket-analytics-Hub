import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Player Form Tracker", "Rolling form for batters and bowlers over their last N innings")
if b.empty:
    st.warning("No data for these filters."); st.stop()
mode = st.radio("Role", ["Batting", "Bowling"], horizontal=True)
n = st.slider("Window (innings)", 3, 20, 10)
src = b if mode == "Batting" else w
cnt = src.player.value_counts(); players = cnt[cnt >= n].index.tolist()
if not players:
    st.info("No player has enough innings for this window. Lower it."); st.stop()
who = st.multiselect("Players", players, default=players[:1], max_selections=5)
if not who: st.stop()
d = src[src.player.isin(who)].copy(); d["date"] = pd.to_datetime(d["date"]); d = d.sort_values(["player", "date"])
def _roll(q):
    q = q.copy()
    if mode == "Batting":
        q["Form"] = q.runs.rolling(n).sum() / q.is_out.astype(int).rolling(n).sum().where(lambda v: v > 0)
        q["SR"] = 100 * q.runs.rolling(n).sum() / q.balls.rolling(n).sum()
    else:
        q["Form"] = q.runs_conceded.rolling(n).sum() / q.overs.rolling(n).sum().where(lambda v: v > 0)
        q["Wkts"] = q.wickets.rolling(n).sum()
    return q


d = pd.concat([_roll(q) for _, q in d.groupby("player")]) if len(d) else d
ylab, key = (f"Average, last {n} innings", "Form") if mode == "Batting" else (f"Economy, last {n} innings", "Form")
d = d.dropna(subset=["Form"])
f = px.line(d, x="date", y=key, color="player", color_discrete_sequence=T.COLORWAY, hover_data=["opponent", "format"])
T.plot(f, f"Rolling {ylab.lower()}", "Date", ylab, h=420)
last = d.groupby("player").tail(1)[["player", "date", key]].rename(columns={key: ylab}); last["date"] = last.date.dt.date
T.section("Current form"); st.dataframe(last.round(2), hide_index=True, width="stretch")
T.note("Rolling window follows the sidebar filters (format, years). Pick one format for a cleaner trend.")
