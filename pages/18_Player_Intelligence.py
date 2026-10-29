import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import analytics as A
from utils import data as D
from utils import ml as ML
from utils import theme as T

D.setup()
m, b, w = D.load()
T.hero("Player Intelligence", "Data-driven roles, similar players, how long batters survive, batter v bowler match-ups and shrunk records against each opponent.",
       chips=["Uses ALL data (sidebar filters do not apply here)", "Unsupervised learning: roles are found by the algorithm, not assigned", "Approximate match-ups: no ball-by-ball data"])
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Roles (clustering)", "Similar players", "Survival (how long batters last)", "Batter v bowler match-ups", "Record vs an opponent (shrunk)"])
MIN_BAT = {"ODI": 25, "T20I": 20, "Test": 30, "All": 40}
MIN_BOWL = {"ODI": 25, "T20I": 15, "Test": 25, "All": 35}
ROLE_COLORS = ["#0B6B3A", "#2A7AB9", "#C9A227", "#C0392B", "#7B5EA7", "#E07B39"]

# ======================================================================= 1 CLUSTERS
with tab1:
    c = st.columns(4)
    kind = c[0].radio("Discipline", ["Batting", "Bowling"], horizontal=True, key="cl_k")
    fmt = c[1].selectbox("Format", ["ODI", "T20I", "Test", "All"], key="cl_f")
    k = c[3].slider("Number of roles (k)", 3, 6, 4, key="cl_n")
    if kind == "Batting":
        mn = c[2].slider("Min innings", 10, 150, MIN_BAT[fmt], key=f"cl_mb_{fmt}")
        prof = ML.batting_profile(b, fmt, mn); feats, ck = ML.BAT_FEATS, "bat"
    else:
        mn = c[2].slider("Min bowling spells", 5, 120, MIN_BOWL[fmt], key=f"cl_mw_{fmt}")
        prof = ML.bowling_profile(w, fmt, mn); feats, ck = ML.BOWL_FEATS, "bowl"
    if len(prof) <= k + 1:
        st.warning("Too few players with these settings. Lower the minimum or the number of roles."); st.stop()
    lab, xy, cent, sil, ev = ML.cluster_players(prof, feats, k, ck)
    T.kpis([("Players clustered", len(prof), f"{fmt} {kind.lower()}", "green"), ("Roles found", k, "k-means, standardised features", "blue"),
            ("Silhouette score", f"{sil:.2f}", "0.5+ clear groups, 0.25 to 0.5 overlapping", "gold"), ("Variance shown", f"{100 * ev.sum():.0f}%", "by the 2-D map below", "grey")], per_row=4)
    pl = xy.join(lab).join(prof[["Inns" if kind == "Batting" else "Spells"]].rename(columns=lambda x: "n"))
    f = px.scatter(pl.reset_index(), x="PC1", y="PC2", color="Role", size="n", size_max=26, hover_name="player", text="player", color_discrete_sequence=ROLE_COLORS)
    f.update_traces(textposition="top center", textfont=dict(size=10, color="#1B2A24"), marker=dict(line=dict(width=1.5, color="white")))
    T.plot(f, f"{fmt} {kind.lower()} roles found by k-means (map of the first two principal components)", f"Component 1 ({100 * ev[0]:.0f}% of variation)",
           f"Component 2 ({100 * ev[1]:.0f}% of variation)", legend="Role", h=560)
    T.section("What each role looks like", "average of the players in the role, original units")
    st.dataframe(cent.style.format({c_: "{:.1f}" for c_ in feats}), hide_index=True, width="stretch")
    with st.expander("Players in each role"):
        for role, g in lab.groupby(lab):
            st.markdown(f"**{role}** ({len(g)}): " + ", ".join(g.index))
    T.note("Role names are suggested by simple rules on the cluster averages (position, strike rate, balls per innings), so check the table before trusting a label. "
           "A silhouette score near 0.3 means roles overlap: cricket styles are a spectrum, not boxes.")

