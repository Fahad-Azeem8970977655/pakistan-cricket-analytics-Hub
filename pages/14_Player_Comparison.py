import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import analytics as AN
from utils import data as D
from utils import splits as S
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Player Comparison", "Pakistan player vs each opponent, player vs player, and batter vs bowler match-ups")
if b.empty or w.empty:
    st.warning("No data for these filters."); st.stop()
ob, ow, _ = D.load_opp()
ids = set(m.match_id)
ob, ow = D.by_ids(ob, ids), D.by_ids(ow, ids)
A, B = "#0B6B3A", "#C9A227"

bat_all = S.batting_table(b, ["player"])
bowl_all = S.bowling_table(w, ["player"])


def pctile(df, col, val, higher_better=True, min_col="Inns", min_val=10):
    pool = df[df[min_col] >= min_val][col].dropna()
    if pool.empty or pd.isna(val): return 0
    r = (pool < val).mean() * 100 if higher_better else (pool > val).mean() * 100
    return round(r, 0)


def radar(names, cats, vals_by_player, title):
    f = go.Figure()
    for (n, col), v in zip(names, vals_by_player):
        f.add_trace(go.Scatterpolar(r=v + [v[0]], theta=cats + [cats[0]], fill="toself", name=n, line=dict(color=col), opacity=.65))
    f.update_layout(polar=dict(radialaxis=dict(range=[0, 100], ticksuffix="", tickfont_size=9)))
    T.plot(f, title, h=430, legend="Player")


tab1, tab2, tab3 = st.tabs(["Player vs opponent teams", "Player vs player", "Batter vs bowler match-ups"])

# ---------------------------------------------------------------- tab 1
with tab1:
    c1, c2 = st.columns([2, 1])
    kind = c2.radio("Discipline", ["Batting", "Bowling"], horizontal=True, key="k1")
    if kind == "Batting":
        names = bat_all.sort_values("Runs", ascending=False).player.tolist()
    else:
        names = bowl_all.sort_values("Wkts", ascending=False).player.tolist()
    who = c1.selectbox("Pakistan player", names, key="p1")
    min_m = st.slider("Minimum innings against an opponent", 1, 10, 2, key="mi1")
    if kind == "Batting":
        t = S.batting_table(b[b.player == who], ["opponent"])
        t = t[t.Inns >= min_m].sort_values("Runs", ascending=False)
        if t.empty: st.info("Not enough innings against any opponent for this selection.")
        else:
            tot = bat_all[bat_all.player == who].iloc[0]
            T.kpis([("Career runs (filtered)", int(tot.Runs), f"{int(tot.Inns)} innings", "green"), ("Average", tot.Avg, "", "green"), ("Strike rate", tot.SR, "", "blue"),
                    ("Best opponent (avg)", t.sort_values("Avg", ascending=False).iloc[0].opponent, f"avg {t.Avg.max()}", "gold", "up"),
                    ("Toughest opponent (avg)", t.sort_values("Avg").iloc[0].opponent, f"avg {t.Avg.min()}", "red", "down")], per_row=5)
            d1, d2 = st.columns(2)
            f = px.bar(t.sort_values("Runs"), y="opponent", x="Runs", orientation="h", text="Runs", color="Avg", color_continuous_scale=T.DIV, hover_data=["Inns", "SR", "HS"])
            f.update_traces(textposition="outside")
            with d1: T.plot(f, f"{who}: runs against each opponent (colour = average)", "Runs", "Opponent", cbar="Average", h=420)
            f = px.scatter(t, x="SR", y="Avg", size="Runs", text="opponent", color="Runs", color_continuous_scale=T.SEQ_GREEN, hover_data=["Inns", "HS"])
            f.update_traces(textposition="top center")
            with d2: T.plot(f, f"{who}: average vs strike rate by opponent", "Strike rate", "Batting average", cbar="Runs", h=420)
            e = b[b.player == who].merge(m[["match_id"]], on="match_id")
            f = px.box(e, x="opponent", y="runs", color="format", color_discrete_map=D.FMT_COLORS, points="all", hover_data=["date"])
            T.plot(f, f"{who}: innings scores by opponent", "Opponent", "Runs per innings", legend="Format")
            st.dataframe(t, hide_index=True, width="stretch")
    else:
        t = S.bowling_table(w[w.player == who], ["opponent"])
        t = t[t.Inns >= min_m].sort_values("Wkts", ascending=False)
        if t.empty: st.info("Not enough spells against any opponent for this selection.")
        else:
            tot = bowl_all[bowl_all.player == who].iloc[0]
            T.kpis([("Wickets (filtered)", int(tot.Wkts), f"{int(tot.Inns)} spells", "green"), ("Average", tot.Avg, "", "green"), ("Economy", tot.Econ, "", "blue"),
                    ("Most wickets vs", t.iloc[0].opponent, f"{int(t.iloc[0].Wkts)} wkts", "gold", "up"),
                    ("Most expensive vs", t.sort_values("Econ", ascending=False).iloc[0].opponent, f"econ {t.Econ.max()}", "red", "down")], per_row=5)
            d1, d2 = st.columns(2)
            f = px.bar(t.sort_values("Wkts"), y="opponent", x="Wkts", orientation="h", text="Wkts", color="Econ", color_continuous_scale=T.DIV_R, hover_data=["Inns", "Avg", "BBI"])
            f.update_traces(textposition="outside")
            with d1: T.plot(f, f"{who}: wickets against each opponent (colour = economy)", "Wickets", "Opponent", cbar="Economy", h=420)
            f = px.scatter(t, x="Econ", y="Avg", size="Wkts", text="opponent", color="Dot %", color_continuous_scale="Viridis", hover_data=["Inns", "BBI"])
            f.update_traces(textposition="top center")
            with d2: T.plot(f, f"{who}: economy vs bowling average by opponent", "Economy (runs per over)", "Bowling average", cbar="Dot-ball %", h=420)
            st.dataframe(t.drop(columns=["_balls"]), hide_index=True, width="stretch")

