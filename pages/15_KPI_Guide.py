import pandas as pd
import streamlit as st

from utils import data as D
from utils import theme as T

D.setup()
T.hero("KPI Guide", "What each KPI means, how it is calculated, and which KPIs you could add next")
T.section("KPIs already in the dashboard")
live = pd.DataFrame([
    ("Team", "Win %", "Wins ÷ (wins + losses + ties). Draws and no-results excluded", "Overview, Rise & Fall, H2H"),
    ("Team", "Win / loss ratio", "Wins ÷ losses", "Overview"),
    ("Team", "Form (last 10)", "Wins in the 10 most recent matches, shown as W/L pills", "Overview, H2H"),
    ("Team", "Home / Away / Neutral win %", "Win % split by venue type (Home includes UAE home games)", "Overview, Opponents & Venues"),
    ("Team", "Chasing / Defending win %", "Win % when batting second / first (ODI & T20I)", "Overview, Opponents & Venues"),
    ("Team", "Toss-winner win %", "Share of matches won after Pakistan won the toss", "Overview"),
    ("Team", "Run rate and phase runs", "Runs per over; powerplay / middle / death runs per innings", "Rise & Fall, H2H"),
    ("Team", "Run difference", "Pakistan runs minus opposition runs per match", "H2H, Tournaments"),
    ("Team", "Stage reached", "Furthest round per tournament edition", "Tournaments"),
    ("Batting", "Average", "Runs ÷ dismissals", "Batting, Splits, Comparison"),
    ("Batting", "Strike rate", "Runs × 100 ÷ balls faced", "Batting, Splits, Comparison"),
    ("Batting", "Boundary %", "Runs from 4s and 6s ÷ total runs", "Splits, Comparison"),
    ("Batting", "50+ per innings, duck %", "Fifties and hundreds per innings; ducks per innings", "Batting, Comparison"),
    ("Bowling", "Bowling average", "Runs conceded ÷ wickets", "Bowling, Splits, Comparison"),
    ("Bowling", "Economy", "Runs conceded per over", "Bowling, Splits, Comparison"),
    ("Bowling", "Strike rate", "Balls bowled ÷ wickets", "Bowling, Splits, Comparison"),
    ("Bowling", "Dot-ball %", "Dot balls ÷ balls bowled", "Bowling, Splits, Comparison"),
    ("Partnerships", "Stand size, runs per 100 balls", "Runs added for a wicket; scoring rate of a pair", "Partnerships & Fielding"),
    ("Fielding", "Dismissals per match", "Catches + stumpings + run-outs ÷ matches", "Partnerships & Fielding"),
    ("Opposition", "Top scorers / wicket-takers vs Pakistan", "Opposition performance in matches against Pakistan", "Opposition Players, H2H"),
    ("Batting", "Runs above par (RAP)", "Runs minus expected runs for that format, venue country and batting-position group (shrunk to format par)", "Batting, Players, Comparison"),
    ("Batting", "Form (Hot / Steady / Cold)", "Last-5-innings RAP per innings; Hot at +10 or more, Cold at -10 or less", "Players, Overview"),
    ("Batting", "20+ rate", "Share of innings with 20 or more runs (consistency)", "Players"),
    ("Batting", "Role analysis", "Runs per innings, strike rate, share of runs for openers / No. 3 / middle / lower-middle / tail", "Batting"),
    ("Match-ups", "Opponent scouting report", "Danger men, targeted batters, phases, venues for one opponent", "Opponent Scouting"),
    ("Match-ups", "Dismissals by bowler-batter pair", "Times a bowler dismissed a batter (run-outs excluded)", "Player Comparison"),
    ("AI & ML", "Elo rating", "Rating per format that rises after wins and falls after losses; K and home advantage tuned on pre-test matches only", "Match Predictor"),
    ("AI & ML", "Pre-match win probability", "Logistic regression and gradient boosting on Elo, form, head-to-head, venue, toss; judged on later matches vs an always-base-rate baseline", "Match Predictor"),
    ("AI & ML", "Live chase probability", "Win chance after every over from runs needed, balls left, wickets in hand, required vs current run rate", "Match Predictor"),
    ("AI & ML", "Predicted first-innings par", "Ridge regression on format, venue and country history (shrunk), batting side, home/away, year", "Match Predictor"),
    ("AI & ML", "Shrunk win % / average", "Small samples blended with the overall figure: (wins + n0 x p0) / (n + n0)", "Match Predictor, Player Intelligence"),
    ("AI & ML", "Batting / bowling role (cluster)", "k-means on standardised player profile (strike rate, boundary %, balls per innings, position ...)", "Player Intelligence"),
    ("AI & ML", "Similarity index", "Closeness of two players on the same standardised profile", "Player Intelligence"),
    ("AI & ML", "Survival curve", "Kaplan-Meier chance a batter is still not out after N balls", "Player Intelligence"),
    ("AI & ML", "Match-up dismissal index", "Shrunk observed dismissal rate / rate expected from the batter's and bowler's generic strengths (balls are estimated)", "Player Intelligence"),
], columns=["Area", "KPI", "Definition", "Where"])
st.dataframe(live, hide_index=True, width="stretch", height=560)

T.section("Possible KPIs to add", "ranked by value; the right column says what data is needed")
nxt = pd.DataFrame([
    ("High", "Win % vs ICC ranking of opponent", "Opponent rankings per date", "Not in Cricsheet"),
    ("High", "Batting impact (runs above par per innings)", "Par score by venue / era from existing data", "Possible now"),
    ("High", "Wicket-taking % and economy by phase per bowler", "Over-by-over bowler data", "Partly (team level only)"),
    ("High", "Batter vs bowler runs, balls and strike rate", "Ball-by-ball rows (raw Cricsheet files)", "Re-parse needed"),
    ("Medium", "Conversion rate: 50s turned into 100s", "Already have 50s and 100s", "Possible now"),
    ("Medium", "Batting position productivity (runs per innings at #3 etc.)", "Already have positions", "Possible now"),
    ("Medium", "Death-over economy / powerplay strike rate per player", "Ball-level phase tagging", "Re-parse needed"),
    ("Medium", "Win % by captain and coach", "eras/captains.csv and coaches.csv", "Done (Captains & Coaches page)"),
    ("Medium", "Pressure index (performance in knockouts / chases)", "Existing is_knockout and chase flags", "Possible now"),
    ("Low", "Weather, pitch and day/night impact", "Weather API or pitch reports", "External data"),
    ("Low", "Fantasy / form index (rolling last-5 innings)", "Existing batting rows", "Possible now"),
    ("Low", "WTC points and ICC rating trend", "ICC data", "External data"),
], columns=["Priority", "KPI", "Needs", "Status"])
st.dataframe(nxt, hide_index=True, width="stretch")
T.note("Win % always uses completed matches, so a high-draw Test record is not inflated or deflated. Small samples (under 10 matches) are shown with a confidence interval on the Rise & Fall page.")
