import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Tournaments", "ICC events, Asia Cups and multi-team series: how far Pakistan went in each edition")
ed = D.editions(m)
if ed.empty:
    st.warning("No tournament matches for these filters (check Tournament type in the sidebar)."); st.stop()

STAGE_ORDER = ["Champions", "Runners-up", "Semi-final", "Quarter-final", "Super stage", "Play-off", "Group/League stage"]
colors = {"Champions": "#0B8A4B", "Runners-up": "#2A7AB9", "Semi-final": "#E5A100", "Quarter-final": "#E07B39",
          "Super stage": "#7B5EA7", "Play-off": "#8A949C", "Group/League stage": "#D64545", "Final (no result/tie)": "#2A7AB9"}
T.kpis([("Editions played", len(ed), "", "green"), ("Titles", int((ed.stage_reached == "Champions").sum()), "", "gold"),
        ("Finals reached", int(ed.stage_reached.isin(["Champions", "Runners-up"]).sum()), "Champions + runners-up", "blue"),
        ("Group-stage exits", int((ed.stage_reached == "Group/League stage").sum()), "", "red")], per_row=4)

T.section("Stage reached over time")
f = px.scatter(ed, x="start", y="group", color="stage_reached", size="P", color_discrete_map=colors,
               category_orders={"stage_reached": STAGE_ORDER}, hover_data=["edition", "W", "L"])
f.update_traces(marker=dict(sizemin=9, line=dict(width=1, color="white")))
T.plot(f, "Tournament timeline: stage reached (bubble = matches played)", "Edition start", "Tournament", h=450, legend="Stage reached")

c1, c2 = st.columns(2)
cnt = ed.groupby(["group", "stage_reached"]).size().reset_index(name="editions")
with c1:
    T.plot(px.bar(cnt, y="group", x="editions", color="stage_reached", orientation="h", color_discrete_map=colors,
                  category_orders={"stage_reached": STAGE_ORDER}), "Outcomes by tournament", "Editions", "Tournament", legend="Stage reached", h=420)
ed["Win %"] = (100 * ed.W / (ed.W + ed.L).where((ed.W + ed.L) > 0)).round(1)
with c2:
    f = px.bar(ed.sort_values("start"), x="edition", y="Win %", color="stage_reached", color_discrete_map=colors, text="Win %")
    f.update_traces(texttemplate="%{text:.0f}", textposition="outside"); f.update_xaxes(tickangle=60)
    T.plot(f, "Win % in each edition", "Edition", "Win %", pct=True, ylim=[0, 115], legend="Stage reached", h=420)

T.section("Edition drill-down")
sel = st.selectbox("Edition", ed.sort_values("start", ascending=False).edition)
g = m[m.edition_clean == sel].sort_values("date")
g = g.assign(label=g.date.dt.strftime("%d %b") + " v " + g.opponent)
T.plot(px.bar(g, x="label", y="run_diff", color="result", color_discrete_map=D.RES_COLORS, hover_data=["pak_score", "opp_score"]),
       f"{sel}: run difference per match (Pakistan minus opposition)", "Match", "Run difference", legend="Result")
st.dataframe(g[["date", "opponent", "stage", "venue", "pak_score", "opp_score", "result", "margin", "player_of_match"]], hide_index=True, width="stretch")
chk = ed[ed.stage_check_needed.fillna(False).astype(bool)]
st.caption("Stage reached uses Cricsheet's stage where it exists and otherwise infers it from every match in the event (see stage_source in pak_editions.csv).")
if len(chk):
    st.warning("Please double-check: " + "; ".join(f"{r.edition} ({r.P} matches, shown as {r.stage_reached})" for r in chk.itertuples()))
