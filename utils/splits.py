"""Player split tables (SENA, England, Home, Away ...) built from the dashboard CSVs.

Pure pandas, no Streamlit, so it is used both by the dashboard page and by
scripts/build_player_splits.py.

A "split" is a condition filter. One match can belong to several splits
(e.g. a Test at Lord's is in "All matches", "Away" and "England" and "SENA"),
so the long table from expand() repeats rows on purpose. Never add up
different splits of the same player.
"""
import numpy as np
import pandas as pd

SENA = ["South Africa", "England", "New Zealand", "Australia"]


def _country(*names):
    return lambda d: d.venue_country.isin(names)


# name -> function(df) -> boolean mask. df needs venue_country and location_type.
SPLITS = {
    "All matches": lambda d: pd.Series(True, index=d.index),
    "Home (Pakistan)": _country("Pakistan"),
    "Home (incl. UAE)": lambda d: d.location_type.str.startswith("Home"),
    "Away": lambda d: d.location_type.eq("Away"),
    "Neutral": lambda d: d.location_type.eq("Neutral"),
    "SENA": _country(*SENA),
    "England": _country("England"),
    "Australia": _country("Australia"),
    "South Africa": _country("South Africa"),
    "New Zealand": _country("New Zealand"),
}


def add_geo(df, matches):
    """Attach venue_country from the matches table (batting/bowling already carry location_type)."""
    geo = matches[["match_id", "venue_country"]].drop_duplicates("match_id")
    return df.drop(columns=["venue_country"], errors="ignore").merge(geo, on="match_id", how="left")


def expand(df, names=None):
    """Long table: one copy of the rows per split, with a 'split' column."""
    names = names or list(SPLITS)
    return pd.concat([df[SPLITS[n](df)].assign(split=n) for n in names], ignore_index=True)


def _safe_div(a, b):
    return (a / b.where(b > 0)).astype(float)


def batting_table(b, by=("player", "format", "split")):
    """Batting by player x split (x format). b must already be expanded."""
    by = list(by)
    has_dots = "dot_balls" in b.columns and b["dot_balls"].notna().any()
    d = b.assign(_out=b.is_out.astype(int), _no=(~b.is_out.astype(bool)).astype(int),
                 _50=b.is_fifty.astype(int), _100=b.is_hundred.astype(int), _duck=b.is_duck.astype(int),
                 _bdry=b.fours * 4 + b.sixes * 6, _dbase=b.balls.where(b.dot_balls.notna(), 0) if "dot_balls" in b.columns else 0)
    agg = dict(Mat=("match_id", "nunique"), Inns=("match_id", "size"), NO=("_no", "sum"),
               Runs=("runs", "sum"), HS=("runs", "max"), Balls=("balls", "sum"), _outs=("_out", "sum"),
               **{"50s": ("_50", "sum"), "100s": ("_100", "sum"), "Ducks": ("_duck", "sum"),
                  "4s": ("fours", "sum"), "6s": ("sixes", "sum"), "_bdry": ("_bdry", "sum")})
    if has_dots:
        agg["Dots"] = ("dot_balls", "sum"); agg["_dbase"] = ("_dbase", "sum")   # rows without dot data (hand-collected scorecards) stay out of the base
    t = d.groupby(by, dropna=False).agg(**agg).reset_index()
    t["Avg"] = _safe_div(t.Runs, t._outs).round(2)
    t["SR"] = (100 * _safe_div(t.Runs, t.Balls)).round(1)
    t["Bdry %"] = (100 * _safe_div(t._bdry, t.Runs)).round(1)
    cols = by + ["Mat", "Inns", "NO", "Runs", "HS", "Avg", "Balls", "SR", "50s", "100s", "Ducks", "4s", "6s", "Bdry %"]
    if has_dots:
        t["Dot %"] = (100 * _safe_div(t.Dots, t._dbase)).round(1)
        cols += ["Dots", "Dot %"]
    return t[cols]


def bowling_table(w, by=("player", "format", "split")):
    """Bowling by player x split (x format). w must already be expanded."""
    by = list(by)
    d = w.assign(_5=w.is_five_wkts.astype(int), _dbase=w.balls.where(w.dot_balls.notna(), 0))
    t = d.groupby(by, dropna=False).agg(
        Mat=("match_id", "nunique"), Inns=("match_id", "size"), _balls=("balls", "sum"), Mdns=("maidens", "sum"),
        Runs=("runs_conceded", "sum"), Wkts=("wickets", "sum"), Dots=("dot_balls", "sum"), _dbase=("_dbase", "sum"),
        Wides=("wides", "sum"), NB=("noballs", "sum"), **{"5W": ("_5", "sum")}).reset_index()
    best = (w.sort_values(["wickets", "runs_conceded"], ascending=[False, True])
             .groupby(by, dropna=False).first().reset_index())
    best["BBI"] = best.wickets.astype(int).astype(str) + "/" + best.runs_conceded.astype(int).astype(str)
    t = t.merge(best[by + ["BBI"]], on=by, how="left")
    t["Overs"] = (t._balls // 6).astype(int).astype(str) + "." + (t._balls % 6).astype(int).astype(str)
    t["Avg"] = _safe_div(t.Runs, t.Wkts).round(2)
    t["Econ"] = (6 * _safe_div(t.Runs, t._balls)).round(2)
    t["SR"] = _safe_div(t._balls, t.Wkts).round(1)
    t["Dot %"] = (100 * _safe_div(t.Dots, t._dbase)).round(1)
    return t[by + ["Mat", "Inns", "Overs", "Mdns", "Runs", "Wkts", "Avg", "Econ", "SR", "BBI", "5W", "Dots", "Dot %",
                   "Wides", "NB", "_balls"]]
