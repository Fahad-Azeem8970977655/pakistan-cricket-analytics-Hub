import plotly.express as px
import streamlit as st

from utils import data as D
from utils import splits as S
from utils import theme as T

D.setup()
m, _, _ = D.filters()
T.hero("Opposition Players", "Who scored runs, took wickets and made dismissals AGAINST Pakistan")
ob, ow, op = D.load_opp()
if ob.empty:
    st.error("No opposition data yet. Run `python scripts/add_opposition_data.py` (see README)."); st.stop()
if m.empty:
    st.warning("No matches for these filters."); st.stop()
ids = set(m.match_id)
ob, ow = D.by_ids(ob, ids), D.by_ids(ow, ids)
st.caption("Who scored runs and took wickets AGAINST Pakistan, for the matches selected in the sidebar. "
           "Names are Cricsheet-style (initials + surname). Stats are only against Pakistan, not career figures.")
mode = st.radio("Group by", ["Player (all)", "Player x format", "Player x opponent team"], horizontal=True)
by = {"Player (all)": ["player"], "Player x format": ["player", "format"], "Player x opponent team": ["player", "opponent"]}[mode]
tab1, tab2, tab4, tab3 = st.tabs(["Batters vs Pakistan", "Bowlers vs Pakistan", "Fielders vs Pakistan", "Player list"])

with tab1:
    if ob.empty: st.info("No data.")
    else:
        mi = st.slider("Minimum innings", 1, 20, 5, key="ob_min")
        t = S.batting_table(ob, by)
        t = t[t.Inns >= mi].sort_values("Runs", ascending=False)
        st.dataframe(t, hide_index=True, width="stretch", height=380)
        top = t.head(15)
        if not top.empty:
            T.plot(px.bar(top, x="player", y="Runs", color=by[1] if len(by) > 1 else None, text="Runs"), "Most runs against Pakistan",
                   "Opposition batter", "Runs vs Pakistan", legend=by[1].title() if len(by) > 1 else None, h=430)
        T.section("Highest individual scores against Pakistan")
        hs = ob.sort_values("runs", ascending=False).head(15)[["player", "opponent", "format", "date", "runs", "balls", "fours", "sixes", "is_out"]]
        st.dataframe(hs.assign(date=hs.date.dt.date), hide_index=True, width="stretch")

with tab2:
    if ow.empty: st.info("No data.")
    else:
        mo = st.slider("Minimum overs bowled", 1, 100, 20, key="ow_min")
        t = S.bowling_table(ow, by)
        t = t[t._balls >= mo * 6].sort_values("Wkts", ascending=False)
        st.dataframe(t.drop(columns=["_balls"]), hide_index=True, width="stretch", height=380)
        top = t.head(15)
        if not top.empty:
            T.plot(px.bar(top, x="player", y="Wkts", color=by[1] if len(by) > 1 else None, text="Wkts"), "Most wickets against Pakistan",
                   "Opposition bowler", "Wickets vs Pakistan", legend=by[1].title() if len(by) > 1 else None, h=430)
        T.section("Best bowling figures against Pakistan")
        bb = ow.sort_values(["wickets", "runs_conceded"], ascending=[False, True]).head(15)[
            ["player", "opponent", "format", "date", "overs", "maidens", "runs_conceded", "wickets"]]
        st.dataframe(bb.assign(date=bb.date.dt.date), hide_index=True, width="stretch")

with tab4:
    of = D.by_ids(D.load_opp_fielding(), ids)
    if of.empty:
        st.info("No opposition fielding data. Re-run the collector script (v2) and scripts/add_opposition_data.py.")
    else:
        subs = st.checkbox("Include substitute fielders", value=False)
        if not subs: of = of[~of.substitute.astype(bool)]
        cols = ["catches", "caught_and_bowled", "stumpings", "runouts_direct", "runouts_assisted"]
        t = of.groupby(by, dropna=False).agg(Matches_with_a_dismissal=("match_id", "nunique"), **{c: (c, "sum") for c in cols}).reset_index()
        t["Run-outs"] = t.runouts_direct + t.runouts_assisted
        t["Total"] = t.catches + t.caught_and_bowled + t.stumpings + t["Run-outs"]
        t = t.rename(columns={"catches": "Catches", "caught_and_bowled": "C&B", "stumpings": "Stumpings",
                              "runouts_direct": "RO direct", "runouts_assisted": "RO assisted"}).sort_values("Total", ascending=False)
        st.caption("Dismissals the opposition's fielders made against Pakistan. 'Matches with a dismissal' only counts "
                   "matches where that fielder took at least one, not all matches played.")
        st.dataframe(t, hide_index=True, width="stretch", height=380)
        top = t.head(15)
        if not top.empty:
            long = top.melt(id_vars=by, value_vars=["Catches", "C&B", "Stumpings", "Run-outs"], var_name="type", value_name="n")
            T.plot(px.bar(long, x="player", y="n", color="type"), "Most dismissals by fielders against Pakistan", "Opposition fielder", "Dismissals", legend="Type", h=430)

with tab3:
    keep = set(ob.player) | set(ow.player)
    pl = op[op.player.isin(keep)]
    c1, c2 = st.columns(2)
    team = c1.multiselect("Team (empty = all)", sorted(pl.opponent.unique()))
    q = c2.text_input("Search player")
    if team: pl = pl[pl.opponent.isin(team)]
    if q: pl = pl[pl.player.str.contains(q, case=False)]
    st.dataframe(pl, hide_index=True, width="stretch", height=450,
                 column_config={"cricinfo_url": st.column_config.LinkColumn("Cricinfo", display_text="profile")})
    st.caption(f"{len(pl)} players")
