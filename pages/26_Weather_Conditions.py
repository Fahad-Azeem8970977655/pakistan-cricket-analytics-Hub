import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.filters()
T.hero("Weather & Conditions", "Does temperature, rain or wind change how Pakistan performs?")
need = ["weather_tmax_c", "weather_tmin_c", "rain_mm", "wind_kmh_max"]
if m.empty:
    st.warning("No matches for these filters."); st.stop()
if any(c not in m for c in need):
    st.error("Weather columns are missing. Run `python scripts/build_pakistan_dataset_v3.py --geo --weather`, copy `output_v3/pak_matches.csv` into `data/`, then re-run build_captains.py and build_coaches.py.")
    st.stop()

x = m.dropna(subset=["weather_tmax_c"]).copy()
if x.empty:
    st.warning("None of the matches in view have weather data."); st.stop()
x["Rain"] = np.where(x.rain_mm >= 1, "Rain (1 mm or more)", "Dry")
x["Temperature"] = pd.cut(x.weather_tmax_c, [-50, 15, 25, 32, 38, 60], labels=["Under 15 °C", "15 to 25 °C", "25 to 32 °C", "32 to 38 °C", "Over 38 °C"])
x["Wind"] = pd.cut(x.wind_kmh_max, [-1, 15, 25, 200], labels=["Light (under 15 km/h)", "Moderate (15 to 25)", "Strong (over 25)"])
done = x[x.is_completed]

T.kpis([("Matches with weather", len(x), f"{len(x)} of {len(m)} in view ({100 * len(x) / len(m):.0f}%)", "green"),
        ("Average high", f"{x.weather_tmax_c.mean():.1f} °C", f"range {x.weather_tmax_c.min():.0f} to {x.weather_tmax_c.max():.0f} °C", "gold"),
        ("Rain days", int((x.rain_mm >= 1).sum()), f"{100 * (x.rain_mm >= 1).mean():.0f}% of matches", "blue"),
        ("Windiest", f"{x.wind_kmh_max.max():.0f} km/h", "daily maximum", "grey")])


def wp(df, by):
    g = df.groupby(by, observed=True).agg(P=("match_id", "count"), W=("is_win", "sum")).reset_index()
    g["Win %"] = (100 * g.W / g.P).round(1); return g


# ---- temperature -----------------------------------------------------------------------------------------------------
T.section("Temperature")
tb = wp(done, ["Temperature", "format"])
c1, c2 = st.columns(2)
with c1:
    f = px.bar(tb, x="Temperature", y="Win %", color="format", barmode="group", text="P", hover_data=["P", "W"], color_discrete_map=D.FMT_COLORS)
    f.update_traces(texttemplate="n=%{text}", textposition="outside")
    T.plot(f, "Win % by daily high temperature", "Temperature", "Win %", pct=True, ylim=[0, 115], hline=50, h=380)
with c2:
    rr = x.dropna(subset=["pak_run_rate"])
    rr = rr[rr.format != "Test"]
    f = px.scatter(rr, x="weather_tmax_c", y="pak_run_rate", color="format", color_discrete_map=D.FMT_COLORS, hover_data=["opponent", "venue", "result"], opacity=0.75)
    for fm, g in rr.groupby("format"):
        if len(g) >= 8:
            k = np.polyfit(g.weather_tmax_c, g.pak_run_rate, 1); xs = np.linspace(g.weather_tmax_c.min(), g.weather_tmax_c.max(), 20)
            f.add_scatter(x=xs, y=np.polyval(k, xs), mode="lines", line=dict(dash="dot", width=2, color=D.FMT_COLORS.get(fm)), showlegend=False, hoverinfo="skip")
    T.plot(f, "Pakistan run rate vs temperature (ODI & T20I)", "Daily high (°C)", "Runs per over", h=380)
    cors = [f"{fm}: r = {np.corrcoef(g.weather_tmax_c, g.pak_run_rate)[0, 1]:+.2f} (n={len(g)})" for fm, g in rr.groupby("format") if len(g) >= 8]
    if cors: st.caption("Correlation of temperature with run rate: " + "; ".join(cors) + ". Values near 0 mean almost no link.")

