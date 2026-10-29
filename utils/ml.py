"""Machine-learning helpers for the Pakistan cricket dashboard.

Everything here uses ALL data (the sidebar filters do not apply) and only information that was known BEFORE
each match / ball (no leakage). Models are small on purpose: ~480 matches is not a lot of data.
"""
import re

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, mean_absolute_error, roc_auc_score, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from utils import data as D

TEST_FRACTION = 0.25
FULL_BALLS = {"ODI": 300, "T20I": 120}


def venue_group(loc):
    s = str(loc)
    return "Home" if s.startswith("Home") else ("Away" if s == "Away" else "Neutral")


def _clip(p):
    return np.clip(p, 1e-4, 1 - 1e-4)


def _metrics(y, p):
    p = _clip(np.asarray(p, float))
    out = dict(Accuracy=accuracy_score(y, p >= 0.5), LogLoss=log_loss(y, p, labels=[0, 1]), Brier=brier_score_loss(y, p))
    out["AUC"] = roc_auc_score(y, p) if len(set(y)) > 1 else np.nan
    return out


# ------------------------------------------------------------------ 1. ELO
def elo_run(m, k=20.0, ha=50.0, start=1500.0):
    """Sequential Elo, one rating ladder per format. Opponent ratings only move through their games vs Pakistan."""
    r = {}
    rows = []
    for x in m.sort_values(["date", "match_id"], kind="stable").itertuples():
        if x.result not in ("Won", "Lost", "Tied", "Draw"):
            continue
        key_p, key_o = (x.format, "Pakistan"), (x.format, x.opponent)
        rp, ro = r.get(key_p, start), r.get(key_o, start)
        g = venue_group(x.location_type)
        hp = ha if g == "Home" else (-ha if g == "Away" else 0.0)
        p = 1 / (1 + 10 ** (-(rp - ro + hp) / 400))
        s = 1.0 if x.result == "Won" else (0.0 if x.result == "Lost" else 0.5)
        r[key_p], r[key_o] = rp + k * (s - p), ro - k * (s - p)
        rows.append((x.match_id, x.date, x.format, x.opponent, g, rp, ro, hp, p, s, r[key_p], r[key_o]))
    cols = ["match_id", "date", "format", "opponent", "venue_group", "elo_pak_pre", "elo_opp_pre", "ha_pts", "p_elo", "score", "elo_pak_post", "elo_opp_post"]
    return pd.DataFrame(rows, columns=cols), r


def fit_elo_params(m, split_date):
    """Choose K and home advantage by log-loss on matches BEFORE split_date only."""
    best, grid = None, []
    for k in (8, 12, 16, 20, 28, 36, 48):
        for ha in (0, 25, 50, 75, 100):
            e, _ = elo_run(m, k, ha)
            t = e[(e.date < split_date) & e.score.isin([0.0, 1.0])]
            if len(t) < 30:
                continue
            ll = log_loss(t.score, _clip(t.p_elo), labels=[0, 1])
            grid.append((k, ha, ll))
            if best is None or ll < best[2]:
                best = (k, ha, ll)
    return best, pd.DataFrame(grid, columns=["K", "HomeAdv", "LogLoss"])


# ------------------------------------------------------------------ 3. PRE-MATCH MODEL
FEATURES = ["is_odi", "is_t20", "is_home", "is_away", "toss_won", "bat_first", "knockout", "elo_diff", "form10", "h2h"]
FEATURE_LABELS = {"is_odi": "Format: ODI", "is_t20": "Format: T20I", "is_home": "Playing at home", "is_away": "Playing away", "toss_won": "Pakistan won toss",
                  "bat_first": "Pakistan bat first", "knockout": "Knockout match", "elo_diff": "Elo difference (incl. home edge)",
                  "form10": "Pakistan form (last 10)", "h2h": "Head-to-head record (shrunk)"}


