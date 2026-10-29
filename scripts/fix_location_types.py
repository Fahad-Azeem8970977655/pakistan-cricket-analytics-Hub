"""Re-label Home (UAE) matches in the existing data/ CSVs WITHOUT re-downloading anything.

    python scripts/fix_location_types.py

Fixes Pakistan's home series played in the UAE that were tagged 'Neutral' (2015 England, 2016 West Indies,
2017 Sri Lanka ODIs). Same rule as the patched classify_location() in build_pakistan_dataset_v3.py.
Safe to run more than once. Re-run scripts/build_player_splits.py afterwards (this script does it for you).
"""
import re, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TABLES = ["pak_matches", "pak_batting", "pak_bowling", "pak_fielding", "pak_partnerships"]


def should_be_home_uae(r):
    t = str(r.tournament) if pd.notna(r.tournament) else ""
    if r.venue_country != "UAE" or r.tournament_type != "Bilateral":
        return False
    return bool(re.match(r"^Pakistan v ", t, re.I)) or t.strip() == "Pakistan tour of United Arab Emirates"


m = pd.read_csv(DATA / "pak_matches.csv")
fix = m[(m.location_type == "Neutral") & m.apply(should_be_home_uae, axis=1)]
ids = set(fix.match_id)
print(f"matches to relabel Neutral -> Home (UAE): {len(ids)}")
for t in TABLES:
    d = pd.read_csv(DATA / f"{t}.csv")
    k = d.match_id.isin(ids) & d.location_type.eq("Neutral")
    d.loc[k, "location_type"] = "Home (UAE)"
    d.to_csv(DATA / f"{t}.csv", index=False)
    print(f"  {t}: {int(k.sum())} rows updated")
sys.path.insert(0, str(ROOT / "scripts"))
import build_player_splits
build_player_splits.main()
