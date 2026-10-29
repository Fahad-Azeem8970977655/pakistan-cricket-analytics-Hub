"""Merge the 15 hand-collected Pakistan v Afghanistan scorecards into the dashboard data.

    python scripts/merge_afghanistan_scorecards.py            (input: extra/afghanistan_scorecards.xlsx)

Run order after a data refresh:
    scripts/merge_manual_into_data.py -> scripts/merge_afghanistan_scorecards.py -> build_captains.py -> build_coaches.py
    -> scripts/build_player_splits.py

What it does (safe to re-run: old manual_1..manual_15 rows are removed first)
  * data/pak_matches.csv    fills XI, umpires, referee, player of the match, scorecard-derived totals, captain (confidence 'scorecard'),
                            batting order, margin type/value; adds detail_level + scorecard_source columns
  * data/pak_batting, pak_bowling, pak_partnerships, pak_appearances, opp_batting, opp_bowling, opp_fielding, opp_players, pak_players
  * eras/captains_scorecard.csv   recorded captains, read by build_captains.py
Not available from the scorecards, so left EMPTY (never estimated): dot balls, over-by-over runs, powerplay / middle / death splits,
batter-by-batter runs inside a partnership, balls per partnership, Pakistan fielding credits (the Afghan batting card names no fielders).
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
XLSX = ROOT / "extra" / "afghanistan_scorecards.xlsx"

PAK_MAP = {"Agha Salman": "Salman Ali Agha", "Salman Agha": "Salman Ali Agha", "Sarfaraz Ahmed": "Sarfraz Ahmed",
           "Mohammad Wasim Jr": "Mohammad Wasim", "Sufyan Moqim": "Sufiyan Muqeem", "Mirza Tahir Baig": "Mirza Baig"}
AFG_MAP = {"Fareed Ahmad Malik": "Fareed Ahmad", "Shahidullah": "Shahidullah Kamal"}
SUFFIX = re.compile(r"\s*\((?:c|wk|c\s*&\s*wk|wk\s*&\s*c|pakistan|afghanistan)\)\s*", re.I)
INT_COLS = ("dot_balls", "fours_conceded", "sixes_conceded", "balls", "batter1_runs", "batter2_runs", "cricinfo_id")
PLAIN = {"caught", "bowled", "lbw", "run out", "stumped", "caught and bowled", "hit wicket"}


# ---------------------------------------------------------------- reading the workbook
x = pd.ExcelFile(XLSX)


def sheet(name):
    raw = x.parse(name, header=None)
    h = next(i for i in range(min(12, len(raw))) if "match_id" in raw.iloc[i].astype(str).tolist())
    return x.parse(name, header=h).dropna(how="all")


def clean_name(s, side):
    if not isinstance(s, str): return s
    s = SUFFIX.sub("", s).strip()
    mp = PAK_MAP if side == "pak" else AFG_MAP
    return mp.get(s, s)


def clean_text(s, side):
    """Apply the name map inside free text such as 'c Mohammad Nabi b Rashid Khan' or 'A, B'."""
    if not isinstance(s, str): return s
    s = SUFFIX.sub(" ", s)
    mp = PAK_MAP if side == "pak" else AFG_MAP
    for k, v in mp.items(): s = re.sub(rf"\b{re.escape(k)}\b", v, s)
    return re.sub(r"\s+", " ", s).strip()


def clean_list(s, side):
    return ", ".join(clean_name(p, side) for p in str(s).split(",") if p.strip())


def o2b(o):
    o = float(o); i = int(o); return i * 6 + int(round((o - i) * 10))


def b2o(b): return float(f"{b // 6}.{b % 6}")


def tot(s):
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", str(s)); return (int(m[1]), int(m[2])) if m else (None, None)


md, pb, ob = sheet("Match Details"), sheet("Pakistan Batting"), sheet("Opposition Batting")
pw, ow, fw = sheet("Pakistan Bowling"), sheet("Opposition Bowling"), sheet("Fall of Wickets")
src = sheet("Sources")
# input typo found while validating: one Afghan row of manual_11 has innings_no 7 (the innings is 2)
ob.loc[(ob.match_id == "manual_11") & (ob.innings_no == 7), "innings_no"] = 2
ids = list(md.match_id)

# ---------------------------------------------------------------- existing data
def rd(name, **k):
    d = pd.read_csv(DATA / f"{name}.csv", dtype={"match_id": str}, low_memory=False, **k)
    d.attrs["orig"] = {c: str(t) for c, t in d.dtypes.items()}
    return d


def wr(df, name):
    orig = df.attrs.get("orig", {})
    for c, t in orig.items():
        if c in df and t.startswith("int") and df[c].dtype.kind == "f" and df[c].dropna().mod(1).eq(0).all():
            df[c] = df[c].astype("Int64")
    for c in INT_COLS:                       # whole-number columns that gained empty cells: keep writing 88, not 88.0
        if c in df and df[c].dtype.kind == "f" and df[c].dropna().mod(1).eq(0).all(): df[c] = df[c].astype("Int64")
    crlf = b"\r\n" in (DATA / f"{name}.csv").read_bytes()[:5000]
    df.to_csv(DATA / f"{name}.csv", index=False, lineterminator="\r\n" if crlf else "\n")


m = rd("pak_matches")
for c, v in (("detail_level", None), ("scorecard_source", None)):
    if c not in m: m[c] = v
m["detail_level"] = np.where(m.data_source.eq("manual"), "result-only", "ball-by-ball")
pp = rd("pak_players"); pid_of = dict(zip(pp.player, pp.player_id))
pak_names_seen = set()


def drop_old(df): return df[~df.match_id.isin(ids)].copy()


# ---------------------------------------------------------------- per-match build
bat_rows, bowl_rows, part_rows, app_rows = [], [], [], []
obat_rows, obowl_rows, ofield_rows = [], [], []
log, summary = [], {}
cricinfo = {}
# Cricinfo IDs: the workbook gives the same player different IDs in different matches (older rows carry superseded IDs).
# Use an ID only when most of that player's matches agree; ties stay blank. Everything disputed is written to extra/cricinfo_id_conflicts.csv
from collections import defaultdict
_cnt = defaultdict(lambda: defaultdict(set))
for d_ in (ob, ow):
    for r in d_.dropna(subset=["cricinfo_id"]).itertuples():
        _cnt[clean_name(r.player, "afg")][int(r.cricinfo_id)].add(r.match_id)
conf_rows = []
for nm_, ids_ in sorted(_cnt.items()):
    rk = sorted(ids_.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    if len(rk) == 1 or len(rk[0][1]) > len(rk[1][1]): cricinfo[nm_] = rk[0][0]
    if len(rk) > 1:
        conf_rows.append(dict(player=nm_, used_id=cricinfo.get(nm_, ""), status="majority" if nm_ in cricinfo else "tie - left blank",
                              ids_found="; ".join(f"{i} ({len(ms)} matches: {', '.join(sorted(ms, key=lambda t: int(t.split('_')[1])))})" for i, ms in rk)))
pd.DataFrame(conf_rows).to_csv(ROOT / "extra" / "cricinfo_id_conflicts.csv", index=False)
log.append(f"Cricinfo IDs: {len(conf_rows)} players have conflicting IDs in the workbook ({sum(r['status'] != 'majority' for r in conf_rows)} left blank); see extra/cricinfo_id_conflicts.csv")


def parse_dismissal(dis, by, fld):
    """-> (kind, dismissed_by, fielders) in the dashboard's Pakistan-batting convention."""
    dis = clean_text(dis, "afg") if isinstance(dis, str) else dis
    by, fld = clean_name(by, "afg"), clean_list(fld, "afg") if isinstance(fld, str) else None
    if not isinstance(dis, str) or dis.lower() in ("not out", "did not bat"): return None, None, None
    d = dis.strip(); dl = d.lower()
    if dl in PLAIN: return dl, (by if isinstance(by, str) else None), (fld or None)
    if dl.startswith("retired"): return "retired hurt", None, None
    if mm := re.match(r"c & b (.+)$", d): return "caught and bowled", mm[1], None
    if mm := re.match(r"c (.+) b (.+)$", d): return "caught", mm[2], mm[1]
    if mm := re.match(r"st (.+) b (.+)$", d): return "stumped", mm[2], mm[1]
    if mm := re.match(r"lbw b (.+)$", d): return "lbw", mm[1], None
    if mm := re.match(r"hit wicket b (.+)$", d): return "hit wicket", mm[1], None
    if mm := re.match(r"b (.+)$", d): return "bowled", mm[1], None
    if mm := re.match(r"run out \((.+)\)$", d): return "run out", None, ", ".join(p.strip() for p in mm[1].split("/"))
    raise ValueError(f"unparsed dismissal: {dis!r}")