def _prematch_frame(m, elo):
    d = m[m.result.isin(["Won", "Lost"])].sort_values(["date", "match_id"], kind="stable").merge(
        elo[["match_id", "elo_pak_pre", "elo_opp_pre", "ha_pts", "p_elo"]], on="match_id", how="inner")
    d = d.reset_index(drop=True)
    d["y"] = (d.result == "Won").astype(int)
    g = d.location_type.map(venue_group)
    d["is_odi"], d["is_t20"] = (d.format == "ODI").astype(int), (d.format == "T20I").astype(int)
    d["is_home"], d["is_away"] = (g == "Home").astype(int), (g == "Away").astype(int)
    d["toss_won"] = d.pak_won_toss.fillna(False).astype(int)
    d["bat_first"] = d.pak_batting_order.eq("Batting first").astype(int)
    d["knockout"] = d.is_knockout.fillna(False).astype(int)
    d["elo_diff"] = d.elo_pak_pre - d.elo_opp_pre + d.ha_pts
    d["form10"] = d.y.shift(1).rolling(10, min_periods=1).mean().fillna(0.5)
    w = d.groupby("opponent").y.transform(lambda s: s.shift(1).fillna(0).cumsum())
    n = d.groupby("opponent").y.transform(lambda s: s.shift(1).notna().cumsum())
    d["h2h"] = (w + 3 * 0.5) / (n + 3)
    return d


def _calibration(y, p, bins=5):
    d = pd.DataFrame({"y": y, "p": p})
    d["bin"] = pd.qcut(d.p, bins, duplicates="drop")
    c = d.groupby("bin", observed=True).agg(predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size")).reset_index(drop=True)
    return c


@st.cache_data(show_spinner="Training pre-match models ...")
def prematch_bundle():
    m, _, _ = D.load()
    dec = m[m.result.isin(["Won", "Lost"])].sort_values("date")
    split_date = dec.date.iloc[int(len(dec) * (1 - TEST_FRACTION))]
    (k, ha, _), grid = fit_elo_params(m, split_date)
    elo, state = elo_run(m, k, ha)
    d = _prematch_frame(m, elo)
    tr, te = d[d.date < split_date], d[d.date >= split_date]
    X_tr, X_te, y_tr, y_te = tr[FEATURES], te[FEATURES], tr.y, te.y

    def mk_lr(): return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=1000))
    def mk_gb(): return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=15, l2_regularization=1.0, random_state=0)

    lr, gb = mk_lr().fit(X_tr, y_tr), mk_gb().fit(X_tr, y_tr)
    preds = pd.DataFrame({"match_id": te.match_id.values, "date": te.date.values, "opponent": te.opponent.values, "format": te.format.values, "y": y_te.values,
                          "Baseline (always base rate)": y_tr.mean(), "Elo only": te.p_elo.values,
                          "Logistic regression": lr.predict_proba(X_te)[:, 1], "Gradient boosting": gb.predict_proba(X_te)[:, 1]})
    models = ["Baseline (always base rate)", "Elo only", "Logistic regression", "Gradient boosting"]
    metrics = pd.DataFrame({n: _metrics(y_te, preds[n]) for n in models}).T.reset_index().rename(columns={"index": "Model"})
    coef = pd.DataFrame({"Feature": [FEATURE_LABELS[f] for f in FEATURES], "Effect": lr[-1].coef_[0]}).sort_values("Effect")
    pi = permutation_importance(gb, X_te, y_te, n_repeats=15, random_state=0, scoring="neg_log_loss")
    imp = pd.DataFrame({"Feature": [FEATURE_LABELS[f] for f in FEATURES], "Importance": pi.importances_mean, "Std": pi.importances_std}).sort_values("Importance")
    calib = {n: _calibration(y_te.values, preds[n].values, 4) for n in models[1:]}
    # live models: refit on every decisive match
    lr_all, gb_all = mk_lr().fit(d[FEATURES], d.y), mk_gb().fit(d[FEATURES], d.y)
    # current state for the predictor
    last10 = float(d.y.tail(10).mean())
    h2h_now = {}
    for o, g in d.groupby("opponent"):
        h2h_now[o] = (g.y.sum() + 1.5) / (len(g) + 3)
    return dict(split_date=split_date, k=k, ha=ha, grid=grid, elo=elo, state=state, data=d, n_train=len(tr), n_test=len(te), base_rate=float(y_tr.mean()),
                preds=preds, metrics=metrics, coef=coef, imp=imp, calib=calib, lr=lr_all, gb=gb_all, form_now=last10, h2h_now=h2h_now,
                opponents=sorted(m.opponent.unique()))