# ---------------------------------------------------------------- tab 2
with tab2:
    kind = st.radio("Discipline", ["Batting", "Bowling"], horizontal=True, key="k2")
    pool = (bat_all[bat_all.Inns >= 10].sort_values("Runs", ascending=False).player if kind == "Batting"
            else bowl_all[bowl_all.Inns >= 10].sort_values("Wkts", ascending=False).player).tolist()
    if len(pool) < 2:
        st.info("Not enough players with 10+ innings under the current filters."); st.stop()
    c1, c2 = st.columns(2)
    p1 = c1.selectbox("Player A", pool, index=0, key="pa")
    p2 = c2.selectbox("Player B", pool, index=1, key="pb")
    if p1 == p2: st.info("Pick two different players.")
    else:
        if kind == "Batting":
            ra, rb = bat_all[bat_all.player == p1].iloc[0], bat_all[bat_all.player == p2].iloc[0]
            met = ["Runs", "Avg", "SR", "HS", "100s", "50s", "Bdry %"]
            cards = [(k, ra[k], rb[k]) for k in met]
            rt = AN.rap_table(AN.with_rap(b[b.player.isin([p1, p2])])).set_index("player")
            cards += [("Runs above par / inn", rt["RAP/inn"].get(p1, "n/a"), rt["RAP/inn"].get(p2, "n/a")), ("Runs above par (total)", rt["RAP"].get(p1, "n/a"), rt["RAP"].get(p2, "n/a"))]
            cats = ["Runs", "Average", "Strike rate", "Boundary %", "50+ per innings", "Not ducks"]
            def rv(r):
                x = bat_all.assign(**{"50+/inn": (bat_all["50s"] + bat_all["100s"]) / bat_all.Inns, "ND": 1 - bat_all.Ducks / bat_all.Inns})
                v = lambda c, val: pctile(x, c, val)
                return [v("Runs", r.Runs), v("Avg", r.Avg), v("SR", r.SR), v("Bdry %", r["Bdry %"]),
                        v("50+/inn", (r["50s"] + r["100s"]) / r.Inns), v("ND", 1 - r.Ducks / r.Inns)]
            vals = [rv(ra), rv(rb)]
            low = []
        else:
            ra, rb = bowl_all[bowl_all.player == p1].iloc[0], bowl_all[bowl_all.player == p2].iloc[0]
            met = ["Wkts", "Avg", "Econ", "SR", "Dot %", "5W", "BBI"]
            cards = [(k, ra[k], rb[k]) for k in met]
            cats = ["Wickets", "Average (lower better)", "Economy (lower better)", "Strike rate (lower better)", "Dot-ball %", "5W hauls"]
            def rv(r):
                return [pctile(bowl_all, "Wkts", r.Wkts), pctile(bowl_all, "Avg", r.Avg, False), pctile(bowl_all, "Econ", r.Econ, False),
                        pctile(bowl_all, "SR", r.SR, False), pctile(bowl_all, "Dot %", r["Dot %"]), pctile(bowl_all, "5W", r["5W"])]
            vals = [rv(ra), rv(rb)]
            low = ["Avg", "Econ", "SR"]
        T.section("Head-to-head numbers", "the better value of each pair is highlighted")
        rows = ""
        for k, va, vb in cards:
            try:
                tie = va == vb
                a_better = (va < vb) if k in low else (va > vb)
            except TypeError:
                tie, a_better = True, False
            hl = "background:#DDF3E7;color:#0B6B3A;font-weight:800"
            sa, sb = ("", "") if tie else ((hl, "") if a_better else ("", hl))
            rows += (f'<tr><td style="padding:8px 12px;color:#5F6F68;font-weight:600">{k}</td>'
                     f'<td style="padding:8px 12px;text-align:center;{sa}">{va}</td>'
                     f'<td style="padding:8px 12px;text-align:center;{sb}">{vb}</td></tr>')
        st.markdown(f'<table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #E1E9E4;border-radius:10px;overflow:hidden">'
                    f'<tr style="background:#073B21;color:#fff"><th style="padding:8px 12px;text-align:left">Metric</th>'
                    f'<th style="padding:8px 12px">{p1}</th><th style="padding:8px 12px">{p2}</th></tr>{rows}</table>', unsafe_allow_html=True)
        st.write("")
        d1, d2 = st.columns(2)
        with d1:
            radar([(p1, A), (p2, B)], cats, vals, f"Percentile profile (vs Pakistan players with 10+ innings)")
        with d2:
            if kind == "Batting":
                t = pd.concat([S.batting_table(b[b.player == p], ["player", "format"]) for p in (p1, p2)])
                f = px.bar(t, x="format", y="Runs", color="player", barmode="group", text="Runs", color_discrete_sequence=[A, B], hover_data=["Avg", "SR", "Inns"])
                f.update_traces(textposition="outside")
                T.plot(f, "Runs by format", "Format", "Runs", legend="Player", h=430)
            else:
                t = pd.concat([S.bowling_table(w[w.player == p], ["player", "format"]) for p in (p1, p2)])
                f = px.bar(t, x="format", y="Wkts", color="player", barmode="group", text="Wkts", color_discrete_sequence=[A, B], hover_data=["Avg", "Econ", "Inns"])
                f.update_traces(textposition="outside")
                T.plot(f, "Wickets by format", "Format", "Wickets", legend="Player", h=430)
        e1, e2 = st.columns(2)
        both = b[b.player.isin([p1, p2])] if kind == "Batting" else w[w.player.isin([p1, p2])]
        if kind == "Batting":
            y = both.groupby(["year", "player"]).agg(Runs=("runs", "sum"), Balls=("balls", "sum")).reset_index()
            with e1: T.plot(px.line(y, x="year", y="Runs", color="player", markers=True, color_discrete_sequence=[A, B]), "Runs per year", "Year", "Runs", legend="Player")
            t = pd.concat([S.batting_table(b[b.player == p], ["player", "opponent"]) for p in (p1, p2)])
            t = t[t.Inns >= 2]
            with e2: T.plot(px.bar(t, x="opponent", y="Avg", color="player", barmode="group", color_discrete_sequence=[A, B], hover_data=["Runs", "Inns"]),
                            "Batting average vs each opponent (min 2 innings)", "Opponent", "Batting average", legend="Player")
        else:
            y = both.groupby(["year", "player"]).wickets.sum().reset_index()
            with e1: T.plot(px.line(y, x="year", y="wickets", color="player", markers=True, color_discrete_sequence=[A, B]), "Wickets per year", "Year", "Wickets", legend="Player")
            t = pd.concat([S.bowling_table(w[w.player == p], ["player", "opponent"]) for p in (p1, p2)])
            t = t[t.Inns >= 2]
            with e2: T.plot(px.bar(t, x="opponent", y="Wkts", color="player", barmode="group", color_discrete_sequence=[A, B], hover_data=["Avg", "Econ"]),
                            "Wickets vs each opponent (min 2 spells)", "Opponent", "Wickets", legend="Player")

