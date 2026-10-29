from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Captains & Coaches", "Pakistan's record under each captain and head coach, by format")
if m.empty:
    st.warning("No matches for these filters."); st.stop()
for col in ("pak_captain", "pak_coach"):
    if col not in m or m[col].notna().sum() == 0:
        st.error(f"`{col}` is empty. Run `python build_captains.py` then `python build_coaches.py`, and copy the CSVs into `data/`."); st.stop()

ERAS = Path(__file__).resolve().parent.parent / "eras"


def record(df, col):
    """P, completed, W, L, win % (completed matches only), average run difference."""
    g = df.dropna(subset=[col]).groupby(col)
    r = g.agg(P=("match_id", "count"), Completed=("is_completed", "sum"), W=("is_win", "sum"), L=("is_loss", "sum"),
              RunDiff=("run_diff", "mean"), First=("date", "min"), Last=("date", "max")).reset_index()
    r["Win %"] = (100 * r.W / r.Completed.where(r.Completed > 0)).round(1)
    return r.sort_values("P", ascending=False)


def panel(col, label, eras_file):
    conf = m[f"{col}_confidence"] if f"{col}_confidence" in m else None
    c1, c2 = st.columns([1, 3])
    with c1:
        floor = st.slider(f"Minimum matches ({label.lower()})", 1, 30, 10, key=f"min_{col}",
                          help="Hides small samples so a 3-match spell does not top the table.")
    r = record(m, col)
    shown = r[r.P >= floor]
    if shown.empty:
        st.info("No one meets the minimum for these filters."); return
    best = shown.sort_values("Win %", ascending=False).iloc[0]
    T.kpis([(f"{label}s in view", len(r), f"{len(shown)} with {floor}+ matches", "green"),
            ("Best win %", f"{best['Win %']:.1f}%", f"{best[col]} ({int(best.P)} matches)", "gold"),
            ("Most matches", r.iloc[0][col], f"{int(r.iloc[0].P)} matches", "blue")])
    f = px.bar(shown.sort_values("Win %"), x="Win %", y=col, orientation="h", text="Win %", hover_data=["P", "W", "L"],
               color="Win %", color_continuous_scale=T.DIV, range_color=[0, 100])
    f.update_traces(texttemplate="%{text:.0f}%", textposition="outside"); f.update_layout(coloraxis_showscale=False)
    f.update_xaxes(ticksuffix="%")
    T.plot(f, f"Win % by {label.lower()} (completed matches)", "Win %", label, h=max(320, 34 * len(shown) + 120))

    T.section(f"Record by {label.lower()} and format")
    t = m.dropna(subset=[col]).groupby([col, "format"]).agg(P=("match_id", "count"), W=("is_win", "sum"), C=("is_completed", "sum")).reset_index()
    t["Win %"] = (100 * t.W / t.C.where(t.C > 0)).round(0)
    hm = t[t[col].isin(shown[col])].pivot(index=col, columns="format", values="Win %")
    T.plot(px.imshow(hm, text_auto=".0f", color_continuous_scale=T.DIV, range_color=[0, 100], aspect="auto"),
           "Win % by format (blank = no completed matches)", "Format", label, cbar="Win %", h=max(300, 34 * len(hm) + 120))

    T.section(f"{label} timeline")
    e = pd.read_csv(ERAS / eras_file, parse_dates=["from_date", "to_date"])
    e["to_date"] = e.to_date + pd.Timedelta(days=1)
    e = e[e.format.isin(m.format.unique())]
    f = px.timeline(e, x_start="from_date", x_end="to_date", y="format", color="person", color_discrete_sequence=T.COLORWAY, hover_name="person")
    f.update_yaxes(autorange="reversed")
    f.update_layout(legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01, title_text=label), margin=dict(r=170))
    T.plot(f, f"{label}s over time (first to last match led)", "Date", "Format", legend=label, h=300)

    T.section("Full table")
    st.dataframe(r.assign(First=r.First.dt.date, Last=r.Last.dt.date, RunDiff=r.RunDiff.round(1))
                  .rename(columns={col: label, "RunDiff": "Avg run diff"}), hide_index=True, width="stretch")
    if conf is not None:
        n = int((conf.isin(["solved", "year-only", "interim-fallback", "overlap-resolved"])).sum())
        T.note(f"{n} of {len(m)} matches have an inferred {label.lower()} (flagged in `{col}_confidence`). Tenure dates come from year-level sources, so single matches at a changeover can be off.")


tab1, tab2 = st.tabs(["Captains", "Head coaches"])
with tab1:
    panel("pak_captain", "Captain", "captains.csv")
with tab2:
    panel("pak_coach", "Coach", "coaches.csv")
T.note("Win % uses completed matches only. Draws count as completed, so Test win % is not inflated by abandoned games.")