def predict_prematch(bundle, fmt, opponent, group, toss_won, bat_first, knockout=False):
    s = bundle["state"]
    rp, ro = s.get((fmt, "Pakistan"), 1500.0), s.get((fmt, opponent), 1500.0)
    ha = bundle["ha"] if group == "Home" else (-bundle["ha"] if group == "Away" else 0.0)
    diff = rp - ro + ha
    row = pd.DataFrame([dict(is_odi=int(fmt == "ODI"), is_t20=int(fmt == "T20I"), is_home=int(group == "Home"), is_away=int(group == "Away"),
                             toss_won=int(toss_won), bat_first=int(bat_first), knockout=int(knockout), elo_diff=diff,
                             form10=bundle["form_now"], h2h=bundle["h2h_now"].get(opponent, 0.5))])
    return dict(Elo=1 / (1 + 10 ** (-diff / 400)), LR=float(bundle["lr"].predict_proba(row)[0, 1]), GB=float(bundle["gb"].predict_proba(row)[0, 1]),
                elo_pak=rp, elo_opp=ro, diff=diff)


# ------------------------------------------------------------------ 4. IN-MATCH WIN PROBABILITY
CHASE_FEATURES = ["runs_needed", "balls_left", "wkts_left", "rrr", "crr", "rrr_minus_crr", "target", "is_t20", "pressure"]


def _chase_rows():
    m, _, _ = D.load()
    o = D.load_extra()["overs"]
    ok = m[m.format.isin(["ODI", "T20I"]) & m.result.isin(["Won", "Lost"])]
    if "dls_method" in ok:
        ok = ok[~ok.dls_method.fillna(False).astype(bool)]
    info = ok.set_index("match_id")[["format", "result", "date", "opponent"]]
    o = o[o.match_id.isin(info.index) & o.innings_no.isin([1, 2])].sort_values(["match_id", "innings_no", "over"])
    rows = []
    for mid, g in o.groupby("match_id"):
        i1, i2 = g[g.innings_no == 1], g[g.innings_no == 2]
        if i1.empty or i2.empty:
            continue
        fmt, res = info.loc[mid, "format"], info.loc[mid, "result"]
        full = FULL_BALLS[fmt]
        target = int(i1.cum_runs.max()) + 1
        chaser = i2.side.iloc[0]
        won = (res == "Won") if chaser == "Pakistan" else (res == "Lost")
        balls = i2.legal_balls.cumsum().values
        states = [(0, 0, 0, 0)] + list(zip(range(1, len(i2) + 1), i2.cum_runs.values, i2.cum_wkts.values, balls))
        for ov, runs, wk, b in states:
            left = max(full - b, 0)
            need = target - runs
            crr = runs / b * 6 if b else 0.0
            rrr = need / left * 6 if left else (99.0 if need > 0 else 0.0)
            rows.append(dict(match_id=mid, format=fmt, date=info.loc[mid, "date"], chaser=chaser, over=ov, runs=runs, wkts=wk, balls=b, target=target,
                             runs_needed=need, balls_left=left, wkts_left=10 - wk, rrr=min(rrr, 36.0), crr=crr, rrr_minus_crr=min(rrr, 36.0) - crr,
                             is_t20=int(fmt == "T20I"), pressure=need / max(10 - wk, 1) / max(left, 1) * 6, y=int(won)))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Building in-match win-probability model ...")
