"""Fixes found by web verification on 2026-10-21. Idempotent. Run from project folder:
python scripts/apply_verification_fixes.py"""
import pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent

CAPTAIN_FIX = {  # date -> (captain, source note)
    "2026-05-16": "Shan Masood",      # Bangladesh Test 2: AP/Prothom Alo/Dhaka Tribune toss reports
    "2026-07-25": "Babar Azam",       # WI Test 1: Babar reappointed Test captain before tour (Al Jazeera/Geo)
    "2026-08-19": "Salman Ali Agha",  # Headingley: Babar injured, Agha led (AFP/PCB)
    "2026-08-27": "Babar Azam",       # Lord's: Babar returned as captain (AP/Geo)
    "2026-09-09": "Babar Azam",       # Edgbaston: Agha sent home, Babar fit (not directly confirmed)
}
NEW = dict(match_id="manual_16", date="2026-10-18", end_date="2026-10-18", days_played=1.0, year=2026, month=10,
    season="2026/27", format="ODI", opponent="Sri Lanka", venue="Rawalpindi Cricket Stadium", city="Rawalpindi",
    venue_country="Pakistan", location_type="Home", tournament="Pakistan ODI Tri-Series", tournament_type="Tri-series",
    tournament_group="Tri-series", stage_detail="Group", match_number=1.0, toss_winner="Sri Lanka", toss_decision="field",
    pak_won_toss=False, pak_batting_order="Batting first", result="Won", margin="37 runs", margin_type="runs", margin_value=37.0,
    is_win=True, is_loss=False, is_completed=True, win_points=1.0, won_toss_and_match=False, pak_score="305/10", opp_score="268/10",
    pak_runs=305, pak_wkts_lost=10, opp_runs=268, opp_wkts_lost=10, run_diff=37, pak_chasing=False, pak_top_scorer="Salman Ali Agha",
    pak_top_score=107.0, pak_hundreds=1.0, opp_target_chased=306.0, stage_inferred="Group/League", stage_source="manual",
    data_source="manual", is_knockout=False, pak_captain="Shaheen Shah Afridi", pak_coach="Mike Hesson",
    pak_captain_confidence="manual", pak_coach_confidence="clean")

def fix(path):
    m = pd.read_csv(path)
    for d, c in CAPTAIN_FIX.items():
        k = (m.format == "Test") & (m.date == d)
        assert k.sum() == 1, d
        m.loc[k, ["pak_captain", "pak_captain_confidence"]] = [c, "manual"]
    k = m.edition == "T20 World Cup 2026"
    for d in ["2026-02-24", "2026-02-28"]:
        m.loc[k & (m.date == d), ["stage_detail", "stage_inferred", "stage_source"]] = ["Super 8", "Super stage", "manual"]
    m.loc[k & (m.date < "2026-02-24"), "stage_detail"] = "Group"
    m.loc[k & (m.date < "2026-02-24"), "stage_source"] = "manual"
    m = m[~((m.date == NEW["date"]) & (m.opponent == "Sri Lanka") & (m.format == "ODI"))]
    m = pd.concat([m, pd.DataFrame([NEW])], ignore_index=True).sort_values("date", kind="stable")
    m.to_csv(path, index=False)
    return m

m = fix(R / "data/pak_matches.csv"); fix(R / "output_v3/pak_matches.csv")

# editions
e = pd.read_csv(R / "data/pak_editions.csv")
k = e.edition == "T20 World Cup 2026"
e.loc[k, ["stage_reached", "stage_source", "stage_check_needed"]] = ["Super stage", "manual", False]
e.to_csv(R / "data/pak_editions.csv", index=False); e.to_csv(R / "output_v3/pak_editions.csv", index=False)

# eras/captains.csv
c = pd.read_csv(R / "eras/captains.csv")
c = c[~((c.format == "Test") & (c.from_date >= "2026-05-16"))]
c = pd.concat([c, pd.DataFrame([
    ("Test", "Shan Masood", "2026-05-16", "2026-05-16"), ("Test", "Babar Azam", "2026-07-25", "2026-08-02"),
    ("Test", "Salman Ali Agha", "2026-08-19", "2026-08-19"), ("Test", "Babar Azam", "2026-08-27", "2026-09-09")],
    columns=c.columns)])
# merge Masood stint with 2026-05-08 start
c.loc[(c.format == "Test") & (c.person == "Shan Masood") & (c.from_date == "2024-08-21"), "to_date"] = "2026-05-16"
c = c[~((c.format == "Test") & (c.from_date == "2026-05-16"))]
c = c.sort_values(["format", "from_date"]); c.to_csv(R / "eras/captains.csv", index=False)

# eras/coaches.csv: ODI Hesson through the new match
k = pd.read_csv(R / "eras/coaches.csv")
k.loc[(k.format == "ODI") & (k.person == "Mike Hesson"), "to_date"] = "2026-10-18"
k.to_csv(R / "eras/coaches.csv", index=False)

# extra/missing_matches.csv (persistence)
x = pd.read_csv(R / "extra/missing_matches.csv")
if not ((x.date == "2026-10-18") & (x.format == "ODI")).any():
    x = pd.concat([x, pd.DataFrame([dict(date="2026-10-18", format="ODI", opponent="Sri Lanka", venue="Rawalpindi Cricket Stadium",
        city="Rawalpindi", tournament="Pakistan ODI Tri-Series", stage="Group", result="Won", margin="37 runs", pak_score="305/10",
        opp_score="268/10", toss_winner="Sri Lanka", toss_decision="field", player_of_match="")])])
    x.to_csv(R / "extra/missing_matches.csv", index=False)
print(len(m), m.pak_captain_confidence.value_counts().to_dict())

# --- second pass (web check of remaining 2026 matches) ---
# Added 2026-10-20 ODI v England (manual_17: Won by 87 runs, 302/9 v 215, POM Arafat Minhas, Shaheen captain) and
# corrected Lord's 2026 Test score to 110/10 & 194/10 (wkts lost 20). See docs/DATA_NOTES.md verification log.
