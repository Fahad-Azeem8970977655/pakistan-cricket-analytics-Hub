"""Merge extra/missing_matches.csv into data/pak_matches.csv and data/pak_editions.csv WITHOUT re-downloading Cricsheet.

Run from the project folder:   python scripts/merge_manual_into_data.py
Safe to re-run: old manual rows are removed first, then every row of extra/missing_matches.csv is added again.
Manual matches have match-level numbers only (no batting / bowling scorecards).
"""
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "build_pakistan_dataset_v3.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)

m = pd.read_csv(ROOT / "data" / "pak_matches.csv")
if "data_source" not in m: m["data_source"] = "cricsheet"
old_manual = int((m.data_source == "manual").sum())
m = m[m.data_source != "manual"]

mm = B.load_manual(ROOT / "extra" / "missing_matches.csv")
if len(mm):
    pw = mm.toss_winner.eq("Pakistan")
    pak_first = (pw & mm.toss_decision.eq("bat")) | (~pw & mm.toss_decision.eq("field"))
    mm["pak_batting_order"] = pak_first.map({True: "Batting first", False: "Batting second"})
    mm["pak_chasing"] = ~pak_first & mm.format.ne("Test")
    mm["pak_won_toss"] = pw
    m = pd.concat([m, mm], ignore_index=True)

m["is_knockout"] = m.stage_inferred.isin(["Final", "Semi Final", "Quarter Final", "Play-off"])
m = m.sort_values("date", kind="stable").reset_index(drop=True)
m.to_csv(ROOT / "data" / "pak_matches.csv", index=False)

# editions (same formula as the builder)
ed = []
mm_ = m[m.edition.notna() & (m.edition != "")]
for e, g in mm_.groupby("edition"):
    end = g.date.max()
    sr = B.stage_reached(g)
    ed.append(dict(edition=e, tournament_group=g.tournament_group.iloc[0], year=int(g.year.iloc[0]), format=g.format.iloc[0],
                   start=g.date.min(), end=end, played=len(g), won=int((g.result == "Won").sum()), lost=int((g.result == "Lost").sum()),
                   stage_reached=sr, stage_source=g.stage_source.iloc[-1],
                   provisional=end >= (date.today() - timedelta(days=7)).isoformat(),
                   stage_check_needed=(sr == "Group/League stage" and len(g) > {"T20 World Cup": 5, "Champions Trophy": 3}.get(g.tournament_group.iloc[0], 99))))
pd.DataFrame(ed).sort_values("start").to_csv(ROOT / "data" / "pak_editions.csv", index=False)
print(f"Done. Removed {old_manual} old manual rows, added {len(mm)}. Matches now: {len(m)}  (Afghanistan: {int((m.opponent == 'Afghanistan').sum())}).")