def chase_bundle():
    d = _chase_rows()
    mids = d.groupby("match_id").date.first().sort_values()
    cut = mids.iloc[int(len(mids) * (1 - TEST_FRACTION))]
    tr, te = d[d.date < cut], d[d.date >= cut]
    lr = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(tr[CHASE_FEATURES], tr.y)
    gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=150, min_samples_leaf=40, l2_regularization=1.0, random_state=0).fit(tr[CHASE_FEATURES], tr.y)
    te = te.assign(p_lr=lr.predict_proba(te[CHASE_FEATURES])[:, 1], p_gb=gb.predict_proba(te[CHASE_FEATURES])[:, 1])
    te["p_ens"] = (te.p_lr + te.p_gb) / 2
    base = float(tr.y.mean())
    rows = []
    for name, col in (("Baseline (base rate)", None), ("Logistic regression", "p_lr"), ("Gradient boosting", "p_gb"), ("Average of both", "p_ens")):
        p = np.full(len(te), base) if col is None else te[col].values
        rows.append(dict(Model=name, **_metrics(te.y, p)))
    # accuracy by stage of the chase
    te["stage"] = pd.cut(te.balls / te.format.map(FULL_BALLS), [-0.01, 0.25, 0.5, 0.75, 1.01], labels=["First quarter", "Second quarter", "Third quarter", "Final quarter"])
    stage = te.groupby("stage", observed=True).apply(lambda g: pd.Series(dict(AUC=roc_auc_score(g.y, g.p_ens) if g.y.nunique() > 1 else np.nan,
                                                                              Accuracy=accuracy_score(g.y, g.p_ens >= 0.5), States=len(g))), include_groups=False).reset_index()
    lr_all = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(d[CHASE_FEATURES], d.y)
    gb_all = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=150, min_samples_leaf=40, l2_regularization=1.0, random_state=0).fit(d[CHASE_FEATURES], d.y)
    d = d.assign(p_chaser=(lr_all.predict_proba(d[CHASE_FEATURES])[:, 1] + gb_all.predict_proba(d[CHASE_FEATURES])[:, 1]) / 2)
    d["p_pak"] = np.where(d.chaser == "Pakistan", d.p_chaser, 1 - d.p_chaser)
    return dict(data=d, metrics=pd.DataFrame(rows), stage=stage, cut=cut, n_matches=d.match_id.nunique(), n_states=len(d), n_test_matches=te.match_id.nunique(),
                lr=lr_all, gb=gb_all)


def predict_chase(cb, fmt, target, runs, wkts, balls):
    full = FULL_BALLS[fmt]
    left, need = max(full - balls, 0), target - runs
    crr = runs / balls * 6 if balls else 0.0
    rrr = min(need / left * 6, 36.0) if left else (36.0 if need > 0 else 0.0)
    row = pd.DataFrame([dict(runs_needed=need, balls_left=left, wkts_left=10 - wkts, rrr=rrr, crr=crr, rrr_minus_crr=rrr - crr, target=target,
                             is_t20=int(fmt == "T20I"), pressure=need / max(10 - wkts, 1) / max(left, 1) * 6)])
    return float((cb["lr"].predict_proba(row[CHASE_FEATURES])[0, 1] + cb["gb"].predict_proba(row[CHASE_FEATURES])[0, 1]) / 2)


