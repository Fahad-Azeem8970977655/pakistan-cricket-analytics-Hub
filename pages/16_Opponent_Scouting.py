import html as _h

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import insights as I
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Opponent Scouting Report", "Who is dangerous, whom they target, where and how they beat Pakistan. Use Ctrl+P or the download button to share.")
if m.empty:
    st.warning("No matches for these filters."); st.stop()

opp = st.selectbox("Opponent to scout", m.opponent.value_counts().index.tolist(), help="Sidebar filters (format, years, venue) apply to the whole report.")
x = m[m.opponent == opp].sort_values("date")
ids = set(x.match_id)
ob, ow, _ = D.load_opp()
ob, ow = D.by_ids(ob, ids), D.by_ids(ow, ids)
xb, xw = b[b.match_id.isin(ids)], w[w.match_id.isin(ids)]
lo = m[m.format != "Test"]; lo_x = lo[lo.opponent == opp]; lo_o = lo[lo.opponent != opp]

# ---------------- opposition player tables
def bat_tbl(df):
    if df.empty: return pd.DataFrame(columns=["player", "Inns", "Runs", "Avg", "SR", "100s", "50s"])
    t = df.groupby("player").agg(Inns=("runs", "size"), Runs=("runs", "sum"), Outs=("is_out", "sum"), Balls=("balls", "sum"),
                                 h=("runs", lambda s: int((s >= 100).sum())), f=("runs", lambda s: int(((s >= 50) & (s < 100)).sum()))).reset_index()
    t["Avg"] = (t.Runs / t.Outs.where(t.Outs > 0)).round(1); t["SR"] = (100 * t.Runs / t.Balls.where(t.Balls > 0)).round(1)
    return t.rename(columns={"h": "100s", "f": "50s"}).drop(columns=["Outs", "Balls"]).sort_values("Runs", ascending=False)


def bowl_tbl(df):
    if df.empty: return pd.DataFrame(columns=["player", "Spells", "Wkts", "Avg", "Econ"])
    t = df.groupby("player").agg(Spells=("wickets", "size"), Wkts=("wickets", "sum"), Runs=("runs_conceded", "sum"), Balls=("balls", "sum")).reset_index()
    t["Avg"] = (t.Runs / t.Wkts.where(t.Wkts > 0)).round(1); t["Econ"] = (6 * t.Runs / t.Balls.where(t.Balls > 0)).round(2)
    return t.drop(columns=["Runs", "Balls"]).sort_values("Wkts", ascending=False)


ob_t, ow_t = bat_tbl(ob), bowl_tbl(ow)
pb_t, pw_t = bat_tbl(xb), bowl_tbl(xw)

# ---------------- headline
o = D.overall(x)
T.kpis([
    ("Matches", int(o.P), f"{int(o.Completed)} completed", "green"),
    ("Pakistan win %", D.fmt_pct(o["Win %"]), f"{opp} win {D.fmt_pct(100 - o['Win %']) if o['Win %'] == o['Win %'] else 'n/a'}", "green" if (o["Win %"] or 0) >= 50 else "red", "up" if (o["Win %"] or 0) >= 50 else "down"),
    ("Last 5 meetings", f"{sum(r == 'Won' for r in D.last_results(x, 5))} wins", f"{sum(r == 'Lost' for r in D.last_results(x, 5))} defeats", "gold"),
    (f"{opp} avg score", f"{lo_x.opp_runs.mean():.0f}" if len(lo_x) else "n/a", f"Pakistan {lo_x.pak_runs.mean():.0f}" if len(lo_x) else "ODI & T20I", "blue"),
    (f"{opp} run rate", f"{lo_x.opp_run_rate.mean():.2f}" if len(lo_x) else "n/a", f"vs other teams {lo_o.opp_run_rate.mean():.2f}" if len(lo_o) else "", "blue"),
    ("Pakistan run-rate", f"{lo_x.pak_run_rate.mean():.2f}" if len(lo_x) else "n/a", f"vs other teams {lo_o.pak_run_rate.mean():.2f}" if len(lo_o) else "", "green"),
])
st.markdown("**Recent meetings (oldest to newest):**"); T.form_strip(D.last_results(x, 10))

# ---------------- scouting notes
notes = []
cw, cn = D.split_record(lo_x, "pak_batting_order", "Batting second"); dw, dn = D.split_record(lo_x, "pak_batting_order", "Batting first")
if cw is not None and dw is not None and cn >= 4 and dn >= 4:
    notes.append(("info", f"Against {opp}, Pakistan win **{cw:.0f}%** chasing ({cn} matches) and **{dw:.0f}%** setting a target ({dn} matches)."))
