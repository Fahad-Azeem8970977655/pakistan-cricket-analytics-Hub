from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Phase Analysis", "Powerplay, middle overs and death overs, plus batter vs bowler matchups, from every delivery")
FILE = Path(__file__).resolve().parent.parent / "data" / "pak_deliveries.csv.gz"
if not FILE.exists():
    st.error("`data/pak_deliveries.csv.gz` is missing. Run `python scripts/build_deliveries.py` (uses the Cricsheet ZIPs the main build already downloaded), then restart the app.")
    st.stop()


@st.cache_data(show_spinner="Loading deliveries...")
def load_deliveries():
    d = pd.read_csv(FILE, dtype={"match_id": str})
    for c in ("extras_type", "wicket_kind", "player_out"): d[c] = d[c].fillna("")
    return d


dl = load_deliveries()
dl = dl[dl.match_id.isin(set(m.match_id.astype(str)))]
if dl.empty:
    st.warning("No deliveries for these filters."); st.stop()
shaped = dl[dl.format != "Test"]
fmts = [f for f in ("ODI", "T20I") if f in set(shaped.format)]
c1, c2 = st.columns([1, 2])
with c1:
    fmt = st.radio("Format", fmts + ["Test"] if "Test" in set(dl.format) else fmts, horizontal=True)
d = dl[dl.format == fmt]
nm = d.match_id.nunique()
T.kpis([("Matches", nm, fmt, "green"), ("Deliveries", f"{len(d):,}", "all innings in view", "blue"),
        ("Wickets", int(d.is_wicket.sum()), "both sides", "gold"), ("Pakistan boundaries", int(d[d.pak_batting == 1][["is_four", "is_six"]].sum().sum()), "fours and sixes", "grey")])


def agg_bat(x, by):
    g = x.groupby(by).agg(Balls=("is_legal", "sum"), Runs=("runs_batter", "sum"), Faced=("is_batter_dot", "size"), Dots=("is_batter_dot", "sum"),
                          Fours=("is_four", "sum"), Sixes=("is_six", "sum"), Outs=("is_wicket", "sum")).reset_index()
    return g


def tidy_bat(g):
    g["SR"] = (100 * g.Runs / g.Balls.where(g.Balls > 0)).round(1); g["Dot %"] = (100 * g.Dots / g.Faced.where(g.Faced > 0)).round(1)
    g["Bdry %"] = (100 * (g.Fours + g.Sixes) / g.Faced.where(g.Faced > 0)).round(1); g["Avg"] = (g.Runs / g.Outs.where(g.Outs > 0)).round(1); return g


# ---- 1. team by phase ------------------------------------------------------------------------------------------
if fmt != "Test":
    T.section("Team scoring and wicket-taking by phase")
    inns = d.groupby(["match_id", "innings_no", "pak_batting", "phase"]).agg(runs=("runs_total", "sum"), legal=("is_legal", "sum"), wk=("is_wicket", "sum")).reset_index()
    ph = inns.groupby(["pak_batting", "phase"]).agg(runs=("runs", "sum"), legal=("legal", "sum"), wk=("wk", "sum"), n=("match_id", "count")).reset_index()
    ph["Run rate"] = (6 * ph.runs / ph.legal).round(2); ph["Wkts per innings"] = (ph.wk / ph.n).round(2)
    ph["Side"] = ph.pak_batting.map({1: "Pakistan batting", 0: "Pakistan bowling (opposition scoring)"})
    order = ["Powerplay", "Middle", "Death"]
    ca, cb = st.columns(2)
    with ca:
        f = px.bar(ph, x="phase", y="Run rate", color="Side", barmode="group", text="Run rate", category_orders={"phase": order},
                   color_discrete_sequence=[T.GOLD, T.GREEN])
        f.update_layout(legend=dict(orientation="h", y=-0.22, x=0, title_text=""), margin=dict(b=90))
        T.plot(f, "Run rate by phase (runs per over)", "Phase", "Runs per over", h=380)
    with cb:
        f = px.bar(ph, x="phase", y="Wkts per innings", color="Side", barmode="group", text="Wkts per innings", category_orders={"phase": order},
                   color_discrete_sequence=[T.GOLD, T.GREEN])
        f.update_layout(legend=dict(orientation="h", y=-0.22, x=0, title_text=""), margin=dict(b=90))
        T.plot(f, "Wickets lost per innings by phase", "Phase", "Wickets per innings", h=380)
    T.note("'Pakistan batting' is Pakistan's own scoring; the other bars are what Pakistan's bowlers concede. Wickets for 'Pakistan batting' are Pakistan wickets lost.")

