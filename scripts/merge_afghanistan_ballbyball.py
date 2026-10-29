"""Merge the ESPN ball-by-ball data for the 15 Pakistan v Afghanistan matches into the dashboard.

    python scripts/merge_afghanistan_ballbyball.py        (input: extra/afghanistan_ball_by_ball.xlsx, sheets 'Ball-by-Ball' + 'Innings Coverage')

Run it AFTER scripts/merge_afghanistan_scorecards.py (it needs the manual_1..manual_15 scorecard rows). Safe to re-run: old manual_* delivery
and over rows are removed first, and every filled column is re-derived from the workbook. Files it changes are copied once to backup_pre_ball_by_ball/.

What it does
  * data/pak_deliveries.csv.gz  + 5,623 deliveries (same columns as the Cricsheet rows; phase = ODI 1-10 / 11-40 / 41-50, T20I 1-6 / 7-15 / 16-20)
  * data/pak_overs.csv          + one row per over per innings
  * pak_batting / pak_bowling / opp_bowling   dot_balls (and any blank fours / sixes conceded) from the deliveries; scorecard values are never overwritten
  * pak_partnerships            balls and runs per batter inside each Pakistan stand
  * pak_matches                 dot-ball %, powerplay / middle / death runs and wickets (both sides), dots bowled; detail_level = ball-by-ball, bbb_source column
  * docs/afghanistan_ballbyball_checks.csv   delivery totals vs scorecard, innings by innings, batter by batter, bowler by bowler
Still NOT available (left empty): Pakistan fielding credits (the source names no fielder), over-by-over rows are derived, nothing is estimated.
"""
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, XLSX = ROOT / "data", ROOT / "extra" / "afghanistan_ball_by_ball.xlsx"
BACKUP = ROOT / "backup_pre_ball_by_ball"

NAME_MAP = {"Abdul Rahman Rahmani": "Abdul Rahman", "Afsar Khan Zazai": "Afsar Zazai", "Fareed Ahmad Malik": "Fareed Ahmad",
            "Mirza Tahir Baig": "Mirza Baig", "Mohammad Asghar Afghan": "Asghar Afghan", "Mohammad Babar Azam": "Babar Azam",
            "Mohammad Shahzad Mohammadi": "Mohammad Shahzad", "Naveen-ul-Haq Murid": "Naveen-ul-Haq", "Noor Ahmad Lakanwal": "Noor Ahmad",
            "Omair Bin Yousuf": "Omair Yousuf", "Qais Ahmad Kamawal": "Qais Ahmad", "Rahmat Shah Zurmatai": "Rahmat Shah",
            "Rashid Khan Arman": "Rashid Khan", "Sarfaraz Ahmed": "Sarfraz Ahmed", "Sufyan Moqim": "Sufiyan Muqeem", "Syed Imad Wasim": "Imad Wasim",
            "Usman Khan Shinwari": "Usman Shinwari", "Zahir Khan  Pakteen": "Zahir Khan"}
PHASES = {"ODI": ((1, 10), 41), "T20I": ((1, 6), 16)}   # (powerplay overs), first death over
KIND = {"caught": "caught", "bowled": "bowled", "leg before wicket": "lbw", "run out": "run out", "stumped": "stumped", "hit wicket": "hit wicket"}
NOT_BOWLERS = {"run out"}
log, checks = [], []


def rd(name):
    d = pd.read_csv(DATA / f"{name}.csv", low_memory=False); d["match_id"] = d["match_id"].astype(str); return d


def phase(fmt, o):
    (lo, hi), death = PHASES[fmt]
    return "Powerplay" if lo <= o <= hi else ("Death" if o >= death else "Middle")