# ======================================================================= 2 SIMILAR
with tab2:
    c = st.columns(4)
    kind2 = c[0].radio("Discipline", ["Batting", "Bowling"], horizontal=True, key="sm_k")
    fmt2 = c[1].selectbox("Format", ["ODI", "T20I", "Test", "All"], key="sm_f")
    if kind2 == "Batting":
        prof2 = ML.batting_profile(b, fmt2, c[2].slider("Min innings", 10, 150, MIN_BAT[fmt2], key=f"sm_mb_{fmt2}")); feats2, inv = ML.BAT_FEATS, ()
    else:
        prof2 = ML.bowling_profile(w, fmt2, c[2].slider("Min bowling spells", 5, 120, MIN_BOWL[fmt2], key=f"sm_mw_{fmt2}")); feats2, inv = ML.BOWL_FEATS, ("Econ", "Strike rate", "Boundary % conceded")
    if len(prof2) < 6:
        st.warning("Too few players with these settings."); st.stop()
    who = c[3].selectbox("Player", sorted(prof2.index), index=sorted(prof2.index).index("Fakhar Zaman") if "Fakhar Zaman" in prof2.index else 0, key="sm_p")
    sim = ML.similar_players(prof2, feats2, who, 8)
    T.section(f"Players most like {who}", "Euclidean distance on standardised features; similarity % is a relative index")
    st.dataframe(sim.reset_index().rename(columns={"player": "Player"}).style.format({c_: "{:.1f}" for c_ in sim.columns}), hide_index=True, width="stretch")
    top3 = sim.index[:3].tolist()
    pct = ML.percentile_profile(prof2, feats2, [who] + top3, invert=inv)
    f = go.Figure()
    for i, (p, row) in enumerate(pct.iterrows()):
        f.add_trace(go.Scatterpolar(r=list(row.values) + [row.values[0]], theta=feats2 + [feats2[0]], name=p, fill="toself" if i == 0 else None,
                                    line=dict(color=ROLE_COLORS[i % 6], width=4 if i == 0 else 2.5), opacity=0.95 if i == 0 else 0.8))
    f.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickfont_size=10, gridcolor="#C9D3CE"), angularaxis=dict(tickfont_size=12)))
    T.plot(f, f"Percentile profile: {who} vs his three closest matches (100 = best among {len(prof2)} players)", legend="Player", h=520)

# ======================================================================= 3 SURVIVAL
with tab3:
    T.section("Kaplan-Meier survival of a batting innings", "probability a batter is still not out after N balls; not-outs are handled as censored")
    c = st.columns(3)
    by = c[0].radio("Compare", ["Formats", "Batting roles", "Players"], horizontal=True, key="sv_by")
    fmts = c[1].multiselect("Formats included", ["Test", "ODI", "T20I"], default=["ODI", "T20I"] if by != "Formats" else ["Test", "ODI", "T20I"], key="sv_f")
    xmax = c[2].slider("Show up to (balls)", 20, 200, 80, 10)
    bb = b[b.format.isin(fmts)] if fmts else b.iloc[0:0]
    curves = {}
    if by == "Formats":
        for f_, g in bb.groupby("format"): curves[f_] = g
    elif by == "Batting roles":
        bb = bb.assign(role=A.bucket(bb.batting_position)).dropna(subset=["role"])
        for r_ in A.BUCKETS:
            g = bb[bb.role == r_]
            if len(g) >= 30: curves[r_] = g
    else:
        cand = bb.groupby("player").size().sort_values(ascending=False)
        cand = cand[cand >= 20].index.tolist()
        sel = st.multiselect("Players (up to 4)", cand, default=cand[:2], max_selections=4)
        curves["Pakistan average"] = bb
        for p in sel: curves[p] = bb[bb.player == p]
    if not curves:
        st.info("Nothing to show with these settings."); st.stop()
    f = go.Figure(); rows = []
    for i, (name, g) in enumerate(curves.items()):
        km = ML.kaplan_meier(g.balls, g.is_out)
        kk = km[km.balls <= xmax]
        col = "#6B7A86" if name == "Pakistan average" else (D.FMT_COLORS.get(name) if by == "Formats" else ROLE_COLORS[i % 6])
        f.add_trace(go.Scatter(x=kk.balls, y=100 * kk.survival, mode="lines", name=f"{name} (n={len(g)})", line=dict(width=4 if name != "Pakistan average" else 3, color=col, dash="dot" if name == "Pakistan average" else "solid"), line_shape="hv"))
        rows.append({"Group": name, "Innings": len(g), "Median balls survived": ML.km_median(km), "Still in after 10 balls %": 100 * ML.km_at(km, 10),
                     "after 30 balls %": 100 * ML.km_at(km, 30), "after 60 balls %": 100 * ML.km_at(km, 60)})
    T.plot(f, "Chance of still being at the crease after N balls", "Balls faced", "Probability batter is not out", ylim=[0, 100], pct=True, legend="Group", h=480)
    st.dataframe(pd.DataFrame(rows).style.format({"Median balls survived": "{:.0f}", "Still in after 10 balls %": "{:.0f}", "after 30 balls %": "{:.0f}", "after 60 balls %": "{:.0f}"}), hide_index=True, width="stretch")
    T.note("The data has no bowler type (pace or spin), so survival cannot be split by bowler type. "
           "If you add a file mapping bowlers to types we can extend this. Individual curves with fewer than about 40 innings are noisy.")

