import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Captain & Coach Impact", "Which captain-coach pairs won most, and how players performed with and without the armband")
if m.empty or "pak_captain" not in m or m.pak_captain.notna().sum() == 0:
    st.warning("No captain data for these filters. Run build_captains.py / build_coaches.py."); st.stop()

x = m.dropna(subset=["pak_captain", "pak_coach"]).copy()

# ---------- 1. Captain x coach pairs ---------------------------------------------------------------------------------
T.section("Captain + coach combinations")
floor = st.slider("Minimum matches together", 1, 30, 8, help="Hides short pairings.")
p = x.groupby(["pak_captain", "pak_coach"]).agg(P=("match_id", "count"), C=("is_completed", "sum"), W=("is_win", "sum"), L=("is_loss", "sum"),
                                                RunDiff=("run_diff", "mean")).reset_index()
p["Win %"] = (100 * p.W / p.C.where(p.C > 0)).round(1)
ps = p[p.P >= floor].sort_values("Win %", ascending=False)
if ps.empty:
    st.info("No pair reaches that minimum with the current filters. Lower the slider.")
else:
    top = ps.iloc[0]
    T.kpis([("Pairs shown", len(ps), f"{floor}+ matches together", "green"),
            ("Best pair", f"{top['Win %']:.0f}%", f"{top.pak_captain} + {top.pak_coach} ({int(top.P)})", "gold"),
            ("Most used pair", f"{int(p.P.max())} matches", " + ".join(p.sort_values('P').iloc[-1][["pak_captain", "pak_coach"]]), "blue")])
    ps["Pair"] = ps.pak_captain + " + " + ps.pak_coach
    f = px.bar(ps.sort_values("Win %"), x="Win %", y="Pair", orientation="h", text="Win %", hover_data=["P", "W", "L"], color="Win %",
               color_continuous_scale=T.DIV, range_color=[0, 100])
    f.update_traces(texttemplate="%{text:.0f}%", textposition="outside"); f.update_layout(coloraxis_showscale=False)
    f.update_xaxes(ticksuffix="%")
    T.plot(f, "Win % by captain-coach pair", "Win %", "Pair", h=max(320, 32 * len(ps) + 120))
    hm = p[p.P >= floor].pivot(index="pak_captain", columns="pak_coach", values="Win %")
    T.plot(px.imshow(hm, text_auto=".0f", color_continuous_scale=T.DIV, range_color=[0, 100], aspect="auto"), "Win % grid (blank = never together or too few)",
           "Coach", "Captain", cbar="Win %", h=max(320, 40 * len(hm) + 120))

# ---------- 2. Change impact -------------------------------------------------------------------------------------------
T.section("Before and after a change")
kind = st.radio("Look at", ["Captain", "Coach"], horizontal=True)
col = "pak_captain" if kind == "Captain" else "pak_coach"
fmt = st.selectbox("Format", ["All"] + sorted(m.format.unique()))
y = (m if fmt == "All" else m[m.format == fmt]).dropna(subset=[col]).sort_values("date").reset_index(drop=True)
def _short(n):
    """Short chart label: initial + surname ("S. Ahmed"), so Azhar Ali and Salman Ali Agha are not both just "Ali"."""
    p = str(n).replace("-ul-", " ").split()
    return n if len(p) < 2 else (p[0] if "-ul-" in str(n) else f"{p[0][0]}. {p[-1]}")


if len(y) >= 10:
    y["roll"] = y.is_win.where(y.is_completed).rolling(10, min_periods=5).mean().mul(100)
    f = px.line(y, x="date", y="roll", hover_data=[col, "opponent"], color_discrete_sequence=[T.GREEN])
    if fmt == "All":
        st.caption(f"Pick a single format above to see {kind.lower()} changes marked on the chart. In 'All' they alternate between formats and would clutter it.")
    else:
        # mark only real hand-overs: the new person must lead at least 3 matches in a row (hides one-off stand-ins and inference noise)
        run = (y[col] != y[col].shift()).cumsum()
        runs = y.groupby(run).agg(start=("date", "first"), n=("date", "size"), who=(col, "first")).reset_index(drop=True)
        marks = runs[runs.n >= 3].iloc[1:] if len(runs) else runs
        for i, (_, r) in enumerate(marks.iterrows()):
            f.add_vline(x=r.start, line_dash="dot", line_color="#B5BCC2", line_width=1)
            f.add_annotation(x=r.start, y=104 if i % 2 == 0 else 94, text=_short(r.who), showarrow=False, xanchor="left", yanchor="top",
                             font=dict(size=10, color="#4A5560"), bgcolor="rgba(255,255,255,0.75)")
    T.plot(f, f"Rolling win % (last 10 completed matches) with {kind.lower()} changes marked", "Date", "Win %", pct=True, ylim=[0, 105], hline=50, h=380)
else:
    st.info("Not enough matches for a rolling chart.")

# ---------- 3. Player with and without the armband -----------------------------------------------------------------------
T.section("Batting and bowling as captain vs not")
caps = x.pak_captain.value_counts(); caps = caps[caps >= 5].index.tolist()
if caps:
    who = st.selectbox("Captain", caps)
    mc = m.set_index("match_id").pak_captain
    bb = b[b.player == who].copy(); bb["role"] = (bb.match_id.map(mc) == who).map({True: "As captain", False: "Not captain"})
    bw = w[w.player == who].copy(); bw["role"] = (bw.match_id.map(mc) == who).map({True: "As captain", False: "Not captain"})
    r = bb.groupby("role").agg(Inns=("match_id", "count"), Runs=("runs", "sum"), Balls=("balls", "sum"), Outs=("is_out", "sum"),
                               Fifties=("is_fifty", "sum"), Hundreds=("is_hundred", "sum")).reset_index()
    r["Avg"] = (r.Runs / r.Outs.where(r.Outs > 0)).round(1); r["SR"] = (100 * r.Runs / r.Balls.where(r.Balls > 0)).round(1)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{who}: batting**"); st.dataframe(r, hide_index=True, width="stretch")
        if len(r) == 2:
            T.plot(px.bar(r, x="role", y="Avg", text="Avg", color="role", color_discrete_sequence=[T.GREEN, "#C3CBD0"]).update_layout(showlegend=False),
                   "Batting average", "", "Average", h=300)
    with c2:
        st.markdown(f"**{who}: bowling**")
        if bw.empty: st.caption("No bowling records for this player in the current filters.")
        else:
            rb = bw.groupby("role").agg(Inns=("match_id", "count"), Overs=("overs", "sum"), Runs=("runs_conceded", "sum"), Wkts=("wickets", "sum")).reset_index()
            rb["Econ"] = (rb.Runs / rb.Overs.where(rb.Overs > 0)).round(2); rb["Avg"] = (rb.Runs / rb.Wkts.where(rb.Wkts > 0)).round(1)
            st.dataframe(rb, hide_index=True, width="stretch")
T.note("Captain and coach for each match come from eras/*.csv. Some matches are inferred; see the confidence columns in pak_matches.csv.")