# ---- 2. over-by-over curve ----------------------------------------------------------------------------------------
T.section("Run rate over by over")
ov = d.groupby(["pak_batting", "over"]).agg(runs=("runs_total", "sum"), inn=("innings_no", "size")).reset_index()
cnt = d.groupby(["pak_batting", "over"]).apply(lambda g: g[["match_id", "innings_no"]].drop_duplicates().shape[0], include_groups=False).rename("n").reset_index()
ov = ov.merge(cnt, on=["pak_batting", "over"]); ov = ov[ov.n >= 5]
ov["Avg runs in over"] = (ov.runs / ov.n).round(2); ov["Side"] = ov.pak_batting.map({1: "Pakistan batting", 0: "Pakistan bowling"})
f = px.line(ov, x="over", y="Avg runs in over", color="Side", markers=True, color_discrete_sequence=[T.GOLD, T.GREEN])
f.update_layout(legend=dict(orientation="h", y=-0.25, x=0, title_text=""), margin=dict(b=90))
T.plot(f, "Average runs scored in each over", "Over", "Runs", h=380)

# ---- 3. batters / bowlers by phase ---------------------------------------------------------------------------------
if fmt != "Test":
    T.section("Players by phase")
    ph_pick = st.radio("Phase", ["Powerplay", "Middle", "Death"], horizontal=True, index=2)
    tb, tw = st.tabs(["Pakistan batters", "Pakistan bowlers"])
    with tb:
        floor = st.slider("Minimum balls faced", 20, 300, 60, step=10, key="bf")
        g = tidy_bat(agg_bat(d[(d.pak_batting == 1) & (d.phase == ph_pick)], "batter")); g = g[g.Balls >= floor].sort_values("SR", ascending=False)
        if g.empty: st.info("Nobody has faced that many balls in this phase. Lower the minimum.")
        else:
            f = px.bar(g.head(15).sort_values("SR"), x="SR", y="batter", orientation="h", text="SR", hover_data=["Balls", "Runs", "Dot %", "Bdry %"], color_discrete_sequence=[T.GREEN])
            T.plot(f, f"Strike rate in the {ph_pick.lower()} (min {floor} balls)", "Strike rate", "Batter", h=max(320, 30 * min(15, len(g)) + 120))
            st.dataframe(g[["batter", "Balls", "Runs", "SR", "Dot %", "Bdry %", "Outs", "Avg"]].rename(columns={"batter": "Batter"}), hide_index=True, width="stretch")
    with tw:
        floor = st.slider("Minimum balls bowled", 20, 300, 60, step=10, key="bw")
        x = d[(d.pak_batting == 0) & (d.phase == ph_pick)]
        g = x.groupby("bowler").agg(Balls=("is_legal", "sum"), Runs=("runs_total", "sum"), Wkts=("bowler_wicket", "sum"),
                                    Dots=("is_dot_ball" if "is_dot_ball" in x else "is_batter_dot", "sum"), Faced=("is_batter_dot", "size")).reset_index()
        g["Econ"] = (6 * g.Runs / g.Balls.where(g.Balls > 0)).round(2); g["Dot %"] = (100 * g.Dots / g.Faced).round(1)
        g["Balls/wkt"] = (g.Balls / g.Wkts.where(g.Wkts > 0)).round(1); g = g[g.Balls >= floor].sort_values("Econ")
        if g.empty: st.info("Nobody has bowled that many balls in this phase. Lower the minimum.")
        else:
            f = px.bar(g.head(15).sort_values("Econ", ascending=False), x="Econ", y="bowler", orientation="h", text="Econ", hover_data=["Balls", "Wkts", "Dot %"], color_discrete_sequence=[T.GREEN])
            T.plot(f, f"Economy in the {ph_pick.lower()} (min {floor} balls, lower is better)", "Runs per over", "Bowler", h=max(320, 30 * min(15, len(g)) + 120))
            st.dataframe(g[["bowler", "Balls", "Runs", "Wkts", "Econ", "Dot %", "Balls/wkt"]].rename(columns={"bowler": "Bowler"}), hide_index=True, width="stretch")