for mid in ids:
    r = m.loc[m.match_id == mid].iloc[0]
    wr_ = md[md.match_id == mid].iloc[0]
    assert str(wr_["date"])[:10] == r.date and wr_["format"] == r["format"], f"{mid}: date/format differ from pak_matches"
    P = pb[(pb.match_id == mid) & (pb.dismissal.astype(str) != "did not bat")].copy()
    O = ob[ob.match_id == mid].copy(); PW = pw[pw.match_id == mid].copy(); OW = ow[ow.match_id == mid].copy()
    pi, oi = int(P.innings_no.iloc[0]), int(O.innings_no.iloc[0])
    assert pi != oi and len(set(PW.innings_no)) == 1 and len(set(OW.innings_no)) == 1, f"{mid}: innings numbers unclear"
    if set(PW.innings_no) != {oi} or set(OW.innings_no) != {pi}:      # bowlers bowl in the OTHER side's batting innings
        log.append(f"{mid}: bowling sheets carried innings_no {sorted(set(PW.innings_no))}/{sorted(set(OW.innings_no))}; set to {oi}/{pi} to match the batting innings they bowled in")
    for d_ in (P, PW): d_["player"] = d_.player.map(lambda s: clean_name(s, "pak"))
    for d_ in (O, OW): d_["player"] = d_.player.map(lambda s: clean_name(s, "afg"))
    # ---- totals: Pakistan from the scorecard, opposition from the dataset (bowling and batting both reconcile to it)
    F = fw[(fw.match_id == mid) & (fw.innings_no == pi)].sort_values("wicket_no")
    pr, pw_ = int(P.team_total.dropna().iloc[0]), len(F)      # runs from the scorecard total, wickets = fall-of-wicket rows
    orr, ow_ = tot(r.opp_score)
    pak_score, opp_score = f"{pr}/{pw_}", r.opp_score
    p_extras = int(P.team_extras.dropna().iloc[0]); o_extras = orr - int(O.runs.sum())
    p_balls, o_balls = int(OW.overs.map(o2b).sum()), int(PW.overs.map(o2b).sum())
    assert int(P.runs.sum()) + p_extras == pr, f"{mid}: Pakistan batting does not add to {pr}"
    assert o_extras >= 0
    if pak_score != r.pak_score: log.append(f"{mid}: pak_score {r.pak_score} -> {pak_score} (scorecard)")
    # ---- batting rows
    for q in P.itertuples():
        kind, by, fld = parse_dismissal(q.dismissal, q.dismissed_by, q.fielders)
        out = bool(q.is_out) and kind != "retired hurt"
        balls = int(q.balls); runs = int(q.runs)
        bat_rows.append(dict(match_id=mid, innings_no=pi, batting_position=int(q.batting_position), player=q.player,
                             player_id=pid_of[q.player], runs=runs, balls=balls, fours=int(q.fours), sixes=int(q.sixes),
                             dot_balls=np.nan, dot_ball_pct=np.nan, strike_rate=round(100 * runs / balls, 2) if balls else 0.0,
                             is_out=out, dismissal=kind, dismissed_by=by, fielders=fld, is_fifty=50 <= runs < 100,
                             is_hundred=runs >= 100, is_duck=out and runs == 0, team_total=pr, team_extras=p_extras))
        if q.player not in pid_of: raise KeyError(q.player)
    obat = []
    for q in O.itertuples():
        runs, balls = int(q.runs), int(q.balls)
        dis = clean_text(q.dismissal, "afg") if isinstance(q.dismissal, str) else None
        out = bool(q.is_out)
        if dis and dis.lower().startswith("retired"): dis = "retired hurt" if "hurt" in dis.lower() else dis
        obat.append(dict(match_id=mid, innings_no=oi, batting_position=int(q.batting_position), player=q.player, player_id="",
                         cricinfo_id=cricinfo.get(q.player, np.nan), runs=runs, balls=balls, fours=int(q.fours), sixes=int(q.sixes),
                         strike_rate=round(100 * runs / balls, 2) if balls else 0.0, is_out=out, dismissal=dis,
                         is_fifty=50 <= runs < 100, is_hundred=runs >= 100, is_duck=out and runs == 0))
    obat_rows += obat
    # ---- bowling rows
    def bowl(df, side, innings, total):
        rows = []
        for q in df.itertuples():
            b = o2b(q.overs); runs = int(q.runs_conceded); w = int(q.wickets)
            rows.append(dict(match_id=mid, innings_no=innings, player=q.player, balls=b, overs=b2o(b), maidens=int(q.maidens),
                             runs_conceded=runs, wickets=w, dot_balls=np.nan, economy=round(6 * runs / b, 2) if b else 0.0,
                             wides=int(q.wides), noballs=int(q.noballs),
                             fours_conceded=q.fours_conceded, sixes_conceded=q.sixes_conceded, is_five_wkts=w >= 5))
        return rows
    pb_rows = bowl(PW, "pak", oi, orr); ow_rows = bowl(OW, "afg", pi, pr)
    for z in pb_rows: z["player_id"] = pid_of[z["player"]]; z["opp_innings_total"] = orr
    for z in ow_rows: z["player_id"] = ""; z["cricinfo_id"] = cricinfo.get(z["player"], np.nan)
    bowl_rows += pb_rows; obowl_rows += ow_rows
    # ---- partnerships (Pakistan innings) from fall of wickets
    # who is at the crease follows from the batting order + the batter dismissed at each wicket (nothing is guessed)
    order_ = list(P.sort_values("batting_position").player)
    crease = order_[:2]; nxt = 2; prev = 0; okc = True
    for q in F.itertuples():
        sc = int(q.score_at_fall); out_ = clean_name(q.batter_out, "pak"); part = None
        if okc and out_ in crease:
            part = [c for c in crease if c != out_]; part = part[0] if part else None
            given = clean_name(q.partner_not_out, "pak") if isinstance(q.partner_not_out, str) else None
            if given and part and given != part:     # the batting order is self-consistent for every wicket, the workbook column is not
                log.append(f"{mid}: wicket {q.wicket_no} partner: workbook says {given}, batting order says {part} (batting order used)")
            crease = [c for c in crease if c != out_] + ([order_[nxt]] if nxt < len(order_) else []); nxt += 1
        else:
            okc = False
            part = clean_name(q.partner_not_out, "pak") if isinstance(q.partner_not_out, str) else None
        part_rows.append(dict(match_id=mid, innings_no=pi, wicket_no=int(q.wicket_no), runs=sc - prev, balls=np.nan, unbroken=False,
                              batter1=out_, batter1_runs=np.nan, batter2=part, batter2_runs=np.nan)); prev = sc
    if not okc: log.append(f"{mid}: could not follow the crease from the batting order; some partners left blank")
    ends = {b.player for b in P.itertuples() if not bool(b.is_out) and str(b.dismissal).lower() not in ("retired hurt",)}
    if okc and pw_ < 10 and not set(crease) <= ends: log.append(f"{mid}: batters left at the crease {crease} differ from the not-out batters {sorted(ends)}")
    if pw_ < 10 and okc and len(crease) == 2 and pr - prev > 0:
        part_rows.append(dict(match_id=mid, innings_no=pi, wicket_no=pw_ + 1, runs=pr - prev, balls=np.nan, unbroken=True,
                              batter1=crease[0], batter1_runs=np.nan, batter2=crease[1], batter2_runs=np.nan))
    # ---- appearances / XI
    xi_p = [clean_name(s, "pak") for s in str(wr_.pak_xi).split(",") if s.strip()]
    xi_o = [clean_name(s, "afg") for s in str(wr_.opp_xi).split(",") if s.strip()]
    assert len(xi_p) == 11 and len(set(xi_p)) == 11, f"{mid}: Pakistan XI {len(xi_p)}"
    assert len(xi_o) == 11 and len(set(xi_o)) == 11, f"{mid}: Afghan XI {len(xi_o)}"
    assert set(P.player) <= set(xi_p) and set(PW.player) <= set(xi_p), f"{mid}: Pakistan scorecard names not in XI"
    extra_o = (set(O.player) | set(OW.player)) - set(xi_o)
    if extra_o: log.append(f"{mid}: Afghan players on the scorecard but not in the listed XI (replacement / substitute): {sorted(extra_o)}")
    for p_ in xi_p:
        app_rows.append(dict(match_id=mid, date=r.date, year=r.year, format=r["format"], opponent="Afghanistan", player=p_,
                             player_id=pid_of[p_], result=r.result, player_cricsheet_name=np.nan))
    # ---- opposition fielding from Pakistan batters' dismissals
    fb = [b for b in bat_rows if b["match_id"] == mid and b["is_out"]]
    need = [b for b in fb if b["dismissal"] in ("caught", "stumped", "run out")]
    miss = [b for b in need if not b["fielders"]]
    if miss:
        log.append(f"{mid}: opp_fielding skipped, {len(miss)} dismissal(s) without a named fielder")
    else:
        cnt = {}
        for b in fb:
            if b["dismissal"] == "caught and bowled":
                cnt.setdefault(b["dismissed_by"], dict(caught_and_bowled=0))["caught_and_bowled"] += 1
            elif b["dismissal"] in ("caught", "stumped"):
                for f_ in [b["fielders"]]:
                    cnt.setdefault(f_, {}); k = "catches" if b["dismissal"] == "caught" else "stumpings"; cnt[f_][k] = cnt[f_].get(k, 0) + 1
            elif b["dismissal"] == "run out":
                fl = [s.strip() for s in b["fielders"].split(",")]
                for f_ in fl:
                    cnt.setdefault(f_, {}); k = "runouts_direct" if len(fl) == 1 else "runouts_assisted"; cnt[f_][k] = cnt[f_].get(k, 0) + 1
        for nm, c in cnt.items():
            row = dict(match_id=mid, date=r.date, year=r.year, format=r["format"], opponent="Afghanistan", player=nm, player_id="",
                       cricinfo_id=cricinfo.get(nm, np.nan), substitute=nm not in xi_o, catches=0, caught_and_bowled=0, stumpings=0,
                       runouts_direct=0, runouts_assisted=0); row.update(c)
            row["total_dismissals"] = sum(row[k] for k in ("catches", "caught_and_bowled", "stumpings", "runouts_direct", "runouts_assisted"))
            ofield_rows.append(row)
    # ---- match-level fields
    pbat = P.copy(); pbw = PW; obw = OW
    best = lambda df: (df.sort_values(["wickets", "runs_conceded"], ascending=[False, True]).iloc[0])
    bp, bo = best(pbw), best(obw)
    ts_p, ts_o = pbat.sort_values("runs", ascending=False).iloc[0], O.sort_values("runs", ascending=False).iloc[0]
    pak_first = pi == 1
    margin = str(r.margin) if isinstance(r.margin, str) else ""
    mt = re.match(r"(\d+)\s*(run|wicket)", margin)
    pom = wr_.player_of_match if isinstance(wr_.player_of_match, str) else None
    pom = clean_name(pom, "pak") if pom in PAK_MAP or pom in xi_p else clean_name(pom, "afg")
    if pom and isinstance(r.player_of_match, str) and pom != r.player_of_match:
        log.append(f"{mid}: player_of_match {r.player_of_match} -> {pom} (scorecard workbook)")
    if pom is None and isinstance(r.player_of_match, str): pom = r.player_of_match
    fc = lambda s: s.sum() if s.notna().all() else np.nan
    upd = dict(pak_score=pak_score, pak_runs=pr, pak_wkts_lost=pw_, run_diff=pr - orr,
               pak_balls_faced=p_balls, pak_overs=f"{p_balls // 6}.{p_balls % 6}",
               pak_run_rate=round(6 * pr / p_balls, 2), opp_balls_faced=o_balls, opp_overs=f"{o_balls // 6}.{o_balls % 6}",
               opp_run_rate=round(6 * orr / o_balls, 2),
               pak_batting_order="Batting first" if pak_first else "Batting second", pak_chasing=not pak_first,
               pak_target_chased=np.nan if pak_first else orr + 1, opp_target_chased=(pr + 1) if pak_first else np.nan,
               pak_fours=int(pbat.fours.sum()), pak_sixes=int(pbat.sixes.sum()),
               pak_boundary_pct=round(100 * (4 * pbat.fours.sum() + 6 * pbat.sixes.sum()) / pr, 1) if pr else np.nan,
               pak_extras_received=p_extras, pak_top_scorer=ts_p.player, pak_top_score=int(ts_p.runs),
               pak_hundreds=int((pbat.runs >= 100).sum()), pak_fifties=int(pbat.runs.between(50, 99).sum()),
               pak_ducks=int(((pbat.is_out.astype(bool)) & (pbat.runs == 0)).sum()),
               pak_fours_conceded=fc(pbw.fours_conceded), pak_sixes_conceded=fc(pbw.sixes_conceded), pak_extras_conceded=o_extras,
               pak_wides_bowled=int(pbw.wides.sum()), pak_noballs_bowled=int(pbw.noballs.sum()),
               pak_best_bowler=bp.player, pak_best_bowling=f"{int(bp.wickets)}/{int(bp.runs_conceded)}",
               pak_five_wkt_hauls=int((pbw.wickets >= 5).sum()), pak_bowlers_used=len(pbw),
               opp_top_scorer=ts_o.player, opp_top_score=int(ts_o.runs), opp_best_bowler=bo.player,
               opp_best_bowling=f"{int(bo.wickets)}/{int(bo.runs_conceded)}",
               pak_xi=", ".join(xi_p), opp_xi=", ".join(xi_o), umpires=wr_.umpires if isinstance(wr_.umpires, str) else None,
               match_referee=wr_.match_referee if isinstance(wr_.match_referee, str) else None,
               player_of_match=pom, pak_pom=(pom in xi_p) if pom else np.nan,
               pak_captain=clean_name(wr_.pak_captain, "pak"), pak_captain_confidence="scorecard",
               detail_level="scorecard", scorecard_source=" | ".join(src[src.match_id == mid].source_url.dropna().unique()),
               won_toss_and_match=bool(r.pak_won_toss) and bool(r.is_win))
    if mt:
        upd.update(margin_type="runs" if mt[2] == "run" else "wickets", margin_value=float(mt[1]))
    for k, v in upd.items():
        m.loc[m.match_id == mid, k] = v
    # toss differences are only reported, never overwritten
    tw = wr_.toss_winner
    if isinstance(tw, str) and tw.strip() != str(r.toss_winner): log.append(f"{mid}: toss winner differs: dataset {r.toss_winner} / workbook {tw}")
    summary[mid] = dict(pak_xi=len(xi_p), pak_bat=len(P), opp_bat=len(O), pak_bowl=len(pbw), opp_bowl=len(obw), parts=len(F))