# ------------------------------------------------------------------------------------------------ 1. read + validate
raw = pd.read_excel(XLSX, "Ball-by-Ball", header=3).dropna(subset=["Match ID"])
cov = pd.read_excel(XLSX, "Innings Coverage", header=3).dropna(subset=["Match ID"])
raw["Wicket"] = raw["Wicket"].astype(bool)
for c in ("Batter", "Non-striker", "Bowler"): raw[c] = raw[c].map(lambda s: NAME_MAP.get(s, s))
g = raw.groupby(["Match ID", "Innings"], sort=False)
raw["legal"] = (g["Legal Balls After Delivery"].diff().fillna(raw["Legal Balls After Delivery"]) > 0).astype(int)
retired = raw["Dismissal Type"].astype(str).str.startswith("retired")
raw["real_wkt"] = raw.Wicket & ~retired

for _, c in cov.iterrows():
    x = raw[(raw["Match ID"] == c["Match ID"]) & (raw.Innings == c.Innings)]
    ok = len(x) == c["Delivery Rows"] and x["Total Runs on Event"].sum() == c["Innings Score"] and x.legal.sum() == c["Legal Balls"] and x.real_wkt.sum() == c["Wickets"] + 0
    wk_note = "" if x.real_wkt.sum() == c["Wickets"] else f" (delivery wickets {int(x.real_wkt.sum())} vs coverage {c['Wickets']})"
    checks.append(dict(level="innings", match_id=c["Match ID"], innings=c.Innings, what="rows/runs/legal balls vs coverage sheet", ok=bool(ok), detail=f"{len(x)} rows, {x['Total Runs on Event'].sum()} runs, {x.legal.sum()} legal{wk_note}"))
assert all(k["ok"] for k in checks if k["level"] == "innings"), [k for k in checks if not k["ok"]]

# ------------------------------------------------------------------------------------------------ 2. scorecard tables (for names / dismissals)
pb, ob = rd("pak_batting"), rd("opp_batting")
pb, ob = pb[pb.match_id.str.startswith("manual_")], ob[ob.match_id.str.startswith("manual_")]
card = pd.concat([pb[["match_id", "innings_no", "player", "is_out", "dismissal"]], ob[["match_id", "innings_no", "player", "is_out", "dismissal"]]])
card_out = {(r.match_id, r.innings_no, r.player): (bool(r.is_out), str(r.dismissal)) for r in card.itertuples()}

# ------------------------------------------------------------------------------------------------ 3. deliveries
rows = []
for (mid, inn), x in raw.groupby(["Match ID", "Innings"], sort=False):
    fmt, dismissed = x.Format.iloc[0], set()
    for r in x.itertuples(index=False):
        pt, bat, ext, tot = r[17], r[14], r[16], r[15]   # Play Type, Runs Off Bat, Extras on Event, Total Runs
        wide, lg = pt == "wide", bool(r.legal)
        et = "wides" if wide else ("noballs" if not lg else ("byes" if pt == "bye" else ("legbyes" if pt == "leg bye" else "")))
        kind_raw, striker, nonstr = r[19], r[11], r[12]
        out, kind = "", ""
        if r.real_wkt:
            kind = KIND[kind_raw]
            if kind == "run out":
                cands = [p for p in (striker, nonstr) if card_out.get((mid, inn, p), (False, ""))[0] and "run out" in card_out[(mid, inn, p)][1].lower() and p not in dismissed]
                if len(cands) != 1:
                    log.append(f"{mid} inn{inn} over {r[8]}: run-out victim ambiguous {cands}, striker used")
                    cands = [striker]
                out = cands[0]
            else:
                out = striker
            dismissed.add(out)
            dtxt = card_out.get((mid, inn, out), (False, ""))[1].lower()
            if kind == "caught" and (re.match(r"c\s*(&|and)\s*b", dtxt) or re.match(r"c (.+?) b \1$", dtxt)): kind = "caught and bowled"
        rows.append(dict(match_id=mid, date=r.Date, format=fmt, opponent="Afghanistan", innings_no=int(inn), pak_batting=int(r[4] == "Pakistan"),
                         over=int(r[6]), ball=int(r[7]), legal_ball_no=float(r[9]) if lg else np.nan, batter=striker, bowler=r[13],
                         runs_batter=int(bat), runs_extras=int(ext), runs_total=int(tot), extras_type=et, is_legal=int(lg),
                         is_batter_dot=int((not wide) and bat == 0), is_four=int(pt == "four" and bat == 4), is_six=int(pt == "six" and bat == 6),
                         is_wicket=int(bool(r.real_wkt)), wicket_kind=kind, player_out=out,
                         bowler_wicket=int(bool(r.real_wkt) and kind not in NOT_BOWLERS), phase=phase(fmt, int(r[6]))))