# ---- 4. matchups --------------------------------------------------------------------------------------------------------
T.section("Batter vs bowler matchups")
st.caption("Uses every delivery in the current filters, all formats you have selected in the sidebar. Small samples are common here: look at the balls column.")
mode = st.radio("Show", ["A Pakistan batter against bowlers", "A Pakistan bowler against batters"], horizontal=True)
a = dl
if mode.startswith("A Pakistan batter"):
    cnt = a[a.pak_batting == 1].batter.value_counts(); who = st.selectbox("Pakistan batter", cnt.index.tolist())
    x = a[(a.pak_batting == 1) & (a.batter == who)]
    g = x.groupby("bowler").agg(Balls=("is_legal", "sum"), Runs=("runs_batter", "sum"), Dots=("is_batter_dot", "sum"), Faced=("is_batter_dot", "size"),
                                Outs=("is_wicket", "sum"), Fours=("is_four", "sum"), Sixes=("is_six", "sum")).reset_index()
    g["Out when"] = g.bowler; label = "Bowler"; key = "bowler"
    outs = x[(x.is_wicket == 1) & (x.player_out == who)].groupby("bowler").size()
    g["Outs"] = g.bowler.map(outs).fillna(0).astype(int)
else:
    cnt = a[a.pak_batting == 0].bowler.value_counts(); who = st.selectbox("Pakistan bowler", cnt.index.tolist())
    x = a[(a.pak_batting == 0) & (a.bowler == who)]
    g = x.groupby("batter").agg(Balls=("is_legal", "sum"), Runs=("runs_batter", "sum"), Dots=("is_batter_dot", "sum"), Faced=("is_batter_dot", "size"),
                                Fours=("is_four", "sum"), Sixes=("is_six", "sum")).reset_index()
    outs = x[x.bowler_wicket == 1].groupby("player_out").size(); g["Outs"] = g.batter.map(outs).fillna(0).astype(int); label = "Batter"; key = "batter"
mn = st.slider("Minimum balls", 1, 60, 12, key="mm")
g = g[g.Balls >= mn].copy()
g["SR"] = (100 * g.Runs / g.Balls.where(g.Balls > 0)).round(1); g["Dot %"] = (100 * g.Dots / g.Faced).round(1)
g["Avg"] = (g.Runs / g.Outs.where(g.Outs > 0)).round(1)
if g.empty: st.info("No opponent with that many balls. Lower the minimum.")
else:
    g = g.sort_values("Balls", ascending=False)
    st.dataframe(g[[key, "Balls", "Runs", "Outs", "SR", "Avg", "Dot %", "Fours", "Sixes"]].rename(columns={key: label}).head(40), hide_index=True, width="stretch")

# ---- 5. where wickets fall ------------------------------------------------------------------------------------------------
T.section("Where Pakistan's bowlers take wickets")
wk = d[(d.pak_batting == 0) & (d.bowler_wicket == 1)]
if len(wk):
    g = wk.groupby("over").size().reset_index(name="Wickets")
    T.plot(px.bar(g, x="over", y="Wickets", color_discrete_sequence=[T.GREEN]), "Wickets by over number (bowler-credited)", "Over", "Wickets", h=320)
T.note("Phases follow the actual mandatory powerplay in each match (rain-reduced games are scaled); everything after it up to the last 4 overs (T20I) or 10 overs (ODI) is 'Middle'. "
       "Strike rate and economy use legal balls; wides do not count as balls faced; run-outs are not credited to the bowler.")
