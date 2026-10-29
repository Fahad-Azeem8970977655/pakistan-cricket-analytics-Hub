"""Write player split tables (SENA, England, Home, Away ...) to data/ from the existing dashboard CSVs.

    python scripts/build_player_splits.py

Reads  data/pak_matches.csv, pak_batting.csv, pak_bowling.csv
Writes data/pak_player_splits_batting.csv and data/pak_player_splits_bowling.csv

No internet needed. Re-run it whenever you refresh the data with build_pakistan_dataset_v3.py.
Batter dot balls (Dots, Dot %) appear automatically once pak_batting.csv has a dot_balls column.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils import splits as S  # noqa: E402

DATA = ROOT / "data"


def main():
    def read(name):  # manual matches have ids like "manual_1", so match_id is text in one file and a number in another: make all text
        d = pd.read_csv(DATA / f"{name}.csv"); d["match_id"] = d["match_id"].astype(str); return d
    m = read("pak_matches")
    b = S.expand(S.add_geo(read("pak_batting"), m))
    w = S.expand(S.add_geo(read("pak_bowling"), m))
    bt = S.batting_table(b).sort_values(["player", "format", "split"])
    bw = S.bowling_table(w).drop(columns=["_balls"]).sort_values(["player", "format", "split"])
    bt.to_csv(DATA / "pak_player_splits_batting.csv", index=False)
    bw.to_csv(DATA / "pak_player_splits_bowling.csv", index=False)
    print(f"batting: {len(bt)} rows | bowling: {len(bw)} rows")
    print("batter dot balls:", "included" if "Dots" in bt.columns else
          "NOT in the data yet - run build_pakistan_dataset_v3.py --refresh first")


if __name__ == "__main__":
    main()