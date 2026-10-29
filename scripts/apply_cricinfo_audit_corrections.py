"""Apply the Cricinfo-verified corrections from the audit (docs/cricinfo_audit.xlsx) to the Pakistan v Afghanistan scorecard rows.

    python scripts/apply_cricinfo_audit_corrections.py     (run AFTER scripts/apply_ballbyball_corrections.py, BEFORE the final merge_afghanistan_ballbyball.py)

Source of truth: docs/cricinfo_audit_corrections.csv (one line per changed cell, with the Cricinfo scorecard URL that was opened).
  * 20 cell changes: manual_4 (Fakhar / Khushdil / Omarzai balls, Haris Rauf wides + sixes), manual_11 (Pakistan wides; Afghan bowlers Fareed, Qais, Zahir, Gulbadin)
  * 1 missing row  : manual_11 inn1 Sharafuddin Ashraf 3-0-17-0 (fours / sixes / dots / maidens derived from the ESPN deliveries; the Cricinfo card does not publish them)
  * 21 Cricinfo player IDs for the four Afghan players whose IDs were a tie in the workbook (Abdul Rahman 819507, Darwish Rasooli 819441, Noor Ahmad 1182529,
    AM Ghazanfar 1326798): opp_batting / opp_bowling / opp_fielding / opp_players, from the Cricinfo profile pages in the audit. Also recorded in extra/cricinfo_id_conflicts.csv.
  * manual_14 Noor Ahmad is retained (Cricinfo lists him, not Karim Janat), so nothing changes there.
  * manual_2 Haris Sohail 27 (57) and Imad Wasim 49 (54): Cricinfo agrees with the scorecard, so nothing is changed; the deliveries are one ball off for each.
    docs/cricinfo_verified_exceptions.csv tells scripts/merge_afghanistan_ballbyball.py to mark those two checks as Cricinfo-verified instead of failing.

Columns that depend on a changed cell are recomputed: strike_rate (balls), overs and economy (bowling), and in pak_matches the wides / no-balls / fours / sixes
bowled, opp_best_bowler and opp_best_bowling. Idempotent: a second run changes nothing. Files it touches are copied once to backup_pre_cricinfo_audit/.
"""
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, BACKUP = ROOT / "data", ROOT / "backup_pre_cricinfo_audit"
FILES = ("data/pak_batting.csv", "data/opp_batting.csv", "data/pak_bowling.csv", "data/opp_bowling.csv", "data/pak_matches.csv")
FILES += ("data/opp_fielding.csv", "data/opp_players.csv")
for rel in FILES:
    dst = BACKUP / rel
    if not dst.exists(): dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / rel, dst)

rd = lambda n: pd.read_csv(DATA / f"{n}.csv", dtype={"match_id": str}, low_memory=False)
tabs = {n: rd(n) for n in ("pak_batting", "opp_batting", "pak_bowling", "opp_bowling")}
ID_TABLES = ("opp_fielding", "opp_players")   # integer IDs in these two files (floats in the others), so keep that format
for n in ID_TABLES: tabs[n] = pd.read_csv(DATA / f"{n}.csv", dtype={"match_id": str, "cricinfo_id": "Int64"}, low_memory=False)
fixes = pd.read_csv(ROOT / "docs" / "cricinfo_audit_corrections.csv", dtype={"match_id": str})
dl = pd.read_csv(DATA / "pak_deliveries.csv.gz", dtype={"match_id": str}, low_memory=False)
dl = dl[dl.match_id.str.startswith("manual_")]
changed, touched = [], set()


def ashraf_style_row(mid, inn, player):
    """One bowler's figures from the ESPN deliveries, same rules as the Cricsheet build (byes / leg byes are not charged to the bowler)."""
    y = dl[(dl.match_id == mid) & (dl.innings_no == inn) & (dl.bowler == player)].copy()
    y["br"] = y.runs_total - np.where(y.extras_type.isin(["byes", "legbyes"]), y.runs_extras, 0)
    balls = int(y.is_legal.sum()); runs = int(y.br.sum()); w = int(y.bowler_wicket.sum())
    mdn = sum(1 for _, o in y.groupby("over") if o.is_legal.sum() == 6 and o.br.sum() == 0)
    return dict(balls=balls, overs=float(f"{balls // 6}.{balls % 6}"), maidens=mdn, runs_conceded=runs, wickets=w,
                dot_balls=int(((y.is_legal == 1) & (y.runs_batter == 0)).sum()), economy=round(6 * runs / balls, 2) if balls else np.nan,
                wides=int((y.extras_type == "wides").sum()), noballs=int((y.extras_type == "noballs").sum()),
                fours_conceded=int(y.is_four.sum()), sixes_conceded=int(y.is_six.sum()), is_five_wkts=w >= 5)