# ---------------------------------------------------------------- denormalised columns copied from pak_matches
mcols = m.set_index("match_id")
def denorm(df, cols):
    for c in cols: df[c] = df.match_id.map(mcols[c])
    return df
common = ["date", "year", "format", "opponent", "tournament", "tournament_type", "edition", "location_type", "venue", "result", "pak_batting_order"]
bat = denorm(pd.DataFrame(bat_rows), common); bowl_ = denorm(pd.DataFrame(bowl_rows), common)
part = denorm(pd.DataFrame(part_rows), common)
bat["player_cricsheet_name"] = np.nan; bowl_["player_cricsheet_name"] = np.nan
obat_ = denorm(pd.DataFrame(obat_rows), ["date", "year", "format", "opponent"])
obowl_ = denorm(pd.DataFrame(obowl_rows), ["date", "year", "format", "opponent"])

def merge_into(name, new, order=None):
    old = rd(name); old = drop_old(old)
    cols = list(old.columns)
    new = new.reindex(columns=cols)
    out = pd.concat([old, new], ignore_index=True)
    out.attrs["orig"] = old.attrs["orig"]
    wr(out, name); return len(new)

n = {}
n["pak_batting"] = merge_into("pak_batting", bat); n["pak_bowling"] = merge_into("pak_bowling", bowl_)
n["pak_partnerships"] = merge_into("pak_partnerships", part)
n["opp_batting"] = merge_into("opp_batting", obat_); n["opp_bowling"] = merge_into("opp_bowling", obowl_)
if ofield_rows: n["opp_fielding"] = merge_into("opp_fielding", pd.DataFrame(ofield_rows))
n["pak_appearances"] = merge_into("pak_appearances", pd.DataFrame(app_rows))

