import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import data as D
from utils import ml as ML
from utils import theme as T

D.setup()
m, b, w = D.load()
T.hero("Match Predictor", "Elo ratings, pre-match win probability, live chase probability, first-innings score model and shrunk opponent records.",
       chips=["Uses ALL data (sidebar filters do not apply here)", "Time-ordered tests: models never see the future", "Small samples: read the caveats"])

pb = ML.prematch_bundle()
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Pre-match win probability", "Live chase probability", "First-innings score", "Opponent record (shrunk)", "Elo ratings"])

# ======================================================================= 1 PRE-MATCH
with tab1:
    T.section("What-if scenario", "Pakistan win probability (draws excluded) before the first ball")
    c = st.columns(5)
    fmt = c[0].selectbox("Format", ["T20I", "ODI", "Test"], key="pm_f")
    opps = sorted(m[m.format == fmt].opponent.unique()) or pb["opponents"]
    opp = c[1].selectbox("Opponent", opps, index=opps.index("Afghanistan") if "Afghanistan" in opps else 0, key="pm_o")
    grp = c[2].selectbox("Venue", ["Neutral", "Home", "Away"], key="pm_v")
    toss = c[3].selectbox("Toss", ["Pakistan won", "Pakistan lost"], key="pm_t") == "Pakistan won"
    bf = c[4].selectbox("Pakistan will", ["Bat first", "Bat second"], key="pm_b") == "Bat first"
    ko = st.checkbox("Knockout match", key="pm_k")
    r = ML.predict_prematch(pb, fmt, opp, grp, toss, bf, ko)
    cons = (r["Elo"] + r["LR"] + r["GB"]) / 3
    T.kpis([("Consensus (average of 3)", f"{100 * cons:.0f}%", "Pakistan win probability", "green" if cons >= .5 else "red", "up" if cons >= .5 else "down"),
            ("Logistic regression", f"{100 * r['LR']:.0f}%", "Best model on the held-out test", "blue"),
            ("Gradient boosting", f"{100 * r['GB']:.0f}%", "Tree-based model", "blue"),
            ("Elo only", f"{100 * r['Elo']:.0f}%", f"Pakistan {r['elo_pak']:.0f} vs {opp} {r['elo_opp']:.0f}", "gold")], per_row=4)
    d = pd.DataFrame({"Model": ["Elo only", "Gradient boosting", "Logistic regression", "Consensus"], "p": [r["Elo"], r["GB"], r["LR"], cons]})
    f = px.bar(d, y="Model", x=100 * d.p, orientation="h", text=(100 * d.p).round(0).astype(int).astype(str) + "%", color="Model",
               color_discrete_map={"Elo only": T.GOLD, "Gradient boosting": "#2A7AB9", "Logistic regression": "#1D5F96", "Consensus": T.GREEN})
    f.update_traces(textposition="outside"); f.update_layout(showlegend=False); f.update_xaxes(range=[0, 105], ticksuffix="%")
    f.add_vline(x=50, line_dash="dot", line_color="#6B7A86")
    T.plot(f, f"Pakistan v {opp} ({fmt}, {grp.lower()} venue): win probability", "Pakistan win probability", "Model", h=300)
    n_h2h = int(((m.opponent == opp) & (m.format == fmt) & m.result.isin(['Won', 'Lost'])).sum())
    T.note(f"Direct history in this format vs {opp}: {n_h2h} decisive matches. With so few meetings the models lean on Pakistan's overall Elo and form, "
           "so treat the number as a starting point, not a forecast. Toss and batting order have almost no effect in the data.")

    T.section("How good are the models?", f"trained on {pb['n_train']} matches before {pb['split_date']:%d %b %Y}, tested on the {pb['n_test']} matches after")
    mt = pb["metrics"]
    st.dataframe(mt.style.format({"Accuracy": "{:.1%}", "LogLoss": "{:.3f}", "Brier": "{:.3f}", "AUC": "{:.3f}"})
                 .highlight_max(subset=["Accuracy", "AUC"], color="#BFE8CF").highlight_min(subset=["LogLoss", "Brier"], color="#BFE8CF"), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    f = px.bar(mt, x="Model", y="AUC", text=mt.AUC.round(3), color="Model", color_discrete_sequence=["#8A949C", T.GOLD, "#1D5F96", "#2A7AB9"])
    f.update_traces(textposition="outside"); f.update_layout(showlegend=False); f.add_hline(y=0.5, line_dash="dot", line_color="#C0392B")
    with c1: T.plot(f, "Ranking quality (AUC, higher is better; red line = coin flip)", "Model", "AUC", ylim=[0.4, 0.85], h=360)
    f = go.Figure(); f.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dot", color="#6B7A86"))
    for (n, cdf), col in zip(pb["calib"].items(), [T.GOLD, "#1D5F96", "#2A7AB9"]):
        f.add_trace(go.Scatter(x=cdf.predicted, y=cdf.observed, mode="lines+markers", name=n, line=dict(color=col, width=3), marker=dict(size=9)))
    with c2: T.plot(f, "Calibration: when a model says 70%, how often does Pakistan win?", "Predicted win probability", "Observed win rate", legend="Model", h=360)
    c3, c4 = st.columns(2)
    co = pb["coef"].assign(col=lambda x: np.where(x.Effect >= 0, "Raises win chance", "Lowers win chance"))
    f = px.bar(co, y="Feature", x="Effect", orientation="h", color="col", color_discrete_map={"Raises win chance": T.GREEN, "Lowers win chance": "#C0392B"})
    with c3: T.plot(f, "Logistic regression: standardised effect of each feature", "Effect on log-odds of a Pakistan win", "Feature", legend="Direction", h=380)
    im = pb["imp"]
    f = px.bar(im, y="Feature", x="Importance", orientation="h", error_x="Std", color_discrete_sequence=["#2A7AB9"])
    with c4: T.plot(f, "Gradient boosting: permutation importance on the test matches", "Drop in log-loss when the feature is scrambled", "Feature", h=380)
    T.note("Reading this honestly: the models beat the 'always base rate' baseline (about 52% accuracy), but the test set is only about 114 matches, so differences between "
           "models are within noise. The strongest signal is the shrunk head-to-head record and Elo; toss and batting order add almost nothing.")

# ======================================================================= 2 CHASE
with tab2:
    cb = ML.chase_bundle()
    d = cb["data"]
    T.section("Chase win probability by over", f"{cb['n_matches']} ODI/T20I chases, {cb['n_states']:,} match states; held-out test on the latest {cb['n_test_matches']} matches")
    meta = d.groupby("match_id").agg(date=("date", "first"), fmt=("format", "first"), chaser=("chaser", "first"), target=("target", "first"), won=("y", "first")).reset_index()
    meta = meta.merge(m[["match_id", "opponent", "result"]], on="match_id").sort_values("date", ascending=False)
    who = st.radio("Show chases by", ["Pakistan chasing", "Opposition chasing"], horizontal=True)
    meta = meta[meta.chaser == ("Pakistan" if who == "Pakistan chasing" else "Opposition")]
    lab = meta.apply(lambda r: f"{r.date:%d %b %Y} · {r.fmt} · v {r.opponent} · target {int(r.target)} · {r.result}", axis=1)
    pick = st.selectbox("Match", range(len(meta)), format_func=lambda i: lab.iloc[i])
    mm = meta.iloc[pick]
    g = d[d.match_id == mm.match_id].sort_values("over")
    wk = g[g.wkts.diff().fillna(0) > 0]
    f = go.Figure()
    f.add_trace(go.Scatter(x=g.over, y=100 * g.p_pak, mode="lines", name="Pakistan win probability", line=dict(color=T.GREEN, width=4)))
    f.add_trace(go.Scatter(x=wk.over, y=100 * wk.p_pak, mode="markers", name="Wicket fell", marker=dict(symbol="x", size=11, color="#C0392B", line=dict(width=2))))
    f.add_hline(y=50, line_dash="dot", line_color="#6B7A86")
    T.plot(f, f"{mm.date:%d %b %Y} v {mm.opponent}: Pakistan win probability ({'Pakistan' if mm.chaser == 'Pakistan' else mm.opponent} chasing {int(mm.target)})",
           "Overs completed", "Pakistan win probability", ylim=[0, 100], pct=True, h=400, legend="")
    p0, p_end = g.p_pak.iloc[0], g.p_pak.iloc[-1]
    swing = g.p_pak.diff().abs()
    sw = g.loc[swing.idxmax()] if swing.notna().any() else g.iloc[0]
    T.kpis([("Result", mm.result, f"Target {int(mm.target)}", "green" if mm.result == "Won" else "red"),
            ("Win chance at the start", f"{100 * p0:.0f}%", "Before the first ball", "blue"),
            ("Lowest / highest", f"{100 * g.p_pak.min():.0f}% / {100 * g.p_pak.max():.0f}%", "Pakistan during the chase", "gold"),
            ("Biggest swing", f"{100 * swing.max():.0f} pts", f"in over {int(sw.over)}", "grey")], per_row=4)
    g2 = g.assign(need=g.runs_needed).melt("over", ["rrr", "crr"], var_name="line", value_name="rate")
    g2["line"] = g2.line.map({"rrr": "Required run rate", "crr": "Current run rate"})
    T.plot(px.line(g2[g2.over > 0], x="over", y="rate", color="line", color_discrete_sequence=["#C0392B", T.GREEN]).update_traces(line_width=3),
           "Required vs current run rate", "Overs completed", "Runs per over", legend="", h=320)
    T.section("What-if calculator", "type any chase situation")
    c = st.columns(5)
    cf_ = c[0].selectbox("Format", ["T20I", "ODI"], key="cf")
    full = ML.FULL_BALLS[cf_]
    tgt = c[1].number_input("Target", 40, 450, 180 if cf_ == "T20I" else 280)
    ov = c[2].number_input("Overs completed", 0, full // 6, 10 if cf_ == "T20I" else 25)
    rn = c[3].number_input("Runs scored", 0, 450, 80 if cf_ == "T20I" else 130)
    wkc = c[4].number_input("Wickets lost", 0, 10, 3)
    pw = ML.predict_chase(cb, cf_, tgt, rn, wkc, ov * 6)
    T.kpis([("Chasing side win probability", f"{100 * pw:.0f}%", f"Need {tgt - rn} from {full - ov * 6} balls, {10 - wkc} wickets in hand", "green" if pw >= .5 else "red")], per_row=4)
    T.section("Model accuracy", "held-out matches only")
    st.dataframe(cb["metrics"].style.format({"Accuracy": "{:.1%}", "LogLoss": "{:.3f}", "Brier": "{:.3f}", "AUC": "{:.3f}"})
                 .highlight_max(subset=["Accuracy", "AUC"], color="#BFE8CF").highlight_min(subset=["LogLoss", "Brier"], color="#BFE8CF"), hide_index=True, width="stretch")
    st2 = cb["stage"]
    T.plot(px.bar(st2, x="stage", y="AUC", text=st2.AUC.round(2), color_discrete_sequence=[T.GREEN]).update_traces(textposition="outside"),
           "The model gets sharper as the chase goes on", "Stage of the chase", "AUC (ensemble, test matches)", ylim=[0.5, 1.05], h=320)
    T.note("The model only uses the score, wickets and balls left. It knows nothing about the pitch, the batters at the crease or dew, and rain-affected (DLS) matches are excluded. "
           "Curves for matches in the training period are slightly flattering; the table above is the honest test.")

# ======================================================================= 3 SCORE
with tab3:
    sb = ML.score_bundle()
    T.section("First-innings score model", f"{sb['n_train']} matches before {sb['cut']:%d %b %Y} for training, {sb['n_test']} after for testing")
    c = st.columns(4)
    fmt3 = c[0].selectbox("Format", ["T20I", "ODI"], key="sf")
    dd = sb["data"][sb["data"].format == fmt3]
    vcount = dd.venue.value_counts()
    ven = c[1].selectbox("Venue", vcount.index.tolist(), key="sv", format_func=lambda v: f"{v} ({vcount[v]} matches)")
    country = dd[dd.venue == ven].venue_country.iloc[0]
    side = c[2].selectbox("Batting first", ["Pakistan", "Opposition"], key="ss")
    grp3 = c[3].selectbox("Venue type for Pakistan", ["Neutral", "Home", "Away"], key="sg")
    pred, nv = ML.predict_score(sb, fmt3, ven, country, side == "Pakistan", grp3)
    sd = sb["resid_sd"]
    T.kpis([("Predicted first-innings total", f"{pred:.0f}", f"Typical range {pred - sd:.0f} to {pred + sd:.0f}", "green"),
            (f"Past {fmt3} average at this ground", f"{dd[dd.venue == ven].total.mean():.0f}" if nv else "n/a", f"{nv} matches in the data", "blue"),
            (f"All {fmt3} first innings", f"{dd.total.mean():.0f}", f"{len(dd)} matches", "grey")], per_row=3)
    mt = sb["metrics"]
    st.dataframe(mt.style.format({"MAE": "{:.1f}", "RMSE": "{:.1f}", "Within 20 runs %": "{:.0f}%"}).highlight_min(subset=["MAE", "RMSE"], color="#BFE8CF").highlight_max(subset=["Within 20 runs %"], color="#BFE8CF"),
                 hide_index=True, width="stretch")
    T.note("Honest result: predicting a first-innings total is hard. The model improves on a plain format average by only about one run (MAE), because pitch, weather and opposition quality are not in the data. "
           "Use it as a rough 'par' for the venue, not as a forecast.")
    te = sb["test"]
    f = px.scatter(te, x="Ridge regression", y="total", color="format", color_discrete_map=D.FMT_COLORS, hover_data=["opponent", "venue"])
    lim = [0, max(te.total.max(), te["Ridge regression"].max()) * 1.05]
    f.add_shape(type="line", x0=lim[0], y0=lim[0], x1=lim[1], y1=lim[1], line=dict(dash="dot", color="#6B7A86"))
    f.update_traces(marker=dict(size=10, line=dict(width=1, color="white")))
    T.plot(f, "Test matches: predicted vs actual first-innings total", "Predicted total (ridge model)", "Actual total", legend="Format", h=420)
    dpak = sb["data"][(sb["data"].bat_pak == 1)].assign(RAP=lambda x: x.total - x.par)
    f = px.bar(dpak, x="date", y="RAP", color="RAP", color_continuous_scale=T.DIV, range_color=[-80, 80], hover_data=["opponent", "venue", "total", "par"])
    T.plot(f, "Pakistan first innings: runs above model par (bat-first matches)", "Date", "Runs above par", cbar="Runs above par", h=360, hline=0)

# ======================================================================= 4 SHRINKAGE
with tab4:
    T.section("Opponent records with empirical-Bayes shrinkage", "small samples are pulled towards Pakistan's average in the same format")
    c = st.columns(2)
    n0 = c[0].slider("Prior strength (how many 'average' matches to blend in)", 0, 30, 8)
    f4 = c[1].selectbox("Format", ["ODI", "T20I", "Test"], key="eb_f")
    sh = ML.shrink_team_record(m, n0)
    sh = sh[(sh.format == f4)].sort_values("shrunk")
    long = sh.melt(["opponent", "matches"], ["raw", "shrunk"], var_name="Estimate", value_name="Win %")
    long["Estimate"] = long.Estimate.map({"raw": "Raw win %", "shrunk": "Shrunk win %"})
    f = px.bar(long, y="opponent", x="Win %", color="Estimate", barmode="group", orientation="h", text=long["Win %"].round(0).astype(int).astype(str) + "%",
               color_discrete_map={"Raw win %": "#8A949C", "Shrunk win %": T.GREEN}, hover_data=["matches"])
    f.update_traces(textposition="outside"); f.update_xaxes(range=[0, 118], ticksuffix="%")
    T.plot(f, f"{f4}: Pakistan win % vs each opponent, raw and shrunk", "Win % (wins out of wins + losses)", "Opponent", legend="Estimate", h=max(380, 40 * len(sh)), hline=None)
    af = sh[sh.opponent == "Afghanistan"]
    if len(af):
        a = af.iloc[0]
        T.note(f"Afghanistan ({f4}): {int(a.wins)} wins in {int(a.matches)} decisive matches = {a.raw:.0f}% raw. Blending with Pakistan's {f4} average of {a.format_avg:.0f}% gives {a.shrunk:.0f}%. "
               "The fewer the meetings, the more the estimate moves towards the average.")
    st.dataframe(sh.sort_values("matches", ascending=False)[["opponent", "matches", "wins", "raw", "shrunk", "format_avg"]]
                 .rename(columns={"raw": "Raw %", "shrunk": "Shrunk %", "format_avg": "Format avg %"}).style.format({"Raw %": "{:.0f}", "Shrunk %": "{:.0f}", "Format avg %": "{:.0f}"}),
                 hide_index=True, width="stretch")

# ======================================================================= 5 ELO
with tab5:
    T.section("Elo ratings", f"K = {pb['k']} and home advantage = {pb['ha']} points, chosen on matches before {pb['split_date']:%d %b %Y} only")
    e = pb["elo"]
    f = px.line(e, x="date", y="elo_pak_post", color="format", color_discrete_map=D.FMT_COLORS, line_shape="hv")
    f.update_traces(line_width=3)
    T.plot(f, "Pakistan Elo rating after every match", "Date", "Elo rating (start = 1500)", legend="Format", h=400, hline=1500)
    fm = st.radio("Opponent ladder for", ["ODI", "T20I", "Test"], horizontal=True, key="elo_f")
    lad = pd.DataFrame([(o, v) for (fm_, o), v in pb["state"].items() if fm_ == fm and o != "Pakistan"], columns=["Opponent", "Elo"]).sort_values("Elo")
    pk = pb["state"].get((fm, "Pakistan"), 1500)
    lad["vs Pakistan"] = np.where(lad.Elo > pk, "Rated above Pakistan", "Rated below Pakistan")
    f = px.bar(lad, y="Opponent", x="Elo", color="vs Pakistan", orientation="h", color_discrete_map={"Rated above Pakistan": "#C0392B", "Rated below Pakistan": T.GREEN},
               text=lad.Elo.round(0).astype(int))
    f.update_traces(textposition="outside"); f.add_vline(x=pk, line_dash="dot", line_color=T.DARK, annotation_text=f"Pakistan {pk:.0f}")
    f.update_xaxes(range=[min(lad.Elo.min(), pk) - 60, max(lad.Elo.max(), pk) + 70])
    T.plot(f, f"{fm}: current ratings", "Elo rating", "Opponent", legend="", h=max(380, 28 * len(lad)))
    T.note("Important limit: the dataset only contains Pakistan's matches, so every opponent rating is learned from its games AGAINST Pakistan. "
           "That makes ratings relative to Pakistan, not a world ranking, and a team with few meetings (such as Afghanistan) has a rating built on very little evidence.")
    g = pb["grid"].pivot(index="K", columns="HomeAdv", values="LogLoss")
    T.plot(px.imshow(g, text_auto=".3f", color_continuous_scale=T.DIV_R, aspect="auto"), "Parameter search: log-loss on training matches (lower is better)", "Home advantage (Elo points)", "K factor", cbar="Log-loss", h=340)
