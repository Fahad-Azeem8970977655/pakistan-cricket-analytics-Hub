import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Match Explorer", "Search every match, download the table and open a full scorecard")
q = st.text_input("Search opponent, tournament, venue or player of the match")
x = m
if q:
    t = q.lower()
    x = m[m[["opponent", "tournament", "venue", "player_of_match"]].fillna("").apply(lambda c: c.str.lower().str.contains(t)).any(axis=1)]
cols = ["date", "format", "opponent", "tournament", "stage", "venue", "location_type", "pak_score", "opp_score", "result", "margin", "player_of_match"]
st.dataframe(x.sort_values("date", ascending=False)[cols], hide_index=True, width="stretch", height=380)
st.download_button("Download filtered matches (CSV)", x.to_csv(index=False).encode(), "pakistan_matches_filtered.csv", "text/csv")

if x.empty:
    st.stop()
T.section("Scorecard")
opts = x.sort_values("date", ascending=False)
lab = opts.apply(lambda r: f"{r.date:%d %b %Y} · {r.format} · v {r.opponent} · {r.result}", axis=1)
pick = st.selectbox("Match", range(len(opts)), format_func=lambda i: lab.iloc[i])
r = opts.iloc[pick]
T.kpis([("Pakistan", r.pak_score, "", "green"), (r.opponent, r.opp_score, "", "red"), ("Result", r.result, "", "gold"),
        ("Margin", r.margin if isinstance(r.margin, str) else "-", "", "blue")], per_row=4)
st.caption(f"{r.tournament} · {r.venue}, {r.city} · Toss: {r.toss_winner} chose to {r.toss_decision} · Player of the match: {r.player_of_match}")
t1, t2 = st.tabs(["Pakistan batting", "Pakistan bowling"])
t1.dataframe(b[b.match_id == r.match_id][["innings_no", "batting_position", "player", "runs", "balls", "fours", "sixes", "strike_rate", "dismissal", "dismissed_by"]], hide_index=True, width="stretch")
t2.dataframe(w[w.match_id == r.match_id][["innings_no", "player", "overs", "maidens", "runs_conceded", "wickets", "economy"]], hide_index=True, width="stretch")
with st.expander("Playing XIs"):
    st.write("**Pakistan:**", r.pak_xi); st.write(f"**{r.opponent}:**", r.opp_xi)