# ------------------------------------------------------------------ 5. FIRST-INNINGS SCORE
@st.cache_data(show_spinner="Training first-innings score models ...")
def score_bundle():
    m, _, _ = D.load()
    d = m[m.format.isin(["ODI", "T20I"]) & m.pak_batting_order.notna() & m.pak_runs.notna() & m.opp_runs.notna()].copy()
    d["bat_pak"] = d.pak_batting_order.eq("Batting first").astype(int)
    d["total"] = np.where(d.bat_pak == 1, d.pak_runs, d.opp_runs)
    d = d[d.total > 0].sort_values(["date", "match_id"], kind="stable").reset_index(drop=True)
    d["grp"] = d.location_type.map(venue_group)
    fm = d.groupby("format").total.transform(lambda s: s.expanding().mean().shift(1)).fillna(d.groupby("format").total.transform("mean"))

    def prior(col, k):
        g = d.groupby(["format", col]).total
        cs, cn = g.transform(lambda s: s.shift(1).fillna(0).cumsum()), g.transform(lambda s: s.shift(1).notna().cumsum())
        return (cs + k * fm) / (cn + k)

    d["venue_prior"], d["country_prior"] = prior("venue", 6), prior("venue_country", 10)
    d["is_t20"] = (d.format == "T20I").astype(int)
    d["is_home"], d["is_away"] = (d.grp == "Home").astype(int), (d.grp == "Away").astype(int)
    d["trend"] = d.year - 2015
    feats = ["is_t20", "bat_pak", "venue_prior", "country_prior", "is_home", "is_away", "trend"]
    cut = d.date.iloc[int(len(d) * (1 - TEST_FRACTION))]
    tr, te = d[d.date < cut], d[d.date >= cut]
    base = tr.groupby("format").total.mean()
    rid = make_pipeline(StandardScaler(), Ridge(alpha=5.0)).fit(tr[feats], tr.total)
    gbr = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=120, min_samples_leaf=15, l2_regularization=1.0, random_state=0).fit(tr[feats], tr.total)
    pr = pd.DataFrame({"Format-average baseline": te.format.map(base).values, "Ridge regression": rid.predict(te[feats]), "Gradient boosting": gbr.predict(te[feats])})
    res = []
    for n in pr:
        e = te.total.values - pr[n].values
        res.append(dict(Model=n, MAE=np.abs(e).mean(), RMSE=np.sqrt((e ** 2).mean()), **{"Within 20 runs %": 100 * (np.abs(e) <= 20).mean()}))
    rid_all = make_pipeline(StandardScaler(), Ridge(alpha=5.0)).fit(d[feats], d.total)
    gbr_all = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=120, min_samples_leaf=15, l2_regularization=1.0, random_state=0).fit(d[feats], d.total)
    d["par"] = rid_all.predict(d[feats])
    resid_sd = float(np.std(d.total - d.par))
    return dict(data=d, feats=feats, metrics=pd.DataFrame(res), cut=cut, n_train=len(tr), n_test=len(te), rid=rid_all, gbr=gbr_all, resid_sd=resid_sd, test=te.assign(**pr.set_index(te.index)),
                venues=d.groupby(["format", "venue"]).total.agg(["size", "mean"]).reset_index())


def predict_score(sb, fmt, venue, country, bat_pak, group):
    d = sb["data"]
    ff = d[d.format == fmt].total
    fm = ff.mean()
    v = d[(d.format == fmt) & (d.venue == venue)].total
    c = d[(d.format == fmt) & (d.venue_country == country)].total
    row = pd.DataFrame([dict(is_t20=int(fmt == "T20I"), bat_pak=int(bat_pak), venue_prior=(v.sum() + 6 * fm) / (len(v) + 6), country_prior=(c.sum() + 10 * fm) / (len(c) + 10),
                             is_home=int(group == "Home"), is_away=int(group == "Away"), trend=d.year.max() - 2015)])
    return float(sb["rid"].predict(row[sb["feats"]])[0]), len(v)


# ------------------------------------------------------------------ 2. EMPIRICAL BAYES
def shrink_team_record(m, n0=8):
    d = m[m.result.isin(["Won", "Lost"])]
    out = []
    for f, g in d.groupby("format"):
        p0 = (g.result == "Won").mean()
        for o, h in g.groupby("opponent"):
            w, n = int((h.result == "Won").sum()), len(h)
            out.append(dict(format=f, opponent=o, matches=n, wins=w, raw=100 * w / n, shrunk=100 * (w + n0 * p0) / (n + n0), format_avg=100 * p0))
    return pd.DataFrame(out)


