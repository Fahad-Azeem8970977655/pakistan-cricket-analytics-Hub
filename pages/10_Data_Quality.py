import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.load()
T.hero("Data Quality & Coverage", "What is in the data, what is missing and the known limits")
gap = D.coverage_missing(m)
if gap:
    st.error("Missing opponents (Pakistan has played them but there are no matches in the data): **" + ", ".join(gap) + "**")
    st.markdown("Cricsheet's ZIPs do not contain these matches. Add them to `extra/missing_matches.csv` and re-run `scripts/build_pakistan_dataset_v3.py`, then copy the new CSVs into `data/`.")
else:
    st.success("All main opponents are present.")
T.kpis([("Matches", len(m), "", "green"), ("Latest match", f"{m.date.max():%d %b %Y}", "", "blue"),
        ("Manual matches", int((m.get("data_source", "cricsheet") == "manual").sum()),
         f"{int((m.get('bbb_source', pd.Series(dtype=str)) == 'ESPN play-by-play').sum())} with ESPN ball-by-ball + scorecard, {int((m.get('detail_level', pd.Series(dtype=str)) == 'result-only').sum())} result only", "gold"),
        ("Captain filled", f"{int(m.pak_captain.notna().sum())}/{len(m)}", f"{int((m.get('pak_captain_confidence', pd.Series(dtype=str)).isin(['solved', 'year-only'])).sum())} inferred, {int((m.get('pak_captain_confidence', pd.Series(dtype=str)) == 'scorecard').sum())} from scorecards", "grey"),
        ("Coach filled", f"{int(m.pak_coach.notna().sum())}/{len(m)}", f"{int((m.get('pak_coach_confidence', pd.Series(dtype=str)) == 'interim-fallback').sum())} fallback", "grey")], per_row=5)
y = m.groupby(["year", "format"]).size().unstack(fill_value=0)
T.plot(px.imshow(y.T, text_auto=True, color_continuous_scale=T.SEQ_GREEN, aspect="auto"), "Matches per year and format", "Year", "Format", cbar="Matches", h=300)
op = m.opponent.value_counts().reset_index()
T.plot(px.bar(op, x="opponent", y="count", text="count", color_discrete_sequence=[T.GREEN]).update_traces(textposition="outside"), "Matches by opponent in the data", "Opponent", "Matches")
if "detail_level" in m:
    T.section("How much detail each match has", "ball-by-ball = every delivery (Cricsheet, or ESPN play-by-play for Pakistan v Afghanistan); scorecard = batting and bowling cards only; result-only = score and result")
    st.dataframe(m.groupby(["opponent", "detail_level"]).size().unstack(fill_value=0), width="stretch")
T.section("Known limits")
st.markdown("""
- The 15 Pakistan v Afghanistan matches (2018 to 2025) are not in Cricsheet. Their scorecards were collected by hand and their deliveries come from ESPN play-by-play (`extra/afghanistan_ball_by_ball.xlsx`). Delivery totals match every innings total, and 7 disagreements with the hand-collected cards were corrected from the deliveries and 20 more values plus one missing bowling row were corrected to the Cricinfo scorecards; the last 2 batter lines (of 444) were checked on Cricinfo and the scorecard was right, so none are unresolved (see `docs/afghanistan_ballbyball_report.md`). They have no Pakistan fielding rows because the source names no fielder.
- The two 18 and 20 Oct 2026 ODIs have the result only.
- Matches abandoned without a ball bowled are not in Cricsheet.
- Stage reached is inferred where Cricsheet has no stage (see the Tournaments page for flagged editions).
- Captain and coach are filled from `eras/*.csv` (build_captains.py, build_coaches.py). Tenure sources give years or months, so some matches are inferred (see the confidence columns). Weather needs `--weather`.
- Pitch reports, day/night, rankings and WTC points are not available from Cricsheet.
""")
