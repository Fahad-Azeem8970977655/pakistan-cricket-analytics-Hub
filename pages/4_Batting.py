import plotly.express as px
import streamlit as st

from utils import analytics as A
from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Batting", "Run-scorers, strike rates, positions and dismissals")
if b.empty:
    st.warning("No batting data for these filters."); st.stop()

p = b.groupby("player").agg(Inns=("runs", "size"), Runs=("runs", "sum"), Balls=("balls", "sum"), Outs=("is_out", "sum"),
                            Fours=("fours", "sum"), Sixes=("sixes", "sum"), HS=("runs", "max"),
                            Fifties=("is_fifty", "sum"), Hundreds=("is_hundred", "sum"), Ducks=("is_duck", "sum")).reset_index()
p["Avg"] = (p.Runs / p.Outs.where(p.Outs > 0)).round(1)
p["SR"] = (100 * p.Runs / p.Balls.where(p.Balls > 0)).round(1)
tot_out = int(b.is_out.sum())
T.kpis([("Total runs", f"{int(b.runs.sum()):,}", f"{len(b):,} innings", "green"),
        ("Batting average", f"{b.runs.sum() / max(tot_out, 1):.1f}", "Runs per dismissal", "green"),
        ("Strike rate", f"{100 * b.runs.sum() / max(b.balls.sum(), 1):.1f}", "Runs per 100 balls", "blue"),
        ("Centuries", int(b.is_hundred.sum()), f"{int(b.is_fifty.sum())} fifties", "gold"),
        ("Sixes / Fours", f"{int(b.sixes.sum())} / {int(b.fours.sum())}", f"{100 * (b.fours.sum() * 4 + b.sixes.sum() * 6) / max(b.runs.sum(), 1):.0f}% of runs in boundaries", "blue"),
        ("Ducks", int(b.is_duck.sum()), f"{100 * b.is_duck.mean():.1f}% of innings", "red")])

mn = st.slider("Minimum runs for leaderboards and charts", 0, 3000, 500, 50)
q = p[p.Runs >= mn].sort_values("Runs", ascending=False)
c1, c2 = st.columns(2)
with c1:
    T.section("Leaderboard")
    st.dataframe(q.drop(columns=["Balls", "Outs"]), hide_index=True, width="stretch", height=430)
with c2:
    T.section("Top run-scorers")
    f = px.bar(q.head(15).sort_values("Runs"), y="player", x="Runs", color="Hundreds", orientation="h", color_continuous_scale=T.SEQ_GREEN, text="Runs")
    f.update_traces(textposition="outside")
    T.plot(f, None, "Runs", "Batter", h=430, cbar="Centuries")

T.section("Quality map")
T.plot(px.scatter(q, x="SR", y="Avg", size="Runs", color="Hundreds", hover_name="player", color_continuous_scale="Viridis", text="player").update_traces(textposition="top center", textfont_size=9),
       "Batting average vs strike rate (bubble = runs, colour = centuries)", "Strike rate (runs per 100 balls)", "Batting average", h=480, cbar="Centuries")

c3, c4 = st.columns(2)
bp = b[b.batting_position.between(1, 11)]
with c3:
    T.plot(px.box(bp, x="batting_position", y="runs", color="format", color_discrete_map=D.FMT_COLORS), "Runs by batting position", "Batting position", "Runs per innings", legend="Format")
dm = b[b.is_out].dismissal.value_counts().reset_index()
with c4:
    f = px.bar(dm.sort_values("count"), x="count", y="dismissal", orientation="h", text="count", color_discrete_sequence=[T.GREEN])
    f.update_traces(textposition="outside")
    T.plot(f, "How Pakistan batters get out", "Dismissals", "Mode of dismissal")

T.section("Runs above par", "format-, venue- and position-adjusted")
T.note("Par = average runs scored by all batters (Pakistan and opposition) in the same format, venue country and batting-position group, "
       "shrunk towards the format-wide figure for small venues. Runs above par (RAP) = actual runs minus par, so a 40 on a low-scoring pitch beats a 40 on a flat one.")
x = A.with_rap(b)
rp = A.rap_table(x)
mi = st.slider("Minimum innings for the RAP table", 10, 200, 40, 5)
rq = rp[rp.Inns >= mi].sort_values("RAP", ascending=False)
if len(rq):
    r1, r2 = st.columns(2)
    with r1:
        f = px.bar(rq.head(15).sort_values("RAP"), y="player", x="RAP", orientation="h", text="RAP", color="RAP/inn", color_continuous_scale=T.DIV, hover_data=["Inns", "Runs", "Expected"])
        f.update_traces(textposition="outside")
        T.plot(f, "Total runs above par (top 15, colour = per innings)", "Runs above par", "Batter", h=460, cbar="RAP per innings")
    with r2:
        q2 = rq.assign(act=(rq.Runs / rq.Inns).round(1), exp=(rq.Expected / rq.Inns).round(1))
        q2["lab"] = ["" if i >= 8 else n for i, n in enumerate(q2.player)]  # label only the top 8 to avoid overlap
        lim = [0, max(q2.act.max(), q2.exp.max()) * 1.1]
        f = px.scatter(q2, x="exp", y="act", size="Inns", color="RAP/inn", color_continuous_scale=T.DIV, hover_name="player", text="lab")
        f.update_traces(textposition="top center", textfont_size=9)
        f.add_shape(type="line", x0=0, y0=0, x1=lim[1], y1=lim[1], line=dict(dash="dot", color="#8A949C"))
        T.plot(f, "Actual vs expected runs per innings (above the line = beating par)", "Expected runs per innings (par)", "Actual runs per innings", h=460, cbar="RAP per innings")
    st.dataframe(rq[["player", "Inns", "Runs", "Expected", "RAP", "RAP/inn"]], hide_index=True, width="stretch", height=300)