lost = x[x.result == "Lost"]
if len(lost) >= 3:
    vc = lost.venue_country.value_counts()
    notes.append(("down", f"{opp} have beaten Pakistan most often in matches played in **{vc.index[0]}** ({int(vc.iloc[0])} of {len(lost)} defeats)."))
if len(ob_t):
    r = ob_t.iloc[0]
    notes.append(("down", f"Batting threat: **{r.player}** has scored {int(r.Runs)} runs against Pakistan (avg {r.Avg}, SR {r.SR})."))
if len(ow_t):
    r = ow_t.iloc[0]
    notes.append(("down", f"Bowling threat: **{r.player}** has taken {int(r.Wkts)} Pakistan wickets (avg {r.Avg}, economy {r.Econ})."))
d_out = xb[xb.is_out & xb.dismissed_by.notna()].groupby(["player", "dismissed_by"]).size().sort_values(ascending=False)
if len(d_out) and d_out.iloc[0] >= 3:
    (pn, bn), c = d_out.index[0], int(d_out.iloc[0])
    notes.append(("warn", f"Key match-up: **{bn}** has dismissed **{pn}** {c} times."))
if len(lo_x) >= 4 and len(lo_o) >= 10:
    dd = lo_x.opp_death_runs.mean() - lo_o.opp_death_runs.mean(); pp = lo_x.opp_powerplay_runs.mean() - lo_o.opp_powerplay_runs.mean()
    ph, v = ("death overs", dd) if abs(dd) >= abs(pp) else ("powerplay", pp)
    if abs(v) >= 2: notes.append(("warn", f"{opp} score {abs(v):.1f} runs per innings {'more' if v > 0 else 'fewer'} in the **{ph}** against Pakistan than other sides do."))
ot = x[x.pak_won_toss == False]; ow_pct, on = D.split_record(ot.assign(a=True), "a", True) if len(ot) else (None, 0)
if ow_pct is not None and on >= 8: notes.append(("info", f"When {opp} win the toss, Pakistan win **{ow_pct:.0f}%** of those matches ({on})."))
if len(pb_t[pb_t.Inns >= 4]):
    best = pb_t[pb_t.Inns >= 4].sort_values("Avg", ascending=False).iloc[0]
    notes.append(("up", f"Best Pakistan batter against them: **{best.player}** (avg {best.Avg}, SR {best.SR}, {int(best.Runs)} runs)."))
T.section("Scouting notes", "generated from the data below")
I.render(notes)

# ---------------- danger men
T.section("Danger men", f"{opp} players in matches against Pakistan")
c1, c2 = st.columns(2)
with c1:
    d = ob_t.head(8).sort_values("Runs")
    f = px.bar(d, y="player", x="Runs", orientation="h", text="Runs", color="Avg", color_continuous_scale=T.SEQ_RED, hover_data=["Inns", "SR", "100s"])
    f.update_traces(textposition="outside"); f.update_xaxes(range=[0, (d.Runs.max() if len(d) else 1) * 1.2])
    T.plot(f, f"{opp} batters: most runs vs Pakistan (colour = average)", "Runs", "Batter", cbar="Average", h=400)
with c2:
    d = ow_t.head(8).sort_values("Wkts")
    f = px.bar(d, y="player", x="Wkts", orientation="h", text="Wkts", color="Econ", color_continuous_scale=T.SEQ_RED, hover_data=["Spells", "Avg"])
    f.update_traces(textposition="outside"); f.update_xaxes(range=[0, (d.Wkts.max() if len(d) else 1) * 1.2])
    T.plot(f, f"{opp} bowlers: most wickets vs Pakistan (colour = economy)", "Wickets", "Bowler", cbar="Economy", h=400)
t1, t2 = st.columns(2)
t1.dataframe(ob_t.head(10), hide_index=True, width="stretch"); t2.dataframe(ow_t.head(10), hide_index=True, width="stretch")

# ---------------- whom they target
T.section("Whom they target", "Pakistan batters most often dismissed in these matches")
dd_ = xb[xb.is_out & xb.dismissed_by.notna()]
if dd_.empty:
    st.info("No attributed dismissals for this selection.")
else:
    c3, c4 = st.columns(2)
    with c3:
        v = dd_.groupby("player").size().sort_values(ascending=False).head(10).reset_index(name="Dismissals").sort_values("Dismissals")
        f = px.bar(v, y="player", x="Dismissals", orientation="h", text="Dismissals", color_discrete_sequence=["#D64545"]); f.update_traces(textposition="outside")
        f.update_xaxes(range=[0, v.Dismissals.max() * 1.2])
        T.plot(f, "Pakistan batters dismissed most often", "Times dismissed (excl. run-outs)", "Pakistan batter", h=400)
    with c4:
        tb, tbw = dd_.player.value_counts().head(8).index, dd_.dismissed_by.value_counts().head(8).index
        mx = dd_[dd_.player.isin(tb) & dd_.dismissed_by.isin(tbw)].groupby(["player", "dismissed_by"]).size().unstack(fill_value=0)
        if not mx.empty: T.plot(px.imshow(mx, text_auto=True, color_continuous_scale=T.SEQ_RED, aspect="auto"), "Match-up matrix: who gets whom", f"{opp} bowler", "Pakistan batter", cbar="Dismissals", h=400)