def shrink_batter_vs_opponent(b, opponent, k=6.0, min_inns=1):
    tot = b.groupby("player").agg(runs=("runs", "sum"), outs=("is_out", "sum"))
    tot["avg_all"] = tot.runs / tot.outs.clip(lower=1)
    x = b[b.opponent == opponent].groupby("player").agg(inns=("runs", "size"), runs=("runs", "sum"), outs=("is_out", "sum")).reset_index()
    x = x[x.inns >= min_inns].merge(tot[["avg_all"]], left_on="player", right_index=True)
    x["raw_avg"] = x.runs / x.outs.replace(0, np.nan)
    x["shrunk_avg"] = (x.runs + k * x.avg_all) / (x.outs + k)
    return x.sort_values("runs", ascending=False)


def shrink_bowler_vs_opponent(w, opponent, k=4.0, min_spells=1):
    tot = w.groupby("player").agg(wk=("wickets", "sum"), sp=("wickets", "size"))
    tot["rate_all"] = tot.wk / tot.sp
    x = w[w.opponent == opponent].groupby("player").agg(spells=("wickets", "size"), wkts=("wickets", "sum")).reset_index()
    x = x[x.spells >= min_spells].merge(tot[["rate_all"]], left_on="player", right_index=True)
    x["raw_rate"] = x.wkts / x.spells
    x["shrunk_rate"] = (x.wkts + k * x.rate_all) / (x.spells + k)
    return x.sort_values("wkts", ascending=False)


# ------------------------------------------------------------------ 6/7. PROFILES, CLUSTERS, SIMILARITY
BAT_FEATS = ["Runs/inn", "Strike rate", "Boundary %", "Balls/inn", "50+ rate %", "Avg position", "Sixes/inn"]
BOWL_FEATS = ["Econ", "Strike rate", "Wkts/spell", "Dot %", "Boundary % conceded", "Balls/spell"]


def batting_profile(b, fmt, min_inns):
    x = b if fmt == "All" else b[b.format == fmt]
    g = x.groupby("player").agg(Inns=("runs", "size"), Runs=("runs", "sum"), Balls=("balls", "sum"), Fours=("fours", "sum"), Sixes=("sixes", "sum"),
                                f50=("is_fifty", "sum"), f100=("is_hundred", "sum"), Pos=("batting_position", "mean"), Outs=("is_out", "sum")).reset_index()
    g = g[(g.Inns >= min_inns) & (g.Balls > 0)]
    g["Runs/inn"] = g.Runs / g.Inns
    g["Strike rate"] = 100 * g.Runs / g.Balls
    g["Boundary %"] = 100 * (g.Fours * 4 + g.Sixes * 6) / g.Runs.clip(lower=1)
    g["Balls/inn"] = g.Balls / g.Inns
    g["50+ rate %"] = 100 * (g.f50 + g.f100) / g.Inns
    g["Avg position"] = g.Pos
    g["Sixes/inn"] = g.Sixes / g.Inns
    g["Average"] = g.Runs / g.Outs.clip(lower=1)
    return g.set_index("player")


def bowling_profile(w, fmt, min_spells):
    x = w if fmt == "All" else w[w.format == fmt]
    x = x.assign(_dbase=x.balls.where(x.dot_balls.notna(), 0), _bbase=x.runs_conceded.where(x.fours_conceded.notna(), 0))   # only rows that record dots / boundaries
    g = x.groupby("player").agg(Spells=("wickets", "size"), Balls=("balls", "sum"), Runs=("runs_conceded", "sum"), Wkts=("wickets", "sum"), Dots=("dot_balls", "sum"),
                                F4=("fours_conceded", "sum"), S6=("sixes_conceded", "sum"), DotBase=("_dbase", "sum"), BdryBase=("_bbase", "sum")).reset_index()
    g = g[(g.Spells >= min_spells) & (g.Balls > 0)]
    g["Econ"] = 6 * g.Runs / g.Balls
    g["Strike rate"] = g.Balls / g.Wkts.clip(lower=0.5)
    g["Wkts/spell"] = g.Wkts / g.Spells
    g["Dot %"] = 100 * g.Dots / g.DotBase.clip(lower=1)
    g["Boundary % conceded"] = 100 * (g.F4 * 4 + g.S6 * 6) / g.BdryBase.clip(lower=1)
    g["Balls/spell"] = g.Balls / g.Spells
    g["Average"] = g.Runs / g.Wkts.clip(lower=0.5)
    return g.set_index("player")