else:
    st.info("No batter has that many innings under the current filters.")

T.section("Batting positions and roles")
fm_opts = ["All formats"] + sorted(b.format.unique())
fsel = st.radio("Format", fm_opts, horizontal=True, key="pos_fmt")
bb_ = b if fsel == "All formats" else b[b.format == fsel]
pt = A.position_table(b, ["format", "bucket"])
c5, c6 = st.columns(2)
f = px.bar(pt, x="bucket", y="Runs/inn", color="format", barmode="group", color_discrete_map=D.FMT_COLORS, text="Runs/inn", hover_data=["Inns", "Avg", "SR"], category_orders={"bucket": A.BUCKETS})
with c5: T.plot(f, "Runs per innings by batting role", "Batting position group", "Runs per innings", legend="Format")
f = px.bar(pt, x="bucket", y="Share of runs %", color="format", barmode="group", color_discrete_map=D.FMT_COLORS, text="Share of runs %", category_orders={"bucket": A.BUCKETS})
with c6: T.plot(f, "Share of Pakistan's batter runs by role", "Batting position group", "Share of runs (%)", legend="Format", pct=True)
c7, c8 = st.columns(2)
f = px.bar(pt, x="bucket", y="SR", color="format", barmode="group", color_discrete_map=D.FMT_COLORS, text="SR", category_orders={"bucket": A.BUCKETS})
with c7: T.plot(f, "Strike rate by role", "Batting position group", "Strike rate", legend="Format")
f = px.bar(pt, x="bucket", y="50+ rate %", color="format", barmode="group", color_discrete_map=D.FMT_COLORS, text="50+ rate %", category_orders={"bucket": A.BUCKETS})
with c8: T.plot(f, "Fifty-plus rate by role", "Batting position group", "Innings with 50+ (%)", legend="Format", pct=True)
top = bb_.groupby("player").size().sort_values(ascending=False).head(15).index
hm = bb_[bb_.player.isin(top) & bb_.batting_position.between(1, 11)].groupby(["player", "batting_position"]).size().unstack(fill_value=0)
if not hm.empty:
    hm = hm.reindex(top)
    T.plot(px.imshow(hm, text_auto=True, color_continuous_scale=T.SEQ_GREEN, aspect="auto"), f"Where do the regulars bat? ({fsel}, innings by position)", "Batting position", "Batter", cbar="Innings", h=480)
yy = bb_[bb_.batting_position.between(1, 7)].groupby(["year", "batting_position"]).player.agg(lambda s: s.value_counts().index[0]).unstack()
if not yy.empty:
    st.markdown("**Most-used batter at each position, by year**")
    yy.columns = [f"No. {int(c)}" for c in yy.columns]
    st.dataframe(yy, width="stretch")

T.section("Player profile")
who = st.selectbox("Player", p.sort_values("Runs", ascending=False).player)
pb = b[b.player == who]
r = p[p.player == who].iloc[0]
T.kpis([("Runs", int(r.Runs), f"{int(r.Inns)} innings", "green"), ("Average", r.Avg, "", "green"), ("Strike rate", r.SR, "", "blue"),
        ("Highest score", int(r.HS), "", "gold"), ("100s / 50s", f"{int(r.Hundreds)} / {int(r.Fifties)}", "", "gold"), ("Ducks", int(r.Ducks), "", "red")])
d1, d2 = st.columns(2)
yr = pb.groupby(["year", "format"]).agg(Runs=("runs", "sum")).reset_index()
with d1: T.plot(px.bar(yr, x="year", y="Runs", color="format", color_discrete_map=D.FMT_COLORS), f"{who}: runs per year", "Year", "Runs", legend="Format")
with d2: T.plot(px.scatter(pb, x="date", y="runs", color="format", size="balls", color_discrete_map=D.FMT_COLORS, hover_data=["opponent", "dismissal"]),
                f"{who}: every innings (bubble = balls faced)", "Date", "Runs", legend="Format")
xr = x[x.player == who].sort_values("date").assign(cum=lambda d: d.rap.cumsum().round(0), n=lambda d: range(1, len(d) + 1))
if len(xr):
    T.plot(px.area(xr, x="n", y="cum", hover_data=["date", "opponent", "runs"]).update_traces(line_color=T.GREEN, fillcolor="rgba(11,107,58,.15)"),
           f"{who}: cumulative runs above par over his career", "Innings number", "Cumulative runs above par")
T.plot(px.histogram(m, x="pak_runs", color="format", nbins=40, color_discrete_map=D.FMT_COLORS, barmode="overlay", opacity=.75),
       "Distribution of Pakistan team totals", "Team total (runs)", "Number of innings", legend="Format")