# ---------------- Pakistan answers
T.section("Pakistan's best answers", "Pakistan players against this opponent")
c5, c6 = st.columns(2)
with c5:
    st.markdown("**Batters** (min 4 innings)"); st.dataframe(pb_t[pb_t.Inns >= 4].sort_values("Avg", ascending=False).head(10), hide_index=True, width="stretch")
with c6:
    st.markdown("**Bowlers** (min 3 spells)"); st.dataframe(pw_t[pw_t.Spells >= 3].head(10), hide_index=True, width="stretch")

# ---------------- phases
T.section("Phase profile", "ODI & T20I: this opponent vs all other opponents")
if len(lo_x) >= 3 and len(lo_o) >= 5:
    def ph(df, pre):
        return [df[f"{pre}_powerplay_runs"].mean(), df[f"{pre}_middle_runs"].mean(), df[f"{pre}_death_runs"].mean()]
    P = ["Powerplay", "Middle overs", "Death overs"]
    d1 = pd.DataFrame({"Phase": P * 2, "Group": [f"{opp} vs Pakistan"] * 3 + ["Other opponents vs Pakistan"] * 3, "Runs": ph(lo_x, "opp") + ph(lo_o, "opp")})
    d2 = pd.DataFrame({"Phase": P * 2, "Group": [f"Pakistan vs {opp}"] * 3 + ["Pakistan vs others"] * 3, "Runs": ph(lo_x, "pak") + ph(lo_o, "pak")})
    c7, c8 = st.columns(2)
    for col, d, ttl in ((c7, d1, f"How {opp} score by phase"), (c8, d2, f"How Pakistan score against {opp} by phase")):
        f = px.bar(d, x="Phase", y="Runs", color="Group", barmode="group", text="Runs", color_discrete_sequence=["#D64545" if col is c7 else T.GREEN, "#9AA5AD"])
        f.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        with col: T.plot(f, ttl, "Phase of innings", "Average runs per innings", legend="Group", h=380)
else:
    st.info("Need at least 3 ODI/T20I meetings with this opponent for phase analysis.")

# ---------------- where and how
T.section("Where and how they beat Pakistan")
c9, c10 = st.columns(2)
vc = x.groupby(["venue_country", "result"]).size().reset_index(name="n")
with c9:
    f = px.bar(vc, y="venue_country", x="n", color="result", orientation="h", color_discrete_map=D.RES_COLORS)
    T.plot(f, f"Results vs {opp} by country", "Matches", "Venue country", legend="Result", h=380)
if len(lo_x):
    bo = lo_x.groupby(["pak_batting_order", "result"]).size().reset_index(name="n")
    with c10:
        T.plot(px.bar(bo, x="pak_batting_order", y="n", color="result", color_discrete_map=D.RES_COLORS, text="n"), "Results by innings order (ODI & T20I)", "Pakistan batting", "Matches", legend="Result", h=380)

# ---------------- download
def md(t): 
    parts = _h.escape(t).split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))

report = f"""<html><head><meta charset="utf-8"><title>Scouting report: {opp}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:30px auto;color:#1B2A24}}h1{{color:#073B21;border-bottom:4px solid #C9A227;padding-bottom:6px}}
h2{{color:#0B6B3A;margin-top:26px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #D9E2DD;padding:5px 8px;text-align:left}}th{{background:#073B21;color:#fff}}</style></head><body>
<h1>Pakistan v {_h.escape(opp)}: scouting report</h1>
<p>{int(o.P)} matches, Pakistan win {D.fmt_pct(o['Win %'])}. Data: Cricsheet, filters as set in the dashboard.</p>
<h2>Scouting notes</h2><ul>{''.join(f'<li>{md(t)}</li>' for _, t in notes)}</ul>
<h2>Danger batters</h2>{ob_t.head(8).to_html(index=False)}<h2>Danger bowlers</h2>{ow_t.head(8).to_html(index=False)}
<h2>Pakistan batters vs {_h.escape(opp)}</h2>{pb_t[pb_t.Inns >= 4].sort_values('Avg', ascending=False).head(8).to_html(index=False)}
<h2>Pakistan bowlers vs {_h.escape(opp)}</h2>{pw_t[pw_t.Spells >= 3].head(8).to_html(index=False)}</body></html>"""
st.download_button("Download this scouting report (HTML)", report.encode("utf-8"), f"scouting_{opp.replace(' ', '_')}.html", "text/html")