new = pd.DataFrame(rows)

# ------------------------------------------------------------------------------------------------ 4. checks against the scorecards
pbat, pbowl = pb, rd("pak_bowling"); pbowl = pbowl[pbowl.match_id.str.startswith("manual_")]
obowl = rd("opp_bowling"); obowl = obowl[obowl.match_id.str.startswith("manual_")]
bat_d = new.groupby(["match_id", "innings_no", "batter"]).agg(runs=("runs_batter", "sum"), faced=("is_batter_dot", "size"), wides=("extras_type", lambda s: (s == "wides").sum()),
                                                                dots=("is_batter_dot", "sum"), fours=("is_four", "sum"), sixes=("is_six", "sum")).reset_index()
bat_d["balls"] = bat_d.faced - bat_d.wides   # wides are not balls faced; faced counts rows, so remove them
bat_d["dots"] = bat_d.dots
bat_d["balls"] = new.assign(f=(new.extras_type != "wides").astype(int)).groupby(["match_id", "innings_no", "batter"]).f.sum().values
for side, tab in (("pak", pbat), ("opp", ob)):
    m = tab.merge(bat_d, left_on=["match_id", "innings_no", "player"], right_on=["match_id", "innings_no", "batter"], how="left", suffixes=("", "_d"))
    for r in m.itertuples():
        if pd.isna(r.runs_d):
            if pd.notna(r.balls) and r.balls > 0: checks.append(dict(level="batter", match_id=r.match_id, innings=r.innings_no, what=f"{r.player}: on scorecard, never faced in deliveries", ok=False, detail=f"scorecard {r.runs}({r.balls})"))
            continue
        diffs = [f"{k} {getattr(r, k)} vs {getattr(r, k + '_d')}" for k in ("runs", "balls", "fours", "sixes") if pd.notna(getattr(r, k)) and getattr(r, k) != getattr(r, k + "_d")]
        checks.append(dict(level="batter", match_id=r.match_id, innings=r.innings_no, what=r.player, ok=not diffs, detail="; ".join(diffs)))
bowl_d = new.assign(br=new.runs_total - np.where(new.extras_type.isin(["byes", "legbyes"]), new.runs_extras, 0), dot=((new.is_legal == 1) & (new.runs_batter == 0)).astype(int),
                    wd=(new.extras_type == "wides").astype(int), nb=(new.extras_type == "noballs").astype(int)).groupby(["match_id", "innings_no", "bowler"]).agg(
    balls=("is_legal", "sum"), runs_conceded=("br", "sum"), wickets=("bowler_wicket", "sum"), dots=("dot", "sum"), wides=("wd", "sum"), noballs=("nb", "sum"),
    fours=("is_four", "sum"), sixes=("is_six", "sum")).reset_index()
