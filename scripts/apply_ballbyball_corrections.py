"""Correct the hand-collected scorecard rows that the ESPN deliveries show to be wrong.

    python scripts/apply_ballbyball_corrections.py      (run AFTER scripts/merge_afghanistan_ballbyball.py)

Only cases where an independent check says the CARD is wrong are changed (evidence in docs/afghanistan_ballbyball_report.md):
  manual_9  inn2 Pakistan batters : fours/sixes (card 27 / 3; bowling card and deliveries 23 / 1; Naseem Shah's card line is arithmetically impossible)
  manual_3  inn1 Afghan batters   : fours/sixes (card 18 / 4; bowling card and deliveries 15 / 5)
  manual_12 inn1 Pakistan batters : sixes (card 6; bowling card and deliveries 9)
  manual_4  inn1 Afghan batters   : fours/sixes (card 6 fours; bowling card and deliveries 10)
  manual_14 inn2 Afghan bowlers   : card has Karim Janat bowling 4 overs; deliveries have Noor Ahmad. Card runs sum to 150, innings needs 145.
  manual_4  inn2 Afghan bowlers   : card omits Azmatullah Omarzai and its runs sum to 126, innings needs 127. The innings is rebuilt from the deliveries.
Everything else that disagrees stays as collected and is only reported.  Idempotent: a second run changes nothing.  Before/after values: docs/afghanistan_ballbyball_corrections.csv
"""
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, BACKUP = ROOT / "data", ROOT / "backup_pre_ball_by_ball"
rd = lambda n: pd.read_csv(DATA / f"{n}.csv", low_memory=False).assign(match_id=lambda d: d.match_id.astype(str)) if False else pd.read_csv(DATA / f"{n}.csv", dtype={"match_id": str}, low_memory=False)
for rel in ("data/opp_batting.csv", "data/opp_bowling.csv", "data/pak_batting.csv", "data/pak_matches.csv"):
    dst = BACKUP / rel
    if not dst.exists(): dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / rel, dst)

d = pd.read_csv(DATA / "pak_deliveries.csv.gz", dtype={"match_id": str}, low_memory=False); d = d[d.match_id.str.startswith("manual_")]
changes = []


def batter_fix(table, mid, inn, cols):
    t = rd(table); sel = (t.match_id == mid) & (t.innings_no == inn)
    x = d[(d.match_id == mid) & (d.innings_no == inn)].groupby("batter").agg(fours=("is_four", "sum"), sixes=("is_six", "sum"))
    for i in t[sel].index:
        p = t.at[i, "player"]
        if p not in x.index: continue
        for c in cols:
            if t.at[i, c] != x.at[p, c]:
                changes.append(dict(table=table, match_id=mid, innings=inn, who=p, field=c, before=t.at[i, c], after=int(x.at[p, c]))); t.at[i, c] = int(x.at[p, c])
    t.to_csv(DATA / f"{table}.csv", index=False)


batter_fix("pak_batting", "manual_9", 2, ("fours", "sixes"))
batter_fix("opp_batting", "manual_3", 1, ("fours", "sixes"))
batter_fix("pak_batting", "manual_12", 1, ("sixes",))
batter_fix("opp_batting", "manual_4", 1, ("fours", "sixes"))


def bowler_rows(mid, inn):
    """Bowling figures for one innings from the deliveries (same rules as the Cricsheet build)."""
    x = d[(d.match_id == mid) & (d.innings_no == inn)].copy()
    x["br"] = x.runs_total - np.where(x.extras_type.isin(["byes", "legbyes"]), x.runs_extras, 0)
    out = []
    for b, y in x.groupby("bowler", sort=False):
        balls = int(y.is_legal.sum()); mdn = 0
        for _, o in y.groupby("over"):
            if o.is_legal.sum() == 6 and o.br.sum() == 0: mdn += 1
        runs = int(y.br.sum()); w = int(y.bowler_wicket.sum())
        out.append(dict(player=b, balls=balls, overs=float(f"{balls // 6}.{balls % 6}"), maidens=mdn, runs_conceded=runs, wickets=w,
                        dot_balls=int(((y.is_legal == 1) & (y.runs_batter == 0)).sum()), economy=round(6 * runs / balls, 2) if balls else np.nan,
                        wides=int((y.extras_type == "wides").sum()), noballs=int((y.extras_type == "noballs").sum()),
                        fours_conceded=int(y.is_four.sum()), sixes_conceded=int(y.is_six.sum()), is_five_wkts=w >= 5))
    return out


