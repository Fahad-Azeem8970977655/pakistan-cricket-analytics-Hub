"""Pakistan Cricket Analytics: entry point / router.  Run with:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Pakistan Cricket Analytics", page_icon="🏏", layout="wide")

from utils import data as D  # noqa: E402
from utils import theme as _T  # noqa: E402

_lp = _T.logo_path()
if _lp:
    st.logo(_lp, size="large")

nav = st.navigation({
    "Overview": [st.Page("views/overview.py", title="Executive Overview", icon="🏏", default=True),
                 st.Page("pages/15_KPI_Guide.py", title="KPI Guide", icon="📖")],
    "Team": [st.Page("pages/1_Rise_and_Fall.py", title="Rise & Fall", icon="📈"),
             st.Page("pages/2_Tournaments.py", title="Tournaments", icon="🏆"),
             st.Page("pages/3_Opponents_and_Venues.py", title="Opponents & Venues", icon="🌍"),
             st.Page("pages/13_Head_to_Head.py", title="Head-to-Head", icon="⚔️"),
             st.Page("pages/22_Toss_and_Chase.py", title="Toss & Chase", icon="🪙"),
             st.Page("pages/23_Venue_Profiles.py", title="Venue Profiles", icon="🏟️"),
             st.Page("pages/26_Weather_Conditions.py", title="Weather & Conditions", icon="🌦️"),
             st.Page("pages/16_Opponent_Scouting.py", title="Opponent Scouting", icon="🕵️"),
             st.Page("pages/8_Innings_Progress.py", title="Innings Progress", icon="📊")],
    "Players": [st.Page("pages/4_Batting.py", title="Batting", icon="🏏"),
                st.Page("pages/5_Bowling.py", title="Bowling", icon="🎯"),
                st.Page("pages/7_Partnerships_and_Fielding.py", title="Partnerships & Fielding", icon="🤝"),
                st.Page("pages/9_Players.py", title="Players", icon="👤"),
                st.Page("pages/20_Captains_and_Coaches.py", title="Captains & Coaches", icon="🧢"),
                st.Page("pages/21_Captain_Coach_Impact.py", title="Captain & Coach Impact", icon="🧬"),
                st.Page("pages/25_Player_Form.py", title="Player Form", icon="📉"),
                st.Page("pages/27_Phase_Analysis.py", title="Phase Analysis", icon="⏱️"),
                st.Page("pages/11_Player_Splits.py", title="Player Splits", icon="📍"),
                st.Page("pages/14_Player_Comparison.py", title="Player Comparison", icon="🆚"),
                st.Page("pages/12_Opposition_Players.py", title="Opposition Players", icon="🎯")],
    "AI & ML": [st.Page("pages/17_Match_Predictor.py", title="Match Predictor", icon="🔮"),
                st.Page("pages/18_Player_Intelligence.py", title="Player Intelligence", icon="🧠"),
                st.Page("pages/19_Ask_the_Data.py", title="Ask the Data (Groq)", icon="💬")],
    "Data": [st.Page("pages/6_Match_Explorer.py", title="Match Explorer", icon="🔎"),
             st.Page("pages/24_Match_One_Pager.py", title="Match One-Pager", icon="📄"),
             st.Page("pages/10_Data_Quality.py", title="Data Quality", icon="🧪")],
})
st.session_state["_routed"] = True
D.render_filters()
nav.run()