# ---------------------------------------------------------------- players
a = rd("pak_appearances")
g = a.groupby("player_id").agg(matches=("match_id", "nunique"), first_match=("date", "min"), last_match=("date", "max"))
g = g.join(a.groupby(["player_id", "format"]).match_id.nunique().unstack(fill_value=0).add_suffix("_matches"))
pp2 = pp.set_index("player_id")
for c in ["matches", "first_match", "last_match", "Test_matches", "ODI_matches", "T20I_matches"]:
    pp2[c] = g[c].reindex(pp2.index).fillna(0).astype(int) if c.endswith("matches") and c != "first_match" and c != "last_match" else g[c].reindex(pp2.index)
pp2.attrs["orig"] = pp.attrs["orig"]; wr(pp2.reset_index()[list(pp.columns)], "pak_players")

op = pd.read_csv(DATA / "opp_players.csv"); op = op[op.opponent != "Afghanistan"]
rows = {}
for mid in ids:
    wr_ = md[md.match_id == mid].iloc[0]; fmt = m.loc[m.match_id == mid, "format"].iloc[0]
    names = {clean_name(s, "afg") for s in str(wr_.opp_xi).split(",") if s.strip()}
    names |= set(obat_[obat_.match_id == mid].player) | set(obowl_[obowl_.match_id == mid].player)
    for nm in sorted(names):
        e = rows.setdefault(nm, dict(formats=set(), ms=set())); e["formats"].add(fmt); e["ms"].add(mid)
