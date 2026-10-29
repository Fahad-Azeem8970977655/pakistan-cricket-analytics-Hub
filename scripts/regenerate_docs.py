"""Rewrite the data counts in README.md and docs/DATA_NOTES.md from data/pak_matches.csv so the two files can never disagree.

    python scripts/regenerate_docs.py

Only the text between <!--auto:...-->  markers (and the 'ball-by-ball detail for N of them' phrase in the README) is replaced.
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
m = pd.read_csv(ROOT / "data" / "pak_matches.csv", dtype={"match_id": str}, low_memory=False)
n = len(m)
dl = m.detail_level.value_counts() if "detail_level" in m else pd.Series({"ball-by-ball": (m.data_source != "manual").sum(), "result-only": (m.data_source == "manual").sum()})
bb = m.bbb_source.value_counts() if "bbb_source" in m else pd.Series(dtype=int)
cs, es = int(bb.get("Cricsheet", dl.get("ball-by-ball", 0))), int(bb.get("ESPN play-by-play", 0))
sc, ro = int(dl.get("scorecard", 0)), int(dl.get("result-only", 0))
cs_all = cs + es   # matches with delivery-level data
cc = m.pak_captain_confidence.value_counts()
kc = m.pak_coach_confidence.value_counts()
g = lambda s, k: int(s.get(k, 0))
fixed = g(cc, "certain") + g(cc, "scorecard") + g(cc, "manual")


def put(text, tag, body):
    pat = re.compile(rf"(<!--auto:{tag}-start-->).*?(<!--auto:{tag}-end-->)", re.S)
    assert pat.search(text), f"marker {tag} missing"
    return pat.sub(lambda mo: f"{mo.group(1)}\n{body}\n{mo.group(2)}", text)


# ------------------------------------------------------------------ README
r = (ROOT / "README.md").read_text(encoding="utf-8")
r = re.sub(r"ball-by-ball detail for \d+ of them", f"ball-by-ball detail for {cs_all} of them", r)
r = re.sub(r"~\d+ matches", f"~{round(n, -1)} matches", r)
r = put(r, "readme-data", f"""* **Matches and players:** Cricsheet ball-by-ball ({cs} matches), plus {es} Pakistan v Afghanistan matches whose scorecards were collected by hand and whose deliveries come from ESPN play-by-play, and {ro} recent matches with the result only.
* **Captains are partly inferred.** The source gives tenure years, not dates, so most matches are assigned a captain from the XI and tenure years, then fitted to the played counts. Every match has a `pak_captain_confidence` flag: {g(cc, 'certain')} certain, {g(cc, 'scorecard')} recorded on a scorecard, {g(cc, 'manual')} set by hand, {g(cc, 'solved')} solved by best fit, {g(cc, 'year-only')} year-only. Only {fixed} of {n} are certain, recorded or hand-checked.
* **Coaches** come from a dated list; {g(kc, 'clean')} matches map to exactly one coach, {g(kc, 'interim-fallback')} use an interim fallback (`pak_coach_confidence`).""")
r = r.replace("* Hand-added matches: `extra/missing_matches.csv`.", "* Hand-added matches: `extra/missing_matches.csv` (results) and `extra/afghanistan_scorecards.xlsx` (Pakistan v Afghanistan scorecards, sources in `pak_matches.scorecard_source`) and `extra/afghanistan_ball_by_ball.xlsx` (ESPN ball-by-ball for the same 15 matches).")
(ROOT / "README.md").write_text(r, encoding="utf-8")

# ------------------------------------------------------------------ DATA_NOTES
d = (ROOT / "docs" / "DATA_NOTES.md").read_text(encoding="utf-8")
d = put(d, "notes-match", f"""* **{cs} of {n} matches** (Tests, ODIs, T20Is, Jan 2015 to 20 Oct 2026) come from Cricsheet ball-by-ball files.
* **{es} Pakistan v Afghanistan matches** (2018 to 2025) are not in Cricsheet. Their scorecards were collected by hand (`scripts/merge_afghanistan_scorecards.py`) and their deliveries come from ESPN play-by-play (`scripts/merge_afghanistan_ballbyball.py`); see the next section. `detail_level = ball-by-ball`, `bbb_source = ESPN play-by-play`.
* **{ro} matches** (the 18 and 20 Oct 2026 ODIs) were added by hand from `extra/missing_matches.csv` with the result only: no XI, scorecards or umpires. `detail_level = result-only`.""")
rows = [("certain", "exactly one possible captain was in the XI"), ("scorecard", "the captain is marked (c) on a scorecard we collected"),
        ("manual", "set by hand from match reports"), ("solved", "several candidates; chosen by the count-fit step"),
        ("year-only", "no XI data; only the tenure year was used")]
tbl = "| Value | Meaning | Matches |\n|---|---|---|\n" + "\n".join(f"| `{k}` | {v} | {g(cc, k)} |" for k, v in rows)
d = put(d, "notes-captain", tbl)
d = put(d, "notes-captain-text", f"**What this means.** {fixed} of {n} matches ({round(100 * fixed / n)}%) are certain, recorded or hand-checked; the other {g(cc, 'solved') + g(cc, 'year-only')} are the best fit, not a record. Pre-2017 ODIs are the weakest (Azhar Ali, Sarfraz Ahmed and Shoaib Malik overlap), so a single match there may be swapped between them. Win % by captain is reliable at the level of a long tenure, not of a single match.")
d = put(d, "notes-coach", f"| `pak_coach_confidence` | Meaning | Matches |\n|---|---|---|\n| `clean` | exactly one coach role covers the match | {g(kc, 'clean')} |\n| `interim-fallback` | Australia white-ball series, Nov 2024, assigned to the interim coach | {g(kc, 'interim-fallback')} |")
(ROOT / "docs" / "DATA_NOTES.md").write_text(d, encoding="utf-8")
print(f"matches {n}: Cricsheet {cs}, ESPN ball-by-ball {es}, scorecard-only {sc}, result-only {ro}")
print("captain confidence:", cc.to_dict()); print("coach confidence:", kc.to_dict())
