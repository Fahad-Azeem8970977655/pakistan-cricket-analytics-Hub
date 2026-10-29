"""Data loading, cleaning, shared filters and helpers for the Pakistan dashboard."""
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parent.parent / "data"
from utils import theme as T

RES_COLORS = T.RES_COLORS
FMT_COLORS = T.FMT_COLORS
FORMATS = ["Test", "ODI", "T20I"]


def setup(title=None):
    """Called by every page: injects the shared CSS (page config is set once in app.py)."""
    if not st.session_state.get("_routed"):  # page opened directly (bookmark / cold start): go through the router so menu + filters exist
        st.switch_page("app.py")
    T.inject()


def _ids(df):
    """match_id must be the same type in every table: manual matches have ids like 'manual_1', which turns the CSV column into text."""
    if isinstance(df, pd.DataFrame) and "match_id" in df:
        df["match_id"] = df["match_id"].astype(str)
    return df


def _clean(m):
    m["edition"] = m["edition"].replace("", pd.NA)
    m["edition_clean"] = m["edition"]
    m["stage"] = m["stage_inferred"].replace("", pd.NA)
    m["pak_toss"] = m["pak_won_toss"].map({True: "Won toss", False: "Lost toss"})
    for c in ("pak_captain", "pak_coach"):
        if c in m: m[c] = m[c].replace("", pd.NA)
    return m


@st.cache_data(show_spinner=False)
def load():
    m = pd.read_csv(DATA / "pak_matches.csv", parse_dates=["date"])
    b = pd.read_csv(DATA / "pak_batting.csv", parse_dates=["date"])
    w = pd.read_csv(DATA / "pak_bowling.csv", parse_dates=["date"])
    return _clean(_ids(m)), _ids(b), _ids(w)


@st.cache_data(show_spinner=False)
def load_extra():
    """Fielding, partnerships, over-by-over, appearances, players, editions."""
    r = lambda n, **k: _ids(pd.read_csv(DATA / f"{n}.csv", **k))
    return dict(field=r("pak_fielding", parse_dates=["date"]), parts=r("pak_partnerships", parse_dates=["date"]),
                overs=r("pak_overs", parse_dates=["date"]), apps=r("pak_appearances", parse_dates=["date"]),
                players=r("pak_players", parse_dates=["first_match", "last_match"]), editions=r("pak_editions"))


@st.cache_data(show_spinner=False)
def load_opp():
    """Opposition batting / bowling / players (built by scripts/add_opposition_data.py). Empty frames if not built yet."""
    r = lambda n, **k: _ids(pd.read_csv(DATA / f"{n}.csv", **k)) if (DATA / f"{n}.csv").exists() else pd.DataFrame()
    return (r("opp_batting", parse_dates=["date"]), r("opp_bowling", parse_dates=["date"]), r("opp_players"))


@st.cache_data(show_spinner=False)
def load_opp_fielding():
    f = DATA / "opp_fielding.csv"
    return _ids(pd.read_csv(f, parse_dates=["date"])) if f.exists() else pd.DataFrame()


def by_ids(df, ids):
    return df[df.match_id.isin(ids)]


EXPECTED_OPPONENTS = ["Afghanistan", "Australia", "Bangladesh", "England", "India", "Ireland", "New Zealand",
                      "South Africa", "Sri Lanka", "West Indies", "Zimbabwe"]


def coverage_missing(m):
    return [t for t in EXPECTED_OPPONENTS if t not in set(m.opponent)]


def wilson(w, n, z=1.96):
    import math
    if not n: return (None, None)
    p = w / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def grouped_record(df, by):
    """Played / Won / Lost / Tied / Other / Win % grouped by column(s)."""
    d = df.assign(W=(df.result == "Won").astype(int), L=(df.result == "Lost").astype(int),
                  T=(df.result == "Tied").astype(int))
    if not by:
        d["_all"] = "All"; by = "_all"
    g = d.groupby(by, dropna=False).agg(P=("result", "size"), W=("W", "sum"),
                                         L=("L", "sum"), T=("T", "sum")).reset_index()
    n = g.W + g.L + g["T"]
    g["Other"] = g.P - n
    g["Win %"] = (100 * g.W / n.where(n > 0)).round(1)
    ci = [wilson(w, k) for w, k in zip(g.W, n)]
    g["CI low"], g["CI high"] = [c[0] for c in ci], [c[1] for c in ci]
    g["Completed"] = n
    return g