ap = pd.DataFrame([dict(player=k, opponent="Afghanistan", formats=", ".join(sorted(v["formats"])), matches_vs_pakistan=len(v["ms"]),
                        player_id="", cricinfo_id=cricinfo.get(k, np.nan),
                        cricinfo_url=(f"https://www.espncricinfo.com/cricketers/{cricinfo[k]}" if k in cricinfo else "")) for k, v in sorted(rows.items())])
op = pd.concat([op, ap], ignore_index=True).sort_values("matches_vs_pakistan", ascending=False, kind="stable")
op["cricinfo_id"] = op.cricinfo_id.astype("Int64"); op.to_csv(DATA / "opp_players.csv", index=False)

# ---------------------------------------------------------------- recorded captains, source patches, save
(ROOT / "eras").mkdir(exist_ok=True)
cap = m[m.match_id.isin(ids)][["match_id", "date", "format", "pak_captain", "scorecard_source"]].rename(columns={"pak_captain": "captain"})
cap.to_csv(ROOT / "eras" / "captains_scorecard.csv", index=False)
m["is_knockout"] = m.stage_inferred.isin(["Final", "Semi Final", "Quarter Final", "Play-off"])
m.attrs["orig"] = {}
m.to_csv(DATA / "pak_matches.csv", index=False)
# keep extra/missing_matches.csv in step so merge_manual_into_data.py does not bring the old values back
mm = pd.read_csv(ROOT / "extra" / "missing_matches.csv")
for mid in ids:
    r = m[m.match_id == mid].iloc[0]; k = (mm.date == r.date) & (mm.opponent == "Afghanistan")
    mm.loc[k, "pak_score"] = r.pak_score
    if isinstance(r.player_of_match, str): mm.loc[k, "player_of_match"] = r.player_of_match
mm.to_csv(ROOT / "extra" / "missing_matches.csv", index=False)

# captain stints (eras/captains.csv) from the final captain column, same layout build_captains.py writes
mm_ = m.assign(date=pd.to_datetime(m.date)).sort_values(["date", "match_id"])
stints = []
for fmt, g in mm_[mm_.pak_captain.notna()].groupby("format"):
    cur = start = prev = None
    for r_ in g.itertuples():
        if r_.pak_captain != cur:
            if cur: stints.append((fmt, cur, start, prev))
            cur, start = r_.pak_captain, r_.date
        prev = r_.date
    stints.append((fmt, cur, start, prev))
era = pd.DataFrame(stints, columns=["format", "person", "from_date", "to_date"])
era["from_date"], era["to_date"] = era.from_date.dt.strftime("%Y-%m-%d"), era.to_date.dt.strftime("%Y-%m-%d")
era.sort_values(["format", "from_date"]).to_csv(ROOT / "eras" / "captains.csv", index=False)

print("rows added:", n)
for k, v in summary.items(): print(k, v)
print("\nNOTES")
for l in log: print(" -", l)