for r in fixes.itertuples():
    t = tabs[r.table]; sel = t.player == r.player
    if "match_id" in t and pd.notna(r.match_id): sel &= t.match_id == r.match_id
    if "innings_no" in t and pd.notna(r.innings): sel &= t.innings_no == r.innings
    if r.field == "__row__":
        if sel.any(): continue
        fig = ashraf_style_row(r.match_id, r.innings, r.player)
        old = t[(t.match_id == r.match_id) & (t.innings_no == r.innings)]
        ids = pd.concat([tabs["opp_batting"][tabs["opp_batting"].match_id == r.match_id], t]).dropna(subset=["cricinfo_id"]).drop_duplicates("player").set_index("player").cricinfo_id
        row = {**{c: old.iloc[0][c] for c in ("match_id", "date", "year", "format", "opponent", "innings_no")}, "player": r.player, "player_id": np.nan, "cricinfo_id": ids.get(r.player, np.nan), **fig}
        t = pd.concat([t, pd.DataFrame([row])[t.columns]], ignore_index=True)
        # keep the innings in bowling order (first delivery bowled), rows of other innings untouched
        first = dl[(dl.match_id == r.match_id) & (dl.innings_no == r.innings)].drop_duplicates("bowler").reset_index(drop=True).reset_index().set_index("bowler")["index"]
        blk = t[(t.match_id == r.match_id) & (t.innings_no == r.innings)]; pos = blk.index.min()
        blk = blk.assign(_o=blk.player.map(first).fillna(99)).sort_values("_o", kind="stable").drop(columns="_o")
        t = pd.concat([t.loc[:pos - 1][~t.loc[:pos - 1].index.isin(blk.index)], blk, t.loc[pos:][~t.loc[pos:].index.isin(blk.index)]], ignore_index=True)
        tabs[r.table] = t; touched.add(r.table)
        changed.append(dict(table=r.table, match_id=r.match_id, innings=r.innings, player=r.player, field="row added", before="", after=f"{fig['overs']}-{fig['maidens']}-{fig['runs_conceded']}-{fig['wickets']}"))
        continue
    assert sel.sum() == 1, f"{r.table} {r.match_id} inn{r.innings} {r.player}: {sel.sum()} rows"
    i = t.index[sel][0]; new = float(r.after)
    if r.field == "cricinfo_id":
        if pd.isna(t.at[i, "cricinfo_id"]) or float(t.at[i, "cricinfo_id"]) != new:
            changed.append(dict(table=r.table, match_id=r.match_id, innings=r.innings, player=r.player, field="cricinfo_id", before=t.at[i, "cricinfo_id"], after=int(new)))
            t.at[i, "cricinfo_id"] = int(new) if r.table in ID_TABLES else new; touched.add(r.table)
            if r.table == "opp_players" and pd.isna(t.at[i, "cricinfo_url"]): t.at[i, "cricinfo_url"] = f"https://www.espncricinfo.com/cricketers/{int(new)}"
        continue
    if pd.isna(t.at[i, r.field]) or float(t.at[i, r.field]) != new:
        changed.append(dict(table=r.table, match_id=r.match_id, innings=r.innings, player=r.player, field=r.field, before=t.at[i, r.field], after=r.after))
        t.at[i, r.field] = type(t.at[i, r.field])(new) if not pd.isna(t.at[i, r.field]) else new; touched.add(r.table)

# recompute dependants of changed cells
for name in ("pak_batting", "opp_batting"):
    t = tabs[name]; ok = t.balls.fillna(0) > 0
    sr = (100 * t.runs / t.balls).round(2)
    d = ok & (t.strike_rate.round(2) != sr)
    d &= t.match_id.str.startswith("manual_")
    for i in t.index[d]: changed.append(dict(table=name, match_id=t.at[i, "match_id"], innings=t.at[i, "innings_no"], player=t.at[i, "player"], field="strike_rate", before=t.at[i, "strike_rate"], after=sr[i]))
    t.loc[d, "strike_rate"] = sr[d]
for name in ("pak_bowling", "opp_bowling"):
    t = tabs[name]; ok = (t.balls > 0) & t.match_id.str.startswith("manual_")
    ov = pd.Series([float(f"{int(b) // 6}.{int(b) % 6}") if b == b else np.nan for b in t.balls], index=t.index); ec = (6 * t.runs_conceded / t.balls).round(2)
    for col, v in (("overs", ov), ("economy", ec)):
        d = ok & (t[col].round(2) != v)
        for i in t.index[d]: changed.append(dict(table=name, match_id=t.at[i, "match_id"], innings=t.at[i, "innings_no"], player=t.at[i, "player"], field=col, before=t.at[i, col], after=v[i]))
        t.loc[d, col] = v[d]
for n, t in tabs.items():
    if n in ID_TABLES and n not in touched: continue
    t.to_csv(DATA / f"{n}.csv", index=False)

# match-level columns built from the bowling / batting rows
m = rd("pak_matches"); pw, ow = tabs["pak_bowling"], tabs["opp_bowling"]
for mid in sorted(set(fixes[fixes.field != "cricinfo_id"].match_id)):
    b = pw[pw.match_id == mid]; o = ow[ow.match_id == mid].sort_values(["wickets", "runs_conceded"], ascending=[False, True])
    new = dict(pak_wides_bowled=int(b.wides.sum()), pak_noballs_bowled=int(b.noballs.sum()), pak_fours_conceded=int(b.fours_conceded.sum()), pak_sixes_conceded=int(b.sixes_conceded.sum()),
               opp_best_bowler=o.iloc[0].player, opp_best_bowling=f"{int(o.iloc[0].wickets)}/{int(o.iloc[0].runs_conceded)}")
    for k, v in new.items():
        cur = m.loc[m.match_id == mid, k].iloc[0]
        if cur != v: changed.append(dict(table="pak_matches", match_id=mid, innings="", player="", field=k, before=cur, after=v)); m.loc[m.match_id == mid, k] = v
m.to_csv(DATA / "pak_matches.csv", index=False)

log = ROOT / "docs" / "cricinfo_audit_applied.csv"
if changed: pd.DataFrame(changed).to_csv(log, index=False)
print(f"{len(changed)} changes this run" + ("" if changed else " (already applied; log left as it was)"))
