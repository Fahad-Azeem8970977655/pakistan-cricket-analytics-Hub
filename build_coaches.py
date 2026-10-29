"""Fill pak_coach in data/pak_matches.csv and build eras/coaches.csv from
eras/pakistan_cricket_coaches_corrected.xlsx.  Run AFTER build_captains.py:  python build_coaches.py"""
import pandas as pd
src = pd.read_excel("eras/pakistan_cricket_coaches_corrected.xlsx")
src["s"] = pd.to_datetime(src["Start Date"]); src["e"] = pd.to_datetime(src["End Date"], errors="coerce").fillna(pd.Timestamp("2099-12-31"))
W, T, A = {"ODI", "T20I"}, {"Test"}, {"ODI", "T20I", "Test"}
def name(c): return c.replace("Sarfaraz", "Sarfraz").split(" (")[0]
# (coach label in sheet, formats covered, priority; lower = chosen first, >=5 = fallback)
RULES = {"Waqar Younis": (A, 0), "Mickey Arthur": (A, 0), "Misbah-ul-Haq": (A, 0), "Saqlain Mushtaq": (A, 0),
         "Abdul Rehman": ({"T20I"}, 0), "Grant Bradburn": (A, 0), "Mohammad Hafeez": (A, 0),
         "Azhar Mahmood (1st stint)": (W, 0), "Gary Kirsten": (W, 0), "Aaqib Javed": (A, 1),
         "Azhar Mahmood (2nd stint)": (T, 0), "Sarfaraz Ahmed": (T, 0),
         "Jason Gillespie": (T, 0),                         # Tests: Gillespie leads until he leaves
         "Mike Hesson": (W, 2)}                             # white-ball head coach from May 2025
FALLBACK = [("Jason Gillespie", W), ("Mike Hesson", T)]     # interim white-ball (Nov 2024) / temp red-ball
m = pd.read_csv("data/pak_matches.csv"); m["_d"] = pd.to_datetime(m["date"])
rows = {r["Coach"]: r for _, r in src.iterrows()}
def pick(r):
    hits = []
    for c, (fm, pr) in RULES.items():
        x = rows[c]
        if r.format in fm and x.s <= r._d <= x.e: hits.append((pr, x.s, c))
    if hits:
        return name(sorted(hits)[0][2]), ("clean" if len(hits) == 1 else "overlap-resolved")
    for c, fm in FALLBACK:
        x = rows[c]
        if r.format in fm and x.s <= r._d <= x.e: return name(c), "interim-fallback"
    return None, ""
res = m.apply(pick, axis=1, result_type="expand")
m["pak_coach"], m["pak_coach_confidence"] = res[0], res[1]
# eras: contiguous stints
out = []
for fmt, g in m[m.pak_coach.notna()].sort_values("_d").groupby("format"):
    cur = None
    for _, r in g.iterrows():
        if r.pak_coach != cur:
            if cur: out.append((fmt, cur, start, prev))
            cur, start = r.pak_coach, r._d
        prev = r._d
    out.append((fmt, cur, start, prev))
era = pd.DataFrame(out, columns=["format", "person", "from_date", "to_date"])
for c in ("from_date", "to_date"): era[c] = era[c].dt.strftime("%Y-%m-%d")
era.sort_values(["format", "from_date"]).to_csv("eras/coaches.csv", index=False)
m.drop(columns="_d").to_csv("data/pak_matches.csv", index=False)
print(m.pak_coach.notna().sum(), "of", len(m), "filled"); print(m.pak_coach_confidence.value_counts())
print(m.groupby(["format", "pak_coach"]).size().to_string()); print(len(era), "stints")
print(m[m.pak_coach.isna()][["date", "format", "opponent"]])
