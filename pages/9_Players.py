import plotly.express as px
import streamlit as st

from utils import analytics as A
from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
X = D.load_extra()
a = D.by_ids(X["apps"], set(m.match_id))
pl = X["players"]
T.hero("Players", "Appearances, careers and squad churn")
if a.empty:
    st.warning("No data for these filters."); st.stop()

cnt = a.groupby(["player_id", "player"]).agg(Matches=("match_id", "nunique"), First=("date", "min"), Last=("date", "max")).reset_index()
cnt = cnt.merge(pl[["player_id", "cricinfo_url"]], on="player_id", how="left")
T.kpis([("Players used", len(cnt), "", "green"), ("Most capped", cnt.sort_values("Matches").iloc[-1].player, f"{int(cnt.Matches.max())} matches", "gold"),
        ("Avg team changes / year", f"{a.groupby('year').player_id.nunique().mean():.0f}", "distinct players per year", "blue")], per_row=3)
c1, c2 = st.columns(2)
with c1:
    f = px.bar(cnt.sort_values("Matches", ascending=False).head(20).sort_values("Matches"), y="player", x="Matches", orientation="h", text="Matches", color_discrete_sequence=[T.GREEN])
    f.update_traces(textposition="outside")
    T.plot(f, "Most appearances (top 20)", "Matches", "Player", h=520)
deb = pl.assign(year=pl.first_match.dt.year).groupby("year").size().reset_index(name="players")
with c2:
    T.plot(px.bar(deb, x="year", y="players", text="players", color_discrete_sequence=[T.GOLD]).update_traces(textposition="outside"),
           "Players making their first appearance, by year", "Year of first appearance", "Players", h=520)
st.caption("First-appearance years before 2016 mean 'already in the side when the data starts in 2015'.")

top = cnt.sort_values("Matches", ascending=False).head(25)
T.plot(px.timeline(top, x_start="First", x_end="Last", y="player", color="Matches", color_continuous_scale=T.SEQ_GREEN).update_yaxes(autorange="reversed"),
       "Career span in the data (top 25 by matches)", "Date", "Player", cbar="Matches", h=620)
ya = a.groupby(["year", "format"]).player_id.nunique().reset_index(name="players_used")
T.plot(px.bar(ya, x="year", y="players_used", color="format", barmode="group", color_discrete_map=D.FMT_COLORS), "Different players used per year (squad churn)", "Year", "Players used", legend="Format")

T.section("Form guide", "last 5 innings / spells vs career; active players only")
T.note("Batting form uses runs above par (format, venue and position adjusted). Hot = last-5 average at least +10 runs above par per innings; Cold = at least 10 below. "
       "Bowling: Hot = 30% more wickets per spell than career without leaking runs; Cold = 40% fewer wickets or economy 1.5+ worse.")
ff = A.batting_form(b)
fw = A.bowling_form(w)
t1, t2 = st.tabs(["Batters", "Bowlers"])
with t1:
    if ff.empty: st.info("No batter has 15+ innings and recent matches under these filters.")
    else:
        k1, k2, k3 = st.columns(3)
        k1.markdown(T.kpi_html("In form", int(ff.Status.str.contains("Hot").sum()), ", ".join(ff[ff.Status.str.contains("Hot")].Player.head(3)), "green"), unsafe_allow_html=True)
        k2.markdown(T.kpi_html("Steady", int(ff.Status.str.contains("Steady").sum()), "", "grey"), unsafe_allow_html=True)
        k3.markdown(T.kpi_html("Out of form", int(ff.Status.str.contains("Cold").sum()), ", ".join(ff[ff.Status.str.contains("Cold")].Player.tail(3)), "red"), unsafe_allow_html=True)
        st.write("")
        d = ff.melt("Player", ["Career RAP/inn", "Last-5 RAP/inn"], var_name="Period", value_name="RAP/inn")
        f = px.bar(d, x="Player", y="RAP/inn", color="Period", barmode="group", color_discrete_map={"Career RAP/inn": "#9AA5AD", "Last-5 RAP/inn": T.GREEN},
                   category_orders={"Player": ff.Player.tolist()})
        f.update_xaxes(tickangle=-40)
        T.plot(f, "Batting form: last 5 innings vs career (runs above par per innings)", "Batter", "Runs above par per innings", legend="Period", h=430)
        st.dataframe(ff, hide_index=True, width="stretch", height=380)
        who_f = st.selectbox("Rolling form for", ff.Player.tolist(), key="rf")
        xr = A.with_rap(b[b.player == who_f]).sort_values(["date", "innings_no"])
        xr["Rolling 5"] = xr.rap.rolling(5, min_periods=5).mean(); xr["Rolling 10"] = xr.rap.rolling(10, min_periods=10).mean(); xr["n"] = range(1, len(xr) + 1)
        l = xr.melt("n", ["Rolling 5", "Rolling 10"], var_name="Window", value_name="v").dropna()
        if len(l): T.plot(px.line(l, x="n", y="v", color="Window", color_discrete_sequence=[T.GREEN, T.GOLD]), f"{who_f}: rolling runs above par per innings", "Innings number", "Runs above par per innings (rolling avg)", hline=0, legend="Window")
with t2:
    if fw.empty: st.info("No bowler has 15+ spells and recent matches under these filters.")
    else:
        d = fw.melt("Player", ["Wkts per spell (career)", "Wkts per spell (last 5)"], var_name="Period", value_name="Wickets per spell")
        d["Period"] = d.Period.str.replace("Wkts per spell ", "")
        f = px.bar(d, x="Player", y="Wickets per spell", color="Period", barmode="group", color_discrete_map={"(career)": "#9AA5AD", "(last 5)": T.GREEN},
                   category_orders={"Player": fw.Player.tolist()})
        f.update_xaxes(tickangle=-40)
        T.plot(f, "Bowling form: last 5 spells vs career (wickets per spell)", "Bowler", "Wickets per spell", legend="Period", h=430)
        st.dataframe(fw, hide_index=True, width="stretch", height=380)

T.section("Player profile")
who = st.selectbox("Player", cnt.sort_values("Matches", ascending=False).player)
r = cnt[cnt.player == who].iloc[0]
pid = r.player_id
bb, ww = b[b.player_id == pid], w[w.player_id == pid]
fl = D.by_ids(X["field"], set(m.match_id)); fl = fl[fl.player_id == pid]
T.kpis([("Matches", int(r.Matches), "", "green"), ("Runs", int(bb.runs.sum()), "", "green"), ("Wickets", int(ww.wickets.sum()), "", "blue"),
        ("Catches", int(fl.catches.sum()), "", "gold"), ("Stumpings", int(fl.stumpings.sum()), "", "gold")], per_row=5)
if isinstance(r.cricinfo_url, str) and r.cricinfo_url:
    st.link_button("Open Cricinfo profile", r.cricinfo_url)
ap = a[a.player_id == pid]
T.plot(px.bar(ap.groupby(["year", "format"]).size().reset_index(name="matches"), x="year", y="matches", color="format", color_discrete_map=D.FMT_COLORS),
       f"{who}: matches per year", "Year", "Matches", legend="Format")
rec = D.grouped_record(ap.merge(m[["match_id"]].drop_duplicates(), on="match_id").assign(), ["format"])
st.caption("Team record when he played: " + ", ".join(f"{x.format} {x.W}W-{x.L}L ({x['Win %']}%)" for _, x in rec.iterrows()))
st.dataframe(cnt.sort_values("Matches", ascending=False), hide_index=True, width="stretch", height=300,
             column_config={"cricinfo_url": st.column_config.LinkColumn("Cricinfo", display_text="open")})