def overall(df):
    g = grouped_record(df, [])
    return g.iloc[0]


def editions(m):
    """One row per tournament edition (stage reached comes from the v3 script) with counts from filtered matches."""
    t = load_extra()["editions"].set_index("edition")
    g = m[m.edition.notna()].groupby("edition").agg(group=("tournament_group", "first"), year=("year", "first"),
        format=("format", "first"), start=("date", "min"), P=("result", "size"),
        W=("result", lambda x: int((x == "Won").sum())), L=("result", lambda x: int((x == "Lost").sum()))).reset_index()
    if g.empty: return g
    g = g.join(t[["stage_reached", "stage_source", "stage_check_needed", "provisional"]], on="edition")
    return g.sort_values("start")


FILTER_KEYS = ["f_fmt", "f_yr", "f_loc", "f_tt", "f_op", "f_cap"]


def _reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def render_filters():
    """Draw the sidebar filters once (called from app.py). Values live in st.session_state."""
    m, _, _ = load()
    sb = st.sidebar
    sb.markdown('<div class="side-title">FILTERS</div>', unsafe_allow_html=True)
    sb.pills("Format", FORMATS, selection_mode="multi", default=FORMATS, key="f_fmt")
    y0, y1 = int(m.year.min()), int(m.year.max())
    sb.slider("Years", y0, y1, (y0, y1), key="f_yr")
    locs = sorted(m.location_type.unique())
    sb.pills("Venue type", locs, selection_mode="multi", default=locs, key="f_loc")
    with sb.expander("More filters  (tournament, opponent, captain)"):
        tts = sorted(m.tournament_type.unique())
        st.multiselect("Tournament type (empty = all)", tts, key="f_tt")
        st.multiselect("Opponent (empty = all)", sorted(m.opponent.unique()), key="f_op")
        if m.pak_captain.notna().any():
            st.multiselect("Captain (empty = all)", sorted(m.pak_captain.dropna().unique()), key="f_cap")
    mf, _, _ = filters()
    sb.markdown(f'<div class="side-count"><b>{len(mf)}</b> of {len(m)} matches selected<br>data to {m.date.max():%d %b %Y}</div>', unsafe_allow_html=True)
    sb.button("Reset filters", on_click=_reset_filters, width="stretch", key="f_reset")


def filters():
    """Filtered (matches, batting, bowling) according to the sidebar selections. An empty selection means 'all'."""
    m, b, w = load()
    ss = st.session_state
    fm = ss.get("f_fmt") or FORMATS
    yr = ss.get("f_yr", (int(m.year.min()), int(m.year.max())))
    lc = ss.get("f_loc") or sorted(m.location_type.unique())
    tt = ss.get("f_tt") or sorted(m.tournament_type.unique())
    op, cp = ss.get("f_op", []), ss.get("f_cap", [])
    k = m.format.isin(fm) & m.year.between(*yr) & m.location_type.isin(lc) & m.tournament_type.isin(tt)
    if op: k &= m.opponent.isin(op)
    if cp: k &= m.pak_captain.isin(cp)
    mf = m[k]
    ids = set(mf.match_id)
    return mf, b[b.match_id.isin(ids)], w[w.match_id.isin(ids)]


# ---------- KPI helpers ----------
def pct(a, n, nd=1):
    return round(100 * a / n, nd) if n else None


def fmt_pct(x):
    return "n/a" if x is None or x != x else f"{x:.1f}%"


def split_record(m, col, val):
    """Win % for the subset m[col] == val (draws / no-results excluded)."""
    g = m[m[col] == val]
    n = int(g.result.isin(["Won", "Lost", "Tied"]).sum())
    return pct(int((g.result == "Won").sum()), n), n


def last_results(m, n=10):
    return m.sort_values("date").tail(n).result.tolist()