def cluster_players(prof, feats, k, kind="bat"):
    X = StandardScaler().fit_transform(prof[feats])
    km = KMeans(n_clusters=k, n_init=25, random_state=0).fit(X)
    sil = float(silhouette_score(X, km.labels_)) if 1 < k < len(prof) else np.nan
    z = pd.DataFrame(km.cluster_centers_, columns=feats)
    cent_orig = pd.DataFrame(StandardScaler().fit(prof[feats]).inverse_transform(km.cluster_centers_), columns=feats)
    names = {}
    for c in range(k):
        r = z.loc[c]
        if kind == "bat":
            pos = cent_orig.loc[c, "Avg position"]
            band = "Top-order" if pos <= 3.2 else ("Middle-order" if pos <= 5.5 else "Lower-order")
            if r["Strike rate"] > 0.45: style = "power hitter"
            elif r["Balls/inn"] > 0.3 and r["Strike rate"] < 0.3: style = "anchor"
            else: style = "accumulator"
            tag = f"{band} {style}"
        else:
            if r["Wkts/spell"] > 0.45 and r["Strike rate"] < -0.2: tag = "Strike bowler"
            elif r["Econ"] < -0.4 and r["Dot %"] > 0.2: tag = "Holding / economical"
            elif r["Balls/spell"] > 0.5: tag = "Workhorse"
            elif r["Econ"] > 0.5: tag = "Expensive / attacking"
            else: tag = "Support bowler"
        names[c] = tag
    used = {}
    final = {}
    for c, t in names.items():
        used[t] = used.get(t, 0) + 1
        final[c] = f"{t}" if list(names.values()).count(t) == 1 else f"{t} ({used[t]})"
    lab = pd.Series([final[c] for c in km.labels_], index=prof.index, name="Role")
    pc = PCA(n_components=2, random_state=0).fit(X)
    xy = pd.DataFrame(pc.transform(X), columns=["PC1", "PC2"], index=prof.index)
    cent = pd.DataFrame(StandardScaler().fit(prof[feats]).inverse_transform(km.cluster_centers_), columns=feats)
    cent.insert(0, "Role", [final[c] for c in range(k)])
    cent.insert(1, "Players", np.bincount(km.labels_, minlength=k))
    return lab, xy, cent, sil, pc.explained_variance_ratio_


def similar_players(prof, feats, player, n=8):
    X = pd.DataFrame(StandardScaler().fit_transform(prof[feats]), index=prof.index, columns=feats)
    d = np.sqrt(((X - X.loc[player]) ** 2).sum(axis=1)).drop(player).sort_values().head(n)
    out = prof.loc[d.index, feats].copy()
    out.insert(0, "Similarity %", (100 * np.exp(-d / np.sqrt(len(feats)))).round(1))
    return out


def percentile_profile(prof, feats, players, invert=()):
    pct = prof[feats].rank(pct=True) * 100
    for f in invert:
        pct[f] = 100 - pct[f]
    return pct.loc[players]