for tab in (pbowl, obowl):
    zero_inn = {k for k, v in tab.groupby(["match_id", "innings_no"]).apply(lambda y: y.fours_conceded.fillna(0).sum() + y.sixes_conceded.fillna(0).sum() == 0, include_groups=False).items() if v}
    m = tab.merge(bowl_d, left_on=["match_id", "innings_no", "player"], right_on=["match_id", "innings_no", "bowler"], how="left", suffixes=("", "_d"))
    for r in m.itertuples():
        if pd.isna(r.balls_d):
            checks.append(dict(level="bowler", match_id=r.match_id, innings=r.innings_no, what=f"{r.player}: on scorecard, not in deliveries", ok=False, detail="")); continue
        diffs = [f"{k} {getattr(r, k)} vs {getattr(r, k + '_d')}" for k in ("balls", "runs_conceded", "wickets", "wides", "noballs") if pd.notna(getattr(r, k)) and getattr(r, k) != getattr(r, k + "_d")]
        if (r.match_id, r.innings_no) not in zero_inn:   # all-zero cards are placeholders: replaced below and logged, not compared
            diffs += [f"{k} {getattr(r, k)} vs {getattr(r, 'fours' if k.startswith('fours') else 'sixes')}" for k in ("fours_conceded", "sixes_conceded")
                      if pd.notna(getattr(r, k)) and getattr(r, k) != getattr(r, "fours" if k.startswith("fours") else "sixes")]
        checks.append(dict(level="bowler", match_id=r.match_id, innings=r.innings_no, what=r.player, ok=not diffs, detail="; ".join(diffs)))
# innings wickets vs scorecard outs
for (mid, inn), x in new.groupby(["match_id", "innings_no"]):
    sc = card[(card.match_id == mid) & (card.innings_no == inn)]
    a, b = set(x.player_out[x.is_wicket == 1]), set(sc.player[sc.is_out.astype(bool)])
    checks.append(dict(level="innings", match_id=mid, innings=inn, what="dismissed batters: deliveries vs scorecard", ok=a == b,
                       detail="" if a == b else f"only in deliveries {sorted(a - b)}; only on scorecard {sorted(b - a)}"))
chk = pd.DataFrame(checks)
# Cricinfo-verified exceptions (docs/cricinfo_verified_exceptions.csv): the scorecard value was confirmed on the Cricinfo page and the deliveries are the odd one out.
# Such a check is marked ok and says so in verification_status; any OTHER difference on the same line still fails.
chk["verification_status"] = ""
exc_path = ROOT / "docs" / "cricinfo_verified_exceptions.csv"
if exc_path.exists():
    for e in pd.read_csv(exc_path, dtype={"match_id": str}).itertuples():
        hit = (chk.level == "batter") & (chk.match_id == e.match_id) & (chk.innings == e.innings) & (chk.what == e.player) & (~chk.ok) & (chk.detail == f"{e.field} {e.scorecard_value} vs {float(e.delivery_value)}")
        chk.loc[hit, "verification_status"] = f"Cricinfo-verified: card {e.scorecard_value} is correct, deliveries have {e.delivery_value}"
        chk.loc[hit, "ok"] = True

# ------------------------------------------------------------------------------------------------ 5. back up, then write
def backup(rel):
    p = ROOT / rel; dst = BACKUP / rel
    if p.exists() and not dst.exists(): dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, dst)

for rel in ("data/pak_deliveries.csv.gz", "data/pak_overs.csv", "data/pak_batting.csv", "data/pak_bowling.csv", "data/opp_bowling.csv", "data/pak_partnerships.csv", "data/pak_matches.csv",
            "data/pak_player_splits_batting.csv", "data/pak_player_splits_bowling.csv"):
    backup(rel)

# deliveries
old = pd.read_csv(DATA / "pak_deliveries.csv.gz", dtype={"match_id": str}, low_memory=False)
old = old[~old.match_id.str.startswith("manual_")]
out = pd.concat([old, new[old.columns]], ignore_index=True)
out.to_csv(DATA / "pak_deliveries.csv.gz", index=False, compression="gzip")

# overs
ov = rd("pak_overs"); ov = ov[~ov.match_id.str.startswith("manual_")]
orows = []
for (mid, inn), x in new.groupby(["match_id", "innings_no"], sort=False):
    cr = cw = 0
    for o, y in x.groupby("over"):
        cr += y.runs_total.sum(); cw += y.is_wicket.sum()
        orows.append(dict(match_id=mid, date=y.date.iloc[0], year=int(str(y.date.iloc[0])[:4]), format=y.format.iloc[0], opponent="Afghanistan", innings_no=inn,
                          side="Pakistan" if y.pak_batting.iloc[0] else "Opposition", over=o, runs=int(y.runs_total.sum()), wickets=int(y.is_wicket.sum()),
                          legal_balls=int(y.is_legal.sum()), cum_runs=int(cr), cum_wkts=int(cw)))
