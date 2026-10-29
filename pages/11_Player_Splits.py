import plotly.express as px
import streamlit as st

from utils import data as D
from utils import splits as S
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Player Splits", "SENA, England, Home and Away: how each player performs in different conditions")
st.caption("One match can sit in several splits (a Test at Lord's is in All, Away, England and SENA), "
           "so never add different splits together. SENA = South Africa, England, New Zealand, Australia "
           "by venue country, so neutral-venue games played there count too. Home (Pakistan) is games in Pakistan; "
           "Home (incl. UAE) adds Pakistan's 'home' games in the UAE.")
if b.empty or w.empty:
    st.warning("No data for these filters."); st.stop()

pick = st.multiselect("Splits to compare", list(S.SPLITS),
                      default=["All matches", "Home (Pakistan)", "Away", "SENA", "England"])
if not pick:
    st.info("Pick at least one split."); st.stop()
mode = st.radio("Group by", ["Per format", "All formats combined"], horizontal=True)
by = ["player", "format", "split"] if mode == "Per format" else ["player", "split"]

bg = S.expand(S.add_geo(b, m), pick)
wg = S.expand(S.add_geo(w, m), pick)
bt = S.batting_table(bg, by)
bw = S.bowling_table(wg, by)


def chart(tbl, ycols, weight, title_prefix, min_col, min_val):
    """Grouped bar: top players (by `weight`) across the chosen splits."""
    c1, c2 = st.columns(2)
    metric = c1.selectbox("Chart metric", ycols, key=f"{title_prefix}_metric")
    t = tbl
    if mode == "Per format":
        f = c2.selectbox("Format", D.FORMATS, key=f"{title_prefix}_fmt")
        t = t[t.format == f]
    t = t[t[min_col] >= min_val]
    if t.empty:
        st.info("Nothing meets the minimum for this selection."); return
    n = st.slider("Players shown", 5, 25, 12, key=f"{title_prefix}_n")
    top = t.groupby("player")[weight].sum().nlargest(n).index
    t = t[t.player.isin(top)].dropna(subset=[metric])
    f = px.bar(t, x="player", y=metric, color="split", barmode="group", text=metric)
    f.update_traces(textposition="outside", textfont_size=9)
    T.plot(f, f"{title_prefix}: {metric} by split", "Player", metric, legend="Split", h=460)


tab1, tab2, tab3 = st.tabs(["Batting", "Bowling", "One player, all splits"])

with tab1:
    mi = st.slider("Minimum innings", 1, 30, 5, key="bat_min")
    shown = bt[bt.Inns >= mi].sort_values(["Runs"], ascending=False)
    st.dataframe(shown, hide_index=True, width="stretch", height=420)
    ycols = ["Avg", "SR", "Runs", "Bdry %"] + (["Dot %"] if "Dot %" in bt.columns else [])
    chart(bt, ycols, "Runs", "Batting", "Inns", mi)
    if "Dot %" not in bt.columns:
        st.info("Batter dot balls are not in the data yet. Re-run scripts/build_pakistan_dataset_v3.py --refresh "
                "(patched to record dot_balls per batter) and copy the new CSVs into data/. "
                "Bowler dot balls are already available in the Bowling tab.")

with tab2:
    mo = st.slider("Minimum overs bowled", 1, 150, 20, key="bowl_min")
    shown = bw[bw._balls >= mo * 6].sort_values("Wkts", ascending=False).drop(columns=["_balls"])
    st.dataframe(shown, hide_index=True, width="stretch", height=420)
    chart(bw, ["Avg", "Econ", "SR", "Dot %", "Wkts"], "Wkts", "Bowling", "_balls", mo * 6)

with tab3:
    ids = sorted(set(b.player) | set(w.player))
    who = st.selectbox("Player", ids, index=ids.index("Babar Azam") if "Babar Azam" in ids else 0)
    allb = S.batting_table(S.expand(S.add_geo(b[b.player == who], m)), ["format", "split"])
    allw = S.bowling_table(S.expand(S.add_geo(w[w.player == who], m)), ["format", "split"])
    T.section(f"{who}: batting")
    st.dataframe(allb, hide_index=True, width="stretch")
    if not allw.empty:
        T.section(f"{who}: bowling")
        st.dataframe(allw.drop(columns=["_balls"]), hide_index=True, width="stretch")
