"""Check extra/missing_matches.csv (Afghanistan etc.) BEFORE running the dataset builder.

    python scripts/check_missing_matches.py

Prints every problem it finds. Exit code 0 = ready to build. Columns (header must be exactly this):
  date,format,opponent,venue,city,tournament,stage,result,margin,pak_score,opp_score,toss_winner,toss_decision,player_of_match

How to fill a row (values are typed as shown, one match per line):
  date            2023-10-23                     YYYY-MM-DD (first day for Tests)
  format          ODI | T20I | Test
  opponent        Afghanistan                    (country name exactly as in the dashboard)
  venue, city     M. A. Chidambaram Stadium, Chennai   (venue/city decide Home/Away/Neutral)
  tournament      ICC Men's Cricket World Cup    (or e.g. "Pakistan v Afghanistan ODI Series")
  stage           Group / Final / ... (can be empty)
  result          Won | Lost | Tied | Draw | No result      (from PAKISTAN's point of view)
  margin          "8 wickets" / "20 runs" / "innings and 20 runs"
  pak_score       "282/7"   (Tests: "300 & 150/4"; all out = "282/10")
  opp_score       "286/2"
  toss_winner     Pakistan | Afghanistan
  toss_decision   bat | field
  player_of_match name (can be empty)
Manual rows count in win/loss, opponents, tournaments and venues. They have NO ball-by-ball detail, so they do not
appear in batting / bowling / splits.
"""
import re
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "extra" / "missing_matches.csv"
HEADER = ["date", "format", "opponent", "venue", "city", "tournament", "stage", "result", "margin",
          "pak_score", "opp_score", "toss_winner", "toss_decision", "player_of_match"]
SCORE = re.compile(r"^\d+(/\d+)?( ?& ?\d+(/\d+)?)*( ?d)?$")


def main():
    problems, warns = [], []
    x = pd.read_csv(PATH, dtype=str).fillna("")
    if list(x.columns) != HEADER:
        sys.exit(f"Header must be exactly:\n{','.join(HEADER)}\nfound:\n{','.join(x.columns)}")
    if x.empty:
        print("File has a header only: no manual matches yet."); return 0
    m = pd.read_csv(ROOT / "data" / "pak_matches.csv", parse_dates=["date"])
    opps = set(m.opponent) | {"Afghanistan"}
    for i, r in x.iterrows():
        n = i + 2  # spreadsheet row number
        err = lambda msg: problems.append(f"row {n}: {msg}")
        d = pd.to_datetime(r.date, format="%Y-%m-%d", errors="coerce")
        if pd.isna(d): err(f"date '{r.date}' must be YYYY-MM-DD")
        elif not (2015 <= d.year <= 2026): warns.append(f"row {n}: date outside 2015-2026")
        if r.format not in ("Test", "ODI", "T20I"): err(f"format '{r.format}' must be Test, ODI or T20I")
        if r.opponent not in opps: err(f"opponent '{r.opponent}' unknown (use the same spelling as the dashboard)")
        if not r.venue and not r.city: err("venue or city is needed to decide Home/Away/Neutral")
        if r.result not in ("Won", "Lost", "Tied", "Draw", "No result"):
            err(f"result '{r.result}' must be Won, Lost, Tied, Draw or No result (Pakistan's view)")
        if r.result in ("Won", "Lost") and not r.margin: warns.append(f"row {n}: margin empty for a {r.result}")
        for c in ("pak_score", "opp_score"):
            if r[c] and not SCORE.match(r[c].strip()): err(f"{c} '{r[c]}' looks wrong (examples: 282/7, 300 & 150/4)")
        if r.toss_decision and r.toss_decision not in ("bat", "field"): err("toss_decision must be bat or field")
        if r.toss_winner and r.toss_winner not in ("Pakistan", r.opponent): err(f"toss_winner must be Pakistan or {r.opponent}")
        if not pd.isna(d):
            same = m[(m.date == d) & (m.opponent == r.opponent)]
            if len(same): err("already in Cricsheet data (same date + opponent): remove this row")
    dup = x.duplicated(["date", "format", "opponent"], keep=False)
    for i in x.index[dup]: problems.append(f"row {i+2}: duplicate of another row (same date/format/opponent)")
    print(f"{len(x)} manual rows checked")
    for w in warns: print("  warning:", w)
    for p in problems: print("  PROBLEM:", p)
    if problems:
        print(f"\n{len(problems)} problem(s): fix them, then run again."); return 1
    print("\nAll good. Next: python scripts/build_pakistan_dataset_v3.py --refresh   (then see README)"); return 0


if __name__ == "__main__":
    sys.exit(main())
