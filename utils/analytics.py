"""Derived analytics: runs above par, form guide, batting roles. Pure pandas (+ cached loaders)."""
import numpy as np
import pandas as pd
import streamlit as st

from utils import data as D

BUCKETS = ["Openers (1-2)", "No. 3", "Middle (4-5)", "Lower-middle (6-7)", "Tail (8-11)"]
SHRINK_K = 30  # a venue-country par counts as K "virtual" innings of the format-wide par


def bucket(pos):
    return pd.cut(pos, [0, 2, 3, 5, 7, 11], labels=BUCKETS).astype("object")


@st.cache_data(show_spinner=False)
def par_tables():
    """Average runs per innings by format x venue country x batting-position bucket, using BOTH sides' batters."""
    m, b, _ = D.load()
    ob, _, _ = D.load_opp()
    cols = ["match_id", "format", "batting_position", "runs"]
    a = pd.concat([b[cols], ob[cols]] if len(ob) else [b[cols]])
    a = a.merge(m[["match_id", "venue_country"]].drop_duplicates("match_id"), on="match_id", how="left")
    a["bucket"] = bucket(a.batting_position)
    a = a.dropna(subset=["bucket"])
    t = a.groupby(["format", "venue_country", "bucket"]).runs.agg(venue_mean="mean", venue_n="size").reset_index()
    c = a.groupby(["format", "bucket"]).runs.mean().rename("fmt_par").reset_index()
    return t, c


def with_rap(b):
    """Adds bucket, exp_runs (expected runs for that format / venue country / position) and rap (runs above par)."""
    t, c = par_tables()
    m = D.load()[0]
    x = b.drop(columns=["venue_country"], errors="ignore").merge(m[["match_id", "venue_country"]].drop_duplicates("match_id"), on="match_id", how="left")
    x["bucket"] = bucket(x.batting_position)
    x = x.dropna(subset=["bucket"]).merge(t, on=["format", "venue_country", "bucket"], how="left").merge(c, on=["format", "bucket"], how="left")
    n = x.venue_n.fillna(0)
    x["exp_runs"] = (n * x.venue_mean.fillna(0) + SHRINK_K * x.fmt_par) / (n + SHRINK_K)
    x["rap"] = x.runs - x.exp_runs
    return x


def rap_table(x, by=("player",)):
    by = list(by)
    t = x.groupby(by).agg(Inns=("runs", "size"), Runs=("runs", "sum"), Expected=("exp_runs", "sum"), RAP=("rap", "sum")).reset_index()
    t["RAP/inn"] = (t.RAP / t.Inns).round(1)
    t["Expected"] = t.Expected.round(0)
    t["RAP"] = t.RAP.round(0)
    return t


# ----------------------------------------------------------------- form
def _scores(g):
    return ", ".join(f"{int(r)}{'' if o else '*'}" for r, o in zip(g.runs, g.is_out))


def batting_form(b, n=5, min_inns=15, active_days=540, hot=10.0):
    x = with_rap(b).sort_values(["date", "innings_no"])
    if x.empty: return pd.DataFrame()
    last = x.date.max()
    rows = []
    for p, g in x.groupby("player"):
        if len(g) < min_inns or (last - g.date.max()).days > active_days: continue
        l, l10 = g.tail(n), g.tail(10)
        rows.append({"Player": p, "Inns": len(g), "Last-5 scores": _scores(l), "Last-5 RAP/inn": round(l.rap.mean(), 1),
                     "Career RAP/inn": round(g.rap.mean(), 1), "20+ rate": round(100 * (g.runs >= 20).mean(), 0),
                     "20+ rate (last 10)": round(100 * (l10.runs >= 20).mean(), 0)})
    f = pd.DataFrame(rows)
    if f.empty: return f
    f["Form change"] = (f["Last-5 RAP/inn"] - f["Career RAP/inn"]).round(1)
    f["Status"] = np.where(f["Last-5 RAP/inn"] >= hot, "🔥 Hot", np.where(f["Last-5 RAP/inn"] <= -hot, "❄️ Cold", "➖ Steady"))
    return f.sort_values("Last-5 RAP/inn", ascending=False)


def bowling_form(w, n=5, min_spells=15, active_days=540):
    x = w.sort_values(["date", "innings_no"])
    if x.empty: return pd.DataFrame()
    last = x.date.max()
    rows = []
    for p, g in x.groupby("player"):
        if len(g) < min_spells or (last - g.date.max()).days > active_days: continue
        l = g.tail(n)
        cw, lw = g.wickets.mean(), l.wickets.mean()
        ce, le = 6 * g.runs_conceded.sum() / max(g.balls.sum(), 1), 6 * l.runs_conceded.sum() / max(l.balls.sum(), 1)
        if lw >= 1.3 * cw and le <= ce + 1: s = "🔥 Hot"
        elif lw <= 0.6 * cw or le >= ce + 1.5: s = "❄️ Cold"
        else: s = "➖ Steady"
        rows.append({"Player": p, "Spells": len(g), "Last-5 (wkts/runs)": ", ".join(f"{int(a)}/{int(r)}" for a, r in zip(l.wickets, l.runs_conceded)),
                     "Wkts per spell (career)": round(cw, 2), "Wkts per spell (last 5)": round(lw, 2),
                     "Econ (career)": round(ce, 2), "Econ (last 5)": round(le, 2), "Status": s})
    return pd.DataFrame(rows).sort_values("Wkts per spell (last 5)", ascending=False)


# ----------------------------------------------------------------- roles
def position_table(b, by=("format", "bucket")):
    x = b.assign(bucket=bucket(b.batting_position)).dropna(subset=["bucket"])
    by = list(by)
    t = x.groupby(by).agg(Inns=("runs", "size"), Runs=("runs", "sum"), Balls=("balls", "sum"), Outs=("is_out", "sum"),
                          f50=("is_fifty", "sum"), f100=("is_hundred", "sum")).reset_index()
    t["Runs/inn"] = (t.Runs / t.Inns).round(1)
    t["Avg"] = (t.Runs / t.Outs.where(t.Outs > 0)).round(1)
    t["SR"] = (100 * t.Runs / t.Balls.where(t.Balls > 0)).round(1)
    t["50+ rate %"] = (100 * (t.f50 + t.f100) / t.Inns).round(1)
    grp = [c for c in by if c != "bucket"]
    tot = t.groupby(grp).Runs.transform("sum") if grp else t.Runs.sum()
    t["Share of runs %"] = (100 * t.Runs / tot).round(1)
    t["bucket"] = pd.Categorical(t.bucket, BUCKETS, ordered=True)
    return t.sort_values(grp + ["bucket"]) if grp else t.sort_values("bucket")
