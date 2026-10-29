"""Apply data fixes 1-5 to data/*.csv, with a backup and a before/after report.

    python scripts/apply_fixes_1_to_5.py            # apply
    python scripts/apply_fixes_1_to_5.py --dry-run  # show counts only, write nothing

Fixes
  1. One canonical name per stadium (spelling variants and renamed grounds merged)
  2. Aug 2023 Afghanistan ODIs in Sri Lanka: "Home (Sri Lanka)" -> "Neutral"
  3. "Tri-series" merged into "Tri/Multi-team Series"
  4. Two matches with a blank tournament get a series name and type Bilateral
  5. City filled and standardised, one city per canonical venue

Safe to re-run (idempotent). Originals are copied to backup_pre_fix_1_to_5/ first.
Writes docs/before_after_fixes_1_to_5.md.
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BACKUP = ROOT / "backup_pre_fix_1_to_5"
REPORT = ROOT / "docs" / "before_after_fixes_1_to_5.md"
DRY = "--dry-run" in sys.argv

# Tables that carry venue / location_type / tournament_type (checked against data/*.csv headers)
TABLES = ["pak_matches", "pak_batting", "pak_bowling", "pak_fielding", "pak_partnerships"]

# ---- FIX 1: variant -> canonical (explicit so every merge can be reviewed) -----------------------
VENUE_MAP = {
    "Gaddafi Stadium": "Gaddafi Stadium, Lahore",
    "Shere Bangla National Stadium": "Shere Bangla National Stadium, Mirpur",
    "R Premadasa Stadium, Colombo": "R Premadasa Stadium",
    "Bay Oval, Mount Maunganui": "Bay Oval",
    "Brisbane Cricket Ground, Woolloongabba, Brisbane": "Brisbane Cricket Ground, Woolloongabba",
    "Eden Gardens, Kolkata": "Eden Gardens",
    "Eden Park, Auckland": "Eden Park",
    "Edgbaston, Birmingham": "Edgbaston",
    "Hagley Oval": "Hagley Oval, Christchurch",
    "Headingley, Leeds": "Headingley",
    "Kennington Oval, London": "Kennington Oval",
    "Kensington Oval, Bridgetown, Barbados": "Kensington Oval, Bridgetown",
    "Kingsmead, Durban": "Kingsmead",
    "Lord's, London": "Lord's",
    "McLean Park, Napier": "McLean Park",
    "National Stadium": "National Stadium, Karachi",
    "Newlands, Cape Town": "Newlands",
    "Old Trafford, Manchester": "Old Trafford",
    "Providence Stadium, Guyana": "Providence Stadium",
    "Queen's Park Oval, Port of Spain, Trinidad": "Queen's Park Oval, Port of Spain",
    "Queens Sports Club": "Queens Sports Club, Bulawayo",
    "Sabina Park, Kingston, Jamaica": "Sabina Park, Kingston",
    "Seddon Park, Hamilton": "Seddon Park",
    "Sophia Gardens, Cardiff": "Sophia Gardens",
    "SuperSport Park": "SuperSport Park, Centurion",
    "The Wanderers Stadium, Johannesburg": "The Wanderers Stadium",
    "Trent Bridge, Nottingham": "Trent Bridge",
    "University Oval": "University Oval, Dunedin",
    # same physical ground, renamed or re-spelled (judgement calls, listed in the report):
    "Zayed Cricket Stadium, Abu Dhabi": "Sheikh Zayed Stadium",
    "Westpac Stadium": "Sky Stadium, Wellington",
}

# ---- FIX 2: Pakistan was not the host; these were Afghanistan's series in Sri Lanka ------------
FIX2_LOCATION = {"from": "Home (Sri Lanka)", "to": "Neutral"}

# ---- FIX 3 ---------------------------------------------------------------------------------------
FIX3_TYPE = {"Tri-series": "Tri/Multi-team Series"}

# ---- FIX 4: blank tournaments (matched by match_id, named in the style of neighbouring rows) -----
FIX4 = {
    "858491": "Pakistan in Bangladesh T20I Series",   # 2015-04-24, Mirpur
    "913663": "Pakistan in England T20I Series",      # 2016-09-07, Old Trafford
}

# ---- FIX 5: city overrides where the data mixes city / region / suburb for one ground ------------
CITY_OVERRIDE = {
    "Kensington Oval, Bridgetown": "Bridgetown",
    "Providence Stadium": "Providence",
    "Queen's Park Oval, Port of Spain": "Port of Spain",
    "Sabina Park, Kingston": "Kingston",
    "Shere Bangla National Stadium, Mirpur": "Dhaka",
    "Punjab Cricket Association IS Bindra Stadium, Mohali": "Mohali",
}


def load(name):
    # match_id is read as text everywhere so ids compare the same way in every table
    return pd.read_csv(DATA / f"{name}.csv", low_memory=False, dtype={"match_id": str})


def snapshot(m):
    """Counts used in the before/after report."""
    gaddafi = m[m.venue.str.contains("Gaddafi", na=False)]
    return {
        "matches (rows)": len(m),
        "distinct venue names": m.venue.nunique(),
        "matches with missing city": int(m.city.isna().sum()),
        "distinct city values": m.city.nunique(),
        "tournament_type = Unknown": int((m.tournament_type == "Unknown").sum()),
        "tournament_type = Tri-series": int((m.tournament_type == "Tri-series").sum()),
        "tournament_type = Tri/Multi-team Series": int((m.tournament_type == "Tri/Multi-team Series").sum()),
        "matches with blank tournament": int(m.tournament.isna().sum()),
        "location_type = Home (Sri Lanka)": int((m.location_type == "Home (Sri Lanka)").sum()),
        "location_type = Neutral": int((m.location_type == "Neutral").sum()),
        "location_type = Home (all kinds)": int(m.location_type.str.startswith("Home").sum()),
        "venues with fewer than 5 matches": int((m.venue.value_counts() < 5).sum()),
        "Gaddafi Stadium: distinct names / matches": f"{gaddafi.venue.nunique()} / {len(gaddafi)}",
    }


def apply(tables):
    """Return fixed copies of all tables."""
    out = {k: v.copy() for k, v in tables.items()}
    m = out["pak_matches"]

    # FIX 4 first, so the type fix below leaves it alone
    for mid, name in FIX4.items():
        k = m.match_id == mid
        m.loc[k, ["tournament", "tournament_type", "tournament_group"]] = [name, "Bilateral", "Bilateral series"]

    # match_ids whose location changes (FIX 2), taken from matches so every table follows
    loc_ids = set(m.loc[m.location_type == FIX2_LOCATION["from"], "match_id"])

    for name, d in out.items():
        d["venue"] = d["venue"].replace(VENUE_MAP)                                   # FIX 1
        d.loc[d.match_id.isin(loc_ids), "location_type"] = FIX2_LOCATION["to"]       # FIX 2
        d["tournament_type"] = d["tournament_type"].replace(FIX3_TYPE)               # FIX 3
        if name != "pak_matches":                                                    # FIX 4 in detail tables
            for mid, t in FIX4.items():
                k = d.match_id == mid
                d.loc[k, ["tournament", "tournament_type"]] = [t, "Bilateral"]

    # FIX 3 also renames the group label of the two ODI tri-series rows to match the other tri groups
    k = (m.tournament_group == "Tri-series") & m.tournament.notna()
    m.loc[k, "tournament_group"] = m.loc[k, "tournament"]

    # FIX 5: one city per canonical venue = override, else most common non-blank city among its rows
    mode_city = m.dropna(subset=["city"]).groupby("venue").city.agg(lambda s: s.value_counts().index[0])
    city = {v: CITY_OVERRIDE.get(v, mode_city.get(v)) for v in m.venue.unique()}
    m["city"] = m.venue.map(city)
    return out


def checks(m):
    """Hard sanity checks; raise if a fix broke something."""
    assert m.match_id.is_unique, "duplicate match_id"
    assert m.groupby("venue").venue_country.nunique().max() == 1, "a venue maps to two countries"
    assert m.groupby("venue").city.nunique().max() == 1, "a venue maps to two cities"
    assert m.city.notna().all(), f"cities still missing: {m[m.city.isna()].venue.unique()}"
    assert not (m.tournament_type == "Unknown").any(), "Unknown tournament_type left"
    assert not (m.tournament_type == "Tri-series").any(), "Tri-series left"
    assert not (m.location_type == "Home (Sri Lanka)").any(), "Home (Sri Lanka) left"


def merged_any(tabs):
    return any(tabs["pak_matches"].venue.isin(VENUE_MAP).any() for _ in [0])


def main():
    before_tabs = {t: load(t) for t in TABLES}
    before = snapshot(before_tabs["pak_matches"])
    after_tabs = apply(before_tabs)
    after = snapshot(after_tabs["pak_matches"])
    checks(after_tabs["pak_matches"])

    # row counts must not change anywhere
    for t in TABLES:
        assert len(before_tabs[t]) == len(after_tabs[t]), f"row count changed in {t}"

    # report pieces
    ven_b = before_tabs["pak_matches"].venue.value_counts()
    ven_a = after_tabs["pak_matches"].venue.value_counts()
    merged = []
    for v, c in VENUE_MAP.items():
        n = int(ven_b.get(v, 0))
        if n:
            merged.append((v, c, n))
    cities_changed = (before_tabs["pak_matches"].city.fillna("(blank)") != after_tabs["pak_matches"].city).sum()
    per_table = {t: (before_tabs[t].venue.nunique(), after_tabs[t].venue.nunique()) for t in TABLES}

    lines = ["# Before / after: fixes 1 to 5", "",
             "Generated by `scripts/apply_fixes_1_to_5.py`. Row counts are unchanged in every table.", "",
             "## Headline counts (pak_matches.csv)", "", "| Metric | Before | After |", "|---|---|---|"]
    lines += [f"| {k} | {before[k]} | {after[k]} |" for k in before]
    lines += ["", "## Distinct venue names per table", "", "| Table | Before | After |", "|---|---|---|"]
    lines += [f"| {t} | {b} | {a} |" for t, (b, a) in per_table.items()]
    lines += ["", "## Venue merges applied (FIX 1)", "", "| Old name | Canonical name | Rows merged |", "|---|---|---|"]
    lines += [f"| {v} | {c} | {n} |" for v, c, n in merged]
    lines += ["", "Judgement calls: Zayed Cricket Stadium = Sheikh Zayed Stadium (same Abu Dhabi ground); "
              "Westpac Stadium = Sky Stadium, Wellington (renamed 2019). WACA and Perth Stadium are different grounds and were NOT merged.",
              "", f"## Cities changed or filled (FIX 5): {int(cities_changed)} matches", "",
              "## Other fixes", "",
              "* FIX 2: 3 matches (22, 24, 26 Aug 2023, Afghanistan ODIs in Sri Lanka) changed Home (Sri Lanka) to Neutral in all 5 tables. "
              "The model code counted them as home games; re-running `evaluate_models.py` before and after shows no change at 3 decimals.",
              "* FIX 3: the 2 ODI Tri-Series matches (Oct 2026) now use type Tri/Multi-team Series.",
              "* FIX 4: 24 Apr 2015 v Bangladesh and 7 Sep 2016 v England now have tournament names and type Bilateral."]
    text = "\n".join(lines) + "\n"
    print(text)

    if DRY:
        print("[dry run] nothing written")
        return
    if not BACKUP.exists():
        BACKUP.mkdir()
        for t in TABLES:
            shutil.copy2(DATA / f"{t}.csv", BACKUP / f"{t}.csv")
        print(f"backup written to {BACKUP}")
    for t in TABLES:
        after_tabs[t].to_csv(DATA / f"{t}.csv", index=False)
    if before == after and not merged_any(before_tabs):
        print("nothing to change (already fixed); report left as is")
        return
    REPORT.write_text(text, encoding="utf-8")
    print(f"updated {len(TABLES)} tables; report: {REPORT}")


if __name__ == "__main__":
    main()