# ======================================================================= 4 MATCH-UPS
with tab4:
    mu = ML.matchup_bundle()
    T.section("Dismissal match-ups", "estimated balls faced and dismissals, compared with what each player's generic strengths would predict")
    T.note("How it works: no ball-by-ball data exists here, so balls faced against each bowler are ESTIMATED as (balls the batter faced in the innings) x (that bowler's share of the innings' balls). "
           "Expected dismissals multiply the batter's and the bowler's overall dismissal rates. The index = shrunk observed rate / expected rate: above 1 means the bowler gets the batter out MORE than normal. Run-outs are excluded.")
    c = st.columns(4)
    dirn = c[0].radio("View", ["Pakistan batter v opposition bowlers", "Pakistan bowler v opposition batters"], key="mu_d")
    kprior = c[2].slider("Prior strength (balls)", 0, 200, 60, 10, key="mu_k")
    minb = c[3].slider("Min estimated balls", 10, 200, 40, 10, key="mu_m")
    if dirn.startswith("Pakistan batter"):
        t = ML.add_rate(mu["bat_vs_opp_bowl"], kprior); a, o = "player", "bowler"; ylab, good_high = "Opposition bowler", False
    else:
        t = ML.add_rate(mu["bowl_vs_opp_bat"], kprior); a, o = "bowler", "batter"; ylab, good_high = "Opposition batter", True
    people = t.groupby(a).E.sum().sort_values(ascending=False).index.tolist()
    who = c[1].selectbox("Pakistan player", people, key="mu_p")
    x = t[(t[a] == who) & (t.E >= minb)].copy()
    if x.empty:
        st.info("No opponents with that many estimated balls. Lower the minimum.")
    else:
        x = x.sort_values("index")
        if good_high: x["Reading"] = np.where(x["index"] >= 1, "Pakistan bowler dominates", "Opponent copes well")
        else: x["Reading"] = np.where(x["index"] >= 1, "Bowler dominates batter", "Batter copes well")
        cmap = ({"Pakistan bowler dominates": T.GREEN, "Opponent copes well": "#C0392B"} if good_high else {"Bowler dominates batter": "#C0392B", "Batter copes well": T.GREEN})
        x["label"] = x.D.astype(int).astype(str) + " out / " + x.expected.round(1).astype(str) + " expected"
        xs = x if len(x) <= 24 else pd.concat([x.head(10), x.tail(14)])   # show both ends: players who cope best AND worst
        f = px.bar(xs, y=o, x="index", orientation="h", color="Reading", color_discrete_map=cmap, text="label", hover_data={"E": ":.0f", "D": True, "rate100": ":.2f", "base100": ":.2f"})
        f.update_traces(textposition="outside"); f.add_vline(x=1, line_dash="dot", line_color="#1B2A24")
        f.update_xaxes(range=[0, max(2.2, x["index"].max() * 1.35)])
        T.plot(f, f"{who}: dismissal index against each opponent (1 = as expected)", "Dismissal index (shrunk observed / expected)", ylab, legend="Reading", h=max(380, 26 * len(xs) + 120))
        st.dataframe(x.sort_values("index", ascending=False)[[o, "E", "D", "expected", "rate100", "base100", "index"]].rename(columns={
            "E": "Est. balls", "D": "Dismissals", "expected": "Expected", "rate100": "Rate /100 balls (shrunk)", "base100": "Generic rate /100", "index": "Index"})
            .style.format({"Est. balls": "{:.0f}", "Expected": "{:.1f}", "Dismissals": "{:.0f}", "Rate /100 balls (shrunk)": "{:.2f}", "Generic rate /100": "{:.2f}", "Index": "{:.2f}"}), hide_index=True, width="stretch")
    T.section("Strongest pairings in the whole dataset", "at least 60 estimated balls and 3 dismissals")
    z = t[(t.E >= 60) & (t.D >= 3)].sort_values("index", ascending=False).head(15)
    st.dataframe(z[[a, o, "E", "D", "expected", "index"]].rename(columns={"E": "Est. balls", "D": "Dismissals", "expected": "Expected", "index": "Index"})
                 .style.format({"Est. balls": "{:.0f}", "Dismissals": "{:.0f}", "Expected": "{:.1f}", "Index": "{:.2f}"}), hide_index=True, width="stretch")

