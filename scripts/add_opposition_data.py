"""Add OPPOSITION batting / bowling / players (from the collector script's CSVs) to the dashboard data/.

    python scripts/add_opposition_data.py [folder_with_collector_csvs]      (default: incoming/)

Reads   batting_summary.csv, bowling_summary.csv, fielding_summary.csv, player_info.csv  (collector output)
Writes  data/opp_batting.csv, data/opp_bowling.csv, data/opp_fielding.csv, data/opp_players.csv
Pakistan's own rows are skipped: the dashboard already has them (verified identical: 112,297 runs, 3,794 wkts).
Only matches that exist in data/pak_matches.csv are kept, so every filter on the sidebar still works.
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "incoming"
DATA = ROOT / "data"

m = pd.read_csv(DATA / "pak_matches.csv")
keep = {int(x) for x in m.match_id.astype(str) if x.isdigit()}   # hand-added matches ("manual_1") have no opposition scorecards
b = pd.read_csv(SRC / "batting_summary.csv"); w = pd.read_csv(SRC / "bowling_summary.csv")
p = pd.read_csv(SRC / "player_info.csv")
mid = lambda s: s.str.split("#").str[1].astype(int)

# player ids (name + team -> cricsheet / cricinfo id)
ids = p[~p.isPakistan].drop_duplicates(["name", "team"]).set_index(["name", "team"])


def ident(df, name_col, team_col):
    j = df.join(ids[["cricsheetID", "cricinfoID"]], on=[name_col, team_col])
    return j.cricsheetID.fillna(""), j.cricinfoID.astype("Int64")


# ---- batting
o = b[~b.isPakistan].copy()
o["match_id"] = mid(o.matchID); o = o[o.match_id.isin(keep)]
out = o["out/not_out"].eq("out")
pid, cid = ident(o, "battername", "teamInnings")
bat = pd.DataFrame({
    "match_id": o.match_id, "date": o.matchDate, "year": o.matchDate.str[:4].astype(int), "format": o.format,
    "opponent": o.teamInnings, "innings_no": o.inningsNo, "batting_position": o.battingPos, "player": o.battername,
    "player_id": pid, "cricinfo_id": cid, "runs": o.runs, "balls": o.balls, "fours": o["4s"], "sixes": o["6s"],
    "strike_rate": o.SR, "is_out": out, "dismissal": o.dismissal,
    "is_fifty": o.runs.between(50, 99), "is_hundred": o.runs >= 100, "is_duck": out & (o.runs == 0)})
bat.to_csv(DATA / "opp_batting.csv", index=False)

# ---- bowling (opposition bowlers = bowling team is the opponent)
o = w[~w.isPakistan].copy()
o["match_id"] = mid(o.matchID); o = o[o.match_id.isin(keep)]
pid, cid = ident(o, "bowlerName", "bowlingTeam")
bowl = pd.DataFrame({
    "match_id": o.match_id, "date": o.matchDate, "year": o.matchDate.str[:4].astype(int), "format": o.format,
    "opponent": o.bowlingTeam, "innings_no": o.inningsNo, "player": o.bowlerName, "player_id": pid, "cricinfo_id": cid,
    "balls": o.balls, "overs": (o.balls // 6).astype(str) + "." + (o.balls % 6).astype(str), "maidens": o.maiden,
    "runs_conceded": o.runs, "wickets": o.wickets, "dot_balls": o["0s"], "economy": o.economy, "wides": o.wides,
    "noballs": o.noBalls, "fours_conceded": o["4s"], "sixes_conceded": o["6s"], "is_five_wkts": o.wickets >= 5})
bowl.to_csv(DATA / "opp_bowling.csv", index=False)

# ---- fielding (opposition fielders = fielding team is the opponent), summed per match like pak_fielding.csv
fpath = SRC / "fielding_summary.csv"
if fpath.exists():
    f = pd.read_csv(fpath)
    o = f[~f.isPakistan].copy()
    o["match_id"] = mid(o.matchID); o = o[o.match_id.isin(keep)]
    cols = ["catches", "caught_and_bowled", "stumpings", "runouts_direct", "runouts_assisted"]
    g = (o.groupby(["match_id", "matchDate", "format", "fieldingTeam", "player", "substitute"], as_index=False)[cols].sum())
    g = g.rename(columns={"matchDate": "date", "fieldingTeam": "opponent"})
    g["year"] = g.date.str[:4].astype(int)
    g["total_dismissals"] = g[cols].sum(axis=1)
    pid, cid = ident(g, "player", "opponent")
    g["player_id"], g["cricinfo_id"] = pid, cid
    g[["match_id", "date", "year", "format", "opponent", "player", "player_id", "cricinfo_id", "substitute"] + cols
      + ["total_dismissals"]].to_csv(DATA / "opp_fielding.csv", index=False)
    print(f"opp_fielding {len(g)} rows")
else:
    print("fielding_summary.csv not found in", SRC, "- skipping opp_fielding.csv (re-run the collector script v2)")

# ---- players who faced Pakistan
pl = p[~p.isPakistan].rename(columns={"name": "player", "team": "opponent", "cricsheetID": "player_id",
                                       "cricinfoID": "cricinfo_id", "matchesPlayed": "matches_vs_pakistan"})
pl["cricinfo_url"] = "https://www.espncricinfo.com/cricketers/" + pl.cricinfo_id.astype("Int64").astype(str)
pl.loc[pl.cricinfo_id.isna(), "cricinfo_url"] = ""
pl[["player", "opponent", "formats", "matches_vs_pakistan", "player_id", "cricinfo_id", "cricinfo_url"]] \
    .sort_values("matches_vs_pakistan", ascending=False).to_csv(DATA / "opp_players.csv", index=False)
print(f"opp_batting {len(bat)} rows | opp_bowling {len(bowl)} rows | opp_players {len(pl)} rows")