# ---------------------------------------------------------------- tab 3
with tab3:
    st.caption("Counts are dismissals only (Cricsheet-derived scorecards have no ball-by-ball runs per pair here). Run-outs are excluded because no bowler is credited.")
    d = b[b.is_out & b.dismissed_by.notna()]
    if d.empty:
        st.info("No dismissals for these filters.")
    else:
        T.section("Opposition bowlers who dismiss Pakistan batters most")
        top = d.groupby("dismissed_by").size().sort_values(ascending=False).head(15).reset_index(name="Dismissals").sort_values("Dismissals")
        f = px.bar(top, y="dismissed_by", x="Dismissals", orientation="h", text="Dismissals", color_discrete_sequence=["#D64545"])
        f.update_traces(textposition="outside")
        T.plot(f, "Most Pakistan wickets taken by an opposition bowler", "Pakistan batters dismissed", "Opposition bowler", h=480)

        T.section("Pakistan batter: who gets him out?")
        bpl = d.player.value_counts().index.tolist()
        who = st.selectbox("Pakistan batter", bpl, key="mu_b")
        x = d[d.player == who].groupby(["dismissed_by"]).size().reset_index(name="Dismissals").sort_values("Dismissals", ascending=False)
        c1, c2 = st.columns(2)
        with c1:
            f = px.bar(x.head(12).sort_values("Dismissals"), y="dismissed_by", x="Dismissals", orientation="h", text="Dismissals", color_discrete_sequence=["#D64545"])
            f.update_traces(textposition="outside")
            T.plot(f, f"{who}: most frequent dismissers", "Times dismissed", "Opposition bowler", h=400)
        with c2:
            dm = d[d.player == who].dismissal.value_counts().reset_index()
            f = px.pie(dm, names="dismissal", values="count", hole=.55, color_discrete_sequence=T.COLORWAY)
            T.plot(f, f"{who}: how he gets out", h=400, legend="Mode")

        T.section("Pakistan bowler: whom does he dismiss?")
        if ob.empty:
            st.info("No opposition scorecard data.")
        else:
            o2 = ob[ob.is_out].copy()
            o2["bowler"] = o2.dismissal.str.extract(r" b (.+)$")[0]
            o2 = o2[o2.bowler.notna()]
            pak_bowlers = set(w.player)
            o2 = o2[o2.bowler.isin(pak_bowlers)]
            bw = o2.bowler.value_counts().index.tolist()
            if not bw:
                st.info("No matching dismissals.")
            else:
                wb = st.selectbox("Pakistan bowler", bw, key="mu_w")
                y = o2[o2.bowler == wb].groupby("player").size().reset_index(name="Dismissals").sort_values("Dismissals", ascending=False)
                z = o2[o2.bowler == wb].groupby("opponent").size().reset_index(name="Wickets").sort_values("Wickets")
                c3, c4 = st.columns(2)
                with c3:
                    f = px.bar(y.head(12).sort_values("Dismissals"), y="player", x="Dismissals", orientation="h", text="Dismissals", color_discrete_sequence=[T.GREEN])
                    f.update_traces(textposition="outside")
                    T.plot(f, f"{wb}: opposition batters he dismisses most", "Times dismissed", "Opposition batter", h=400)
                with c4:
                    f = px.bar(z, y="opponent", x="Wickets", orientation="h", text="Wickets", color_discrete_sequence=[T.GREEN])
                    f.update_traces(textposition="outside")
                    T.plot(f, f"{wb}: bowler-credited wickets by opponent team", "Wickets", "Opponent", h=400)
        T.section("Match-up matrix", "top Pakistan batters × top opposition bowlers")
        tb = d.player.value_counts().head(10).index
        to = d.dismissed_by.value_counts().head(10).index
        mx = d[d.player.isin(tb) & d.dismissed_by.isin(to)].groupby(["player", "dismissed_by"]).size().unstack(fill_value=0)
        if not mx.empty:
            T.plot(px.imshow(mx, text_auto=True, color_continuous_scale=T.SEQ_RED, aspect="auto"), "Times each Pakistan batter was dismissed by each bowler", "Opposition bowler", "Pakistan batter", cbar="Dismissals", h=470)
