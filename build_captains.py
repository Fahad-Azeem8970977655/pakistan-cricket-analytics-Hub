"""NOTE: the optimisation below can break ties differently each time it is re-run, which re-assigns some ambiguous matches
(about 19 changed when it was last re-run). The shipped data/pak_matches.csv therefore keeps the earlier inferred captains and only
overlays the 15 captains recorded on scorecards (eras/captains_scorecard.csv, confidence 'scorecard'). Re-run only on a full rebuild.

Fill pak_captain in data/pak_matches.csv and build eras/captains.csv.
Wikipedia gives tenure years only, so each match is assigned a captain who (a) was in the XI,
(b) held the captaincy that year (Wikipedia / captains_2015_present.csv), and (c) fits the
tenure's played count (solved as a small optimisation). Run: python build_captains.py"""
import numpy as np, pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix

ALIAS = {"Shaheen Afridi": "Shaheen Shah Afridi"}
XI_ALIAS = {"Agha Salman": "Salman Ali Agha"}
m = pd.read_csv("data/pak_matches.csv"); m["match_id"] = m["match_id"].astype(str)
a = pd.read_csv("data/pak_appearances.csv"); a["match_id"] = a["match_id"].astype(str)
cap = pd.read_csv("eras/captains_2015_present.csv")
cap["captain"] = cap.captain.replace(ALIAS)
# fix column-shift in source for ODI Rizwan / Shaheen (lost = played - won)
cap.loc[cap.captain.isin(["Mohammad Rizwan", "Shaheen Shah Afridi"]) & (cap.format == "ODI"), "lost"] = \
    cap.played - cap.won
xi = a.assign(player=a.player.replace(XI_ALIAS)).groupby("match_id").player.apply(set).to_dict()
for i, r in m.iterrows():
    if isinstance(r.pak_xi, str):
        xi.setdefault(r.match_id, set()).update(XI_ALIAS.get(p.strip(), p.strip()) for p in r.pak_xi.split(","))
m["date"] = pd.to_datetime(m["date"]); m = m.sort_values("date").reset_index(drop=True)
# captains RECORDED on a scorecard (scripts/merge_afghanistan_scorecards.py) are overlaid at the end as facts; the fit itself is left as it was,
# so adding scorecards never re-shuffles the other inferred matches
import os
SC = {}
if os.path.exists("eras/captains_scorecard.csv"):
    SC = dict(pd.read_csv("eras/captains_scorecard.csv", dtype=str).set_index("match_id").captain)

m["pak_captain"] = None; m["pak_captain_confidence"] = ""
for fmt in ["Test", "ODI", "T20I"]:
    cf = cap[cap.format == fmt].reset_index(drop=True)
    idx = m.index[m.format == fmt]
    cands = {}
    for i in idx:
        r = m.loc[i]; players = xi.get(r.match_id, set())
        ok = cf[(cf.from_year <= r.year) & (cf.to_year >= r.year)].captain.tolist()
        inxi = [c for c in ok if c in players]
        cands[i] = (inxi, "xi" if inxi else "year-only", ok if not inxi and not players else inxi)
    # variables x[i,c]
    var = [(i, c) for i in idx for c in cands[i][2]]
    nv = len(var); caps = cf.captain.tolist(); nc = len(caps)
    # slack: over/under per captain
    N = nv + 2 * nc
    cost = np.zeros(N); cost[nv:] = 1
    A = lil_matrix((len(idx) + nc, N)); lo = []; hi = []
    row = 0; pos = {}
    for k, (i, c) in enumerate(var): pos.setdefault(i, []).append(k)
    for i in idx:
        for k in pos.get(i, []): A[row, k] = 1
        lo.append(1 if i in pos else 0); hi.append(1 if i in pos else 0); row += 1
    for j, c in enumerate(caps):
        for k, (i, cc) in enumerate(var):
            if cc == c: A[row, k] = 1
        A[row, nv + j] = -1; A[row, nv + nc + j] = 1       # count - over + under = target
        t = cf.played[j]
        if pd.isna(t): t = 0
        lo.append(t); hi.append(t); row += 1
    # captains whose tenure began before 2015 may have unseen matches -> under-slack free
    for j in range(nc):
        if cf.from_year[j] < 2015: cost[nv + nc + j] = 0
    res = milp(cost, constraints=LinearConstraint(A.tocsr(), lo, hi),
               integrality=np.r_[np.ones(nv), np.zeros(2 * nc)], bounds=Bounds(0, np.r_[np.ones(nv), [1e3] * 2 * nc]))
    x = res.x
    for k, (i, c) in enumerate(var):
        if x[k] > .5:
            m.loc[i, "pak_captain"] = c
            n = len(cands[i][2])
            m.loc[i, "pak_captain_confidence"] = ("certain" if n == 1 and cands[i][1] == "xi" else
                                                  "solved" if cands[i][1] == "xi" else "year-only")

# manual overrides: NZ 2021 + Asian Games 2023 from PCB/Cricinfo reports; 2020 England & SA Tests from the
# series-level Test table on Wikipedia (captain per series)
OVERRIDES = {("Test", "2026-05-16"): "Shan Masood", ("Test", "2026-07-25"): "Babar Azam", ("Test", "2026-08-19"): "Salman Ali Agha",
             ("Test", "2026-08-27"): "Babar Azam", ("Test", "2026-09-09"): "Babar Azam",  # web-verified 2026-10-21
             ("Test", "2020-08-05"): "Azhar Ali", ("Test", "2020-08-13"): "Azhar Ali", ("Test", "2020-08-21"): "Azhar Ali",
             ("Test", "2021-01-26"): "Babar Azam", ("Test", "2021-02-04"): "Babar Azam",
             ("Test", "2020-12-26"): "Mohammad Rizwan", ("Test", "2021-01-03"): "Mohammad Rizwan",
             ("T20I", "2023-10-03"): "Qasim Akram", ("T20I", "2023-10-06"): "Qasim Akram", ("T20I", "2023-10-07"): "Qasim Akram"}
for (f, d), c in OVERRIDES.items():
    k = (m.format == f) & (m.date.dt.strftime("%Y-%m-%d") == d)
    m.loc[k, "pak_captain"] = c; m.loc[k, "pak_captain_confidence"] = "manual"
for mid_, c_ in SC.items():
    k = m.match_id == mid_
    m.loc[k, "pak_captain"] = c_; m.loc[k, "pak_captain_confidence"] = "scorecard"
m = m.sort_values(["date", "match_id"]).reset_index(drop=True)
# eras: contiguous stints per format
rows = []
for fmt, g in m[m.pak_captain.notna()].groupby("format"):
    g = g.sort_values("date"); start = prev = None; cur = None
    for _, r in g.iterrows():
        if r.pak_captain != cur:
            if cur: rows.append((fmt, cur, start, prev))
            cur, start = r.pak_captain, r.date
        prev = r.date
    rows.append((fmt, cur, start, prev))
era = pd.DataFrame(rows, columns=["format", "person", "from_date", "to_date"])
era["from_date"] = era.from_date.dt.strftime("%Y-%m-%d"); era["to_date"] = era.to_date.dt.strftime("%Y-%m-%d")
era.sort_values(["format", "from_date"]).to_csv("eras/captains.csv", index=False)
m["date"] = m.date.dt.strftime("%Y-%m-%d"); m.to_csv("data/pak_matches.csv", index=False)
print(m.pak_captain.notna().sum(), "of", len(m), "matches filled")
print(m.pak_captain_confidence.value_counts())
print(m.groupby(["format", "pak_captain"]).size().to_string())
print(len(era), "stints")