# ------------------------------------------------------------------ 8. SURVIVAL (Kaplan-Meier on balls faced)
def kaplan_meier(durations, events):
    d = pd.DataFrame({"t": np.maximum(np.asarray(durations, float), 1), "e": np.asarray(events, int)})
    g = d.groupby("t").agg(deaths=("e", "sum"), n=("e", "size")).sort_index()
    at_risk = len(d) - g.n.cumsum().shift(1, fill_value=0)
    s = (1 - g.deaths / at_risk).cumprod()
    out = pd.DataFrame({"balls": g.index, "survival": s.values, "at_risk": at_risk.values, "deaths": g.deaths.values})
    return pd.concat([pd.DataFrame({"balls": [0], "survival": [1.0], "at_risk": [len(d)], "deaths": [0]}), out], ignore_index=True)


def km_at(km, t):
    x = km[km.balls <= t]
    return float(x.survival.iloc[-1]) if len(x) else 1.0


def km_median(km):
    x = km[km.survival <= 0.5]
    return float(x.balls.iloc[0]) if len(x) else np.nan


# ------------------------------------------------------------------ 9. MATCH-UP MODEL (approximation: no ball-by-ball data)
_BOWLER_RE = re.compile(r"(?:^|\s)b\s+(.+)$")


def _pair_exposure(bat, bowl):
    """Estimated balls each batter faced from each bowler: batter balls x bowler share of the innings' balls."""
    bw = bowl.groupby(["match_id", "innings_no", "player"], as_index=False).balls.sum().rename(columns={"player": "bowler", "balls": "bowler_balls"})
    tot = bw.groupby(["match_id", "innings_no"]).bowler_balls.transform("sum")
    bw["share"] = bw.bowler_balls / tot
    x = bat[["match_id", "innings_no", "player", "balls"]].merge(bw[["match_id", "innings_no", "bowler", "share"]], on=["match_id", "innings_no"])
    x["E"] = x.balls * x.share
    return x


@st.cache_data(show_spinner="Estimating batter vs bowler match-ups ...")
def matchup_bundle():
    m, b, w = D.load()
    ob, ow, _ = D.load_opp()
    out = {}
    # A) Pakistan batters vs opposition bowlers
    if len(ow):
        e = _pair_exposure(b, ow)
        dis = b[b.is_out & b.dismissed_by.notna()].groupby(["player", "dismissed_by"]).size().rename("D").reset_index().rename(columns={"dismissed_by": "bowler"})
        out["bat_vs_opp_bowl"] = _finish(e.groupby(["player", "bowler"], as_index=False).E.sum(), dis, "player", "bowler")
    # B) Pakistan bowlers vs opposition batters
    if len(ob):
        ob2 = ob.copy()
        ob2["bowler"] = ob2.dismissal.fillna("").str.extract(_BOWLER_RE)[0]
        ob2["credited"] = ob2.is_out & ob2.bowler.notna()
        e = _pair_exposure(ob2, w).rename(columns={"player": "batter"})
        dis = ob2[ob2.credited].groupby(["player", "bowler"]).size().rename("D").reset_index().rename(columns={"player": "batter"})
        out["bowl_vs_opp_bat"] = _finish(e.groupby(["bowler", "batter"], as_index=False).E.sum(), dis, "bowler", "batter")
    return out


def add_rate(t, k=60.0):
    """Gamma-Poisson shrinkage: posterior dismissal rate per 100 balls with a prior worth k balls at the expected (generic) rate."""
    t = t.copy()
    t["rate100"] = 100 * (t.D + k * t.base) / (t.E + k)
    t["index"] = t.rate100 / t.base100
    return t


def _finish(E, D_, a, c):
    t = E.merge(D_, on=[a, c], how="left").fillna({"D": 0})
    t = t[t.E > 0]
    lam = t.D.sum() / t.E.sum()
    ra = t.groupby(a).apply(lambda g: g.D.sum() / g.E.sum(), include_groups=False)   # dismissal rate per ball of side a
    rc = t.groupby(c).apply(lambda g: g.D.sum() / g.E.sum(), include_groups=False)
    t["base"] = (t[a].map(ra) * t[c].map(rc) / lam).clip(lower=1e-4)
    t["expected"] = t.E * t.base
    t["base100"] = 100 * t.base
    return add_rate(t)