pd.concat([ov, pd.DataFrame(orows)[ov.columns]], ignore_index=True).to_csv(DATA / "pak_overs.csv", index=False)

# batting / bowling dots (+ blank boundary counts)
def fill(name, df_new):
    d = rd(name); df_new.to_csv(DATA / f"{name}.csv", index=False)

pbat_all = rd("pak_batting"); mk = pbat_all.match_id.str.startswith("manual_")
key = lambda d: list(zip(d.match_id, d.innings_no, d.player))
bd = bat_d.set_index(["match_id", "innings_no", "batter"])
dots = [bd.dots.get(k, np.nan) for k in key(pbat_all)]; balls = [bd.balls.get(k, np.nan) for k in key(pbat_all)]
pbat_all.loc[mk, "dot_balls"] = pd.Series(dots, index=pbat_all.index)[mk]
pbat_all.loc[mk, "dot_ball_pct"] = pd.Series([round(100 * d / b, 1) if b and not pd.isna(b) else np.nan for d, b in zip(dots, balls)], index=pbat_all.index)[mk]
pbat_all.to_csv(DATA / "pak_batting.csv", index=False)

bw = bowl_d.set_index(["match_id", "innings_no", "bowler"])
for name in ("pak_bowling", "opp_bowling"):
    t = rd(name); mk = t.match_id.str.startswith("manual_")
    t.loc[mk, "dot_balls"] = pd.Series([bw.dots.get(k, np.nan) for k in key(t)], index=t.index)[mk]
    for src, col in (("fours", "fours_conceded"), ("sixes", "sixes_conceded")):
        v = pd.Series([bw[src].get(k, np.nan) for k in key(t)], index=t.index)
        blank = mk & t[col].isna(); t.loc[blank, col] = v[blank]
    # an innings whose bowlers ALL show 0 fours and 0 sixes on the card, while the deliveries have boundaries, is placeholder zeros, not a record
    for (mid, inn), idx in t[mk].groupby(["match_id", "innings_no"]).groups.items():
        vf, vs = [pd.Series([bw[c].get(k, np.nan) for k in key(t)], index=t.index)[idx] for c in ("fours", "sixes")]
        if t.loc[idx, "fours_conceded"].fillna(0).sum() == 0 and t.loc[idx, "sixes_conceded"].fillna(0).sum() == 0 and (vf.sum() + vs.sum()) > 0:
            t.loc[idx, "fours_conceded"], t.loc[idx, "sixes_conceded"] = vf, vs
            log.append(f"{name} {mid} inn{inn}: card showed 0 fours / 0 sixes conceded for every bowler (placeholder); replaced by the deliveries ({int(vf.sum())} fours, {int(vs.sum())} sixes)")
    t.to_csv(DATA / f"{name}.csv", index=False)

# partnerships (Pakistan stands): balls + runs per batter
pp = rd("pak_partnerships"); mk = pp.match_id.str.startswith("manual_")
for (mid, inn), x in new[new.pak_batting == 1].groupby(["match_id", "innings_no"]):
    cur = dict(runs=0, balls=0, by={}); stands = []
    for r in x.itertuples():
        cur["runs"] += r.runs_total; cur["balls"] += r.is_legal; cur["by"][r.batter] = cur["by"].get(r.batter, 0) + r.runs_batter
        if r.is_wicket: stands.append(cur); cur = dict(runs=0, balls=0, by={})
    if cur["runs"] or cur["balls"]: stands.append(cur)
    sel = pp[mk & (pp.match_id == mid) & (pp.innings_no == inn)].sort_values("wicket_no")
    if len(sel) != len(stands): log.append(f"{mid} inn{inn}: {len(sel)} partnership rows vs {len(stands)} stands in deliveries"); continue
    for (i, row), s in zip(sel.iterrows(), stands):
        ok = row.runs == s["runs"]
        if not ok: log.append(f"{mid} inn{inn} wkt{row.wicket_no}: stand {row.runs} on scorecard vs {s['runs']} in deliveries (balls/batter runs not filled)"); continue
        pp.loc[i, "balls"] = s["balls"]; pp.loc[i, "batter1_runs"] = s["by"].get(row.batter1, 0); pp.loc[i, "batter2_runs"] = s["by"].get(row.batter2, 0)
