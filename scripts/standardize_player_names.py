"""Rename Cricsheet spellings to the names players use (Cricinfo/PCB). Idempotent; re-run after any rebuild:
python scripts/standardize_player_names.py   (player_cricsheet_name column is left as Cricsheet spells it)"""
import pandas as pd, re
from pathlib import Path
R = Path(__file__).resolve().parent.parent
FIX = {"Agha Salman": "Salman Ali Agha", "Hassan Nawaz": "Hasan Nawaz"}
pat = re.compile("|".join(re.escape(k) for k in FIX))
files = [p for d in ("data", "output_v3") for p in (R / d).glob("*.csv*")]
changed = {}
for p in files:
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    n = 0
    for c in df.columns:
        if c == "player_cricsheet_name": continue
        s = df[c]; hit = s.str.contains(pat)
        if hit.any():
            df[c] = s.where(~hit, s.str.replace(pat, lambda m: FIX[m.group(0)], regex=True)); n += int(hit.sum())
    if n:
        df.to_csv(p, index=False, lineterminator="\r\n", compression="gzip" if p.suffix == ".gz" else None); changed[p.name] = n
print(changed)