def rebuild_bowling(mid, inn):
    t = rd("opp_bowling"); sel = (t.match_id == mid) & (t.innings_no == inn)
    old, new = t[sel], pd.DataFrame(bowler_rows(mid, inn))
    if len(old) == len(new) and set(old.player) == set(new.player) and all((old.set_index("player").loc[new.player][c].values == new[c].values).all() for c in ("balls", "runs_conceded", "wickets", "wides", "noballs")):
        return   # already corrected
    ids = rd("opp_batting").query("match_id == @mid").set_index("player").cricinfo_id.to_dict()
    ids.update(t[t.cricinfo_id.notna()].drop_duplicates("player").set_index("player").cricinfo_id.to_dict())
    base = t[sel].iloc[0]
    for _, r in old.iterrows(): changes.append(dict(table="opp_bowling", match_id=mid, innings=inn, who=r.player, field="row (old card)", before=f"{int(r.balls)} balls {int(r.runs_conceded)} runs {int(r.wickets)} wkts", after=""))
    for r in new.itertuples():
        changes.append(dict(table="opp_bowling", match_id=mid, innings=inn, who=r.player, field="row (from deliveries)", before="", after=f"{r.balls} balls {r.runs_conceded} runs {r.wickets} wkts"))
    rows = pd.DataFrame([{**{c: base[c] for c in ("match_id", "date", "year", "format", "opponent", "innings_no")}, "player_id": np.nan,
                          "cricinfo_id": ids.get(r["player"], np.nan), **r} for r in new.to_dict("records")])
    pos = t[sel].index.min()
    t = pd.concat([t[~sel].iloc[:0], t.loc[:pos - 1][~t.loc[:pos - 1].index.isin(t[sel].index)], rows[t.columns], t.loc[pos:][~t.loc[pos:].index.isin(t[sel].index)]], ignore_index=True)
    t.to_csv(DATA / "opp_bowling.csv", index=False)


rebuild_bowling("manual_14", 2)
rebuild_bowling("manual_4", 2)

# match-level columns that depend on the corrected rows
m = rd("pak_matches")
pb, ow = rd("pak_batting"), rd("opp_bowling")
for mid in ("manual_9", "manual_12"):
    b = pb[pb.match_id == mid]; r = m.loc[m.match_id == mid].iloc[0]
    new = dict(pak_fours=int(b.fours.sum()), pak_sixes=int(b.sixes.sum()), pak_boundary_pct=round(100 * (4 * b.fours.sum() + 6 * b.sixes.sum()) / r.pak_runs, 1))
    for k, v in new.items():
        if m.loc[m.match_id == mid, k].iloc[0] != v: changes.append(dict(table="pak_matches", match_id=mid, innings="", who="", field=k, before=m.loc[m.match_id == mid, k].iloc[0], after=v)); m.loc[m.match_id == mid, k] = v
for mid in ("manual_14", "manual_4"):
    b = ow[ow.match_id == mid].sort_values(["wickets", "runs_conceded"], ascending=[False, True]).iloc[0]
    new = dict(opp_best_bowler=b.player, opp_best_bowling=f"{int(b.wickets)}/{int(b.runs_conceded)}")
    for k, v in new.items():
        if m.loc[m.match_id == mid, k].iloc[0] != v: changes.append(dict(table="pak_matches", match_id=mid, innings="", who="", field=k, before=m.loc[m.match_id == mid, k].iloc[0], after=v)); m.loc[m.match_id == mid, k] = v
m.to_csv(DATA / "pak_matches.csv", index=False)

log = ROOT / "docs" / "afghanistan_ballbyball_corrections.csv"
if changes: pd.DataFrame(changes).to_csv(log, index=False)
print(f"{len(changes)} changes this run" + ("" if changes else " (already applied; log left as it was)"))