# ---- rain and wind ---------------------------------------------------------------------------------------------------
T.section("Rain and wind")
c1, c2 = st.columns(2)
with c1:
    rb = wp(done, ["Rain", "format"])
    f = px.bar(rb, x="Rain", y="Win %", color="format", barmode="group", text="P", color_discrete_map=D.FMT_COLORS)
    f.update_traces(texttemplate="n=%{text}", textposition="outside")
    T.plot(f, "Win % on dry vs rainy days (completed matches)", "", "Win %", pct=True, ylim=[0, 115], hline=50, h=340)
with c2:
    wb = wp(done, ["Wind", "format"])
    f = px.bar(wb, x="Wind", y="Win %", color="format", barmode="group", text="P", color_discrete_map=D.FMT_COLORS)
    f.update_traces(texttemplate="n=%{text}", textposition="outside")
    T.plot(f, "Win % by wind strength", "", "Win %", pct=True, ylim=[0, 115], hline=50, h=340)
lost = x[~x.is_completed]
if len(lost):
    st.caption(f"{len(lost)} matches with weather data were not completed (abandoned or no result). {int((lost.rain_mm >= 1).sum())} of them were on a rainy day. They are left out of the win % charts above.")

# ---- home / away ------------------------------------------------------------------------------------------------------
T.section("Home, away and neutral conditions")
ha = x.groupby("location_type").agg(Matches=("match_id", "count"), AvgHigh=("weather_tmax_c", "mean"), AvgLow=("weather_tmin_c", "mean"),
                                   RainDays=("rain_mm", lambda s: int((s >= 1).sum())), AvgWind=("wind_kmh_max", "mean")).round(1).reset_index()
st.dataframe(ha.rename(columns={"location_type": "Venue type", "AvgHigh": "Avg high °C", "AvgLow": "Avg low °C", "RainDays": "Rain days", "AvgWind": "Avg max wind km/h"}),
             hide_index=True, width="stretch")
hot = done.assign(Hot=np.where(done.weather_tmax_c >= 32, "32 °C or hotter", "Under 32 °C"))
hb = wp(hot, ["location_type", "Hot"])
if not hb.empty:
    f = px.bar(hb, x="location_type", y="Win %", color="Hot", barmode="group", text="P", color_discrete_sequence=[T.GOLD, T.GREEN])
    f.update_traces(texttemplate="n=%{text}", textposition="outside")
    T.plot(f, "Win % in hot vs cooler conditions, by venue type", "Venue type", "Win %", pct=True, ylim=[0, 115], hline=50, h=340)

# ---- extremes ---------------------------------------------------------------------------------------------------------
T.section("Extremes")
cols = ["date", "format", "opponent", "venue", "result", "weather_tmax_c", "rain_mm", "wind_kmh_max"]
show = lambda d: d[cols].assign(date=d.date.dt.date).rename(columns={"weather_tmax_c": "High °C", "rain_mm": "Rain mm", "wind_kmh_max": "Wind km/h"})
t1, t2, t3 = st.tabs(["Hottest", "Coldest", "Wettest"])
with t1: st.dataframe(show(x.nlargest(8, "weather_tmax_c")), hide_index=True, width="stretch")
with t2: st.dataframe(show(x.nsmallest(8, "weather_tmax_c")), hide_index=True, width="stretch")
with t3: st.dataframe(show(x.nlargest(8, "rain_mm")), hide_index=True, width="stretch")

T.note("Weather is the daily summary for the venue's city (Open-Meteo), not the conditions at the ground at match time, and day or night is not recorded. "
       "Temperature, venue and season move together (for example hot matches are mostly in the UAE or Pakistan), so a difference here is not proof that heat caused it. "
       "Bars show the number of matches (n); read small ones with care.")