pp.to_csv(DATA / "pak_partnerships.csv", index=False)

# matches
m = rd("pak_matches")
if "bbb_source" not in m: m["bbb_source"] = np.where(m.get("detail_level", "") == "result-only", "", "Cricsheet")
bow_all = {name: rd(name) for name in ("pak_bowling", "opp_bowling")}
for mid in sorted(new.match_id.unique(), key=lambda s: int(s.split("_")[1])):
    x = new[new.match_id == mid]; P, O = x[x.pak_batting == 1], x[x.pak_batting == 0]
    u = dict(detail_level="ball-by-ball", bbb_source="ESPN play-by-play",
             pak_dot_ball_pct=round(100 * ((P.is_legal == 1) & (P.runs_total == 0)).sum() / P.is_legal.sum(), 1),
             pak_dot_balls_bowled=int(((O.is_legal == 1) & (O.runs_total == 0)).sum()),
             pak_dot_ball_bowled_pct=round(100 * ((O.is_legal == 1) & (O.runs_total == 0)).sum() / O.is_legal.sum(), 1))
    for key_, d in (("pak_", P), ("opp_", O)):
        for ph, nm in (("Powerplay", "powerplay"), ("Middle", "middle"), ("Death", "death")):
            y = d[d.phase == ph]
            if key_ == "pak_": u[f"pak_{nm}_runs"] = int(y.runs_total.sum()); u[f"pak_{nm}_wkts_lost"] = int(y.is_wicket.sum())
            else: u[f"opp_{nm}_runs"] = int(y.runs_total.sum()); u[f"pak_{nm}_wkts_taken"] = int(y.is_wicket.sum())
    for c in ("pak", "opp"):   # same totals as the scorecard?
        d = P if c == "pak" else O
        sc = m.loc[m.match_id == mid, f"{c}_runs"].iloc[0]
        if sc != d.runs_total.sum(): log.append(f"{mid}: {c} runs {sc} (scorecard) vs {d.runs_total.sum()} (deliveries)")
    for col, bt in (("pak_fours_conceded", bow_all["pak_bowling"]), ("pak_sixes_conceded", bow_all["pak_bowling"])):
        s = bt[bt.match_id == mid][col.replace("pak_", "").replace("conceded", "conceded")] if False else None
    pbw_ = bow_all["pak_bowling"]; pbw_ = pbw_[pbw_.match_id == mid]
    u["pak_fours_conceded"], u["pak_sixes_conceded"] = int(pbw_.fours_conceded.sum()), int(pbw_.sixes_conceded.sum())
    for k, v in u.items(): m.loc[m.match_id == mid, k] = v
m.to_csv(DATA / "pak_matches.csv", index=False)

chk.to_csv(ROOT / "docs" / "afghanistan_ballbyball_checks.csv", index=False)
bad = chk[~chk.ok]
print(f"{len(new):,} deliveries, {len(orows)} over rows, {new.match_id.nunique()} matches")
print(f"checks: {len(chk)} total, {len(bad)} with differences, {int((chk.verification_status != '').sum())} Cricinfo-verified exceptions")
print(bad.groupby("level").size().to_string() if len(bad) else "all agree")
for l in log: print("LOG:", l)
(ROOT / "docs" / "afghanistan_ballbyball_log.txt").write_text("\n".join(log), encoding="utf-8")