# ======================================================================= 5 SHRUNK VS OPPONENT
with tab5:
    T.section("Player records against one opponent, with empirical-Bayes shrinkage", "few innings => estimate pulled towards the player's own overall record")
    c = st.columns(4)
    opp = c[0].selectbox("Opponent", sorted(set(m.opponent)), index=sorted(set(m.opponent)).index("Afghanistan") if "Afghanistan" in set(m.opponent) else 0, key="eb_o")
    kind5 = c[1].radio("Discipline", ["Batting", "Bowling"], horizontal=True, key="eb_k")
    if kind5 == "Batting":
        kk = c[2].slider("Prior strength (dismissals)", 0, 20, 6, key="eb_kb")
        t5 = ML.shrink_batter_vs_opponent(b, opp, kk)
        t5 = t5[t5.inns >= c[3].slider("Min innings", 1, 10, 1, key="eb_mb")]
        if t5.empty: st.info(f"No Pakistan batting scorecards against {opp} yet. Matches added manually have no player rows.")
        else:
            d = t5.head(15).melt("player", ["raw_avg", "shrunk_avg", "avg_all"], var_name="e", value_name="Average")
            d["e"] = d.e.map({"raw_avg": f"Raw average vs {opp}", "shrunk_avg": "Shrunk average", "avg_all": "Career average (all opponents)"})
            f = px.bar(d, x="player", y="Average", color="e", barmode="group", color_discrete_sequence=["#8A949C", T.GREEN, T.GOLD])
            T.plot(f, f"Batting average against {opp}: raw vs shrunk vs career", "Batter", "Runs per dismissal", legend="Estimate", h=460)
            st.dataframe(t5.rename(columns={"inns": "Innings", "runs": "Runs", "outs": "Dismissals", "avg_all": "Career avg", "raw_avg": "Raw avg", "shrunk_avg": "Shrunk avg"})
                         .style.format({"Career avg": "{:.1f}", "Raw avg": "{:.1f}", "Shrunk avg": "{:.1f}"}), hide_index=True, width="stretch")
    else:
        kk = c[2].slider("Prior strength (spells)", 0, 15, 4, key="eb_kw")
        t5 = ML.shrink_bowler_vs_opponent(w, opp, kk)
        t5 = t5[t5.spells >= c[3].slider("Min spells", 1, 10, 1, key="eb_mw")]
        if t5.empty: st.info(f"No Pakistan bowling scorecards against {opp} yet. Matches added manually have no player rows.")
        else:
            d = t5.head(15).melt("player", ["raw_rate", "shrunk_rate", "rate_all"], var_name="e", value_name="Wickets per spell")
            d["e"] = d.e.map({"raw_rate": f"Raw vs {opp}", "shrunk_rate": "Shrunk", "rate_all": "Career (all opponents)"})
            f = px.bar(d, x="player", y="Wickets per spell", color="e", barmode="group", color_discrete_sequence=["#8A949C", T.GREEN, T.GOLD])
            T.plot(f, f"Wickets per spell against {opp}: raw vs shrunk vs career", "Bowler", "Wickets per spell", legend="Estimate", h=460)
            st.dataframe(t5, hide_index=True, width="stretch")
