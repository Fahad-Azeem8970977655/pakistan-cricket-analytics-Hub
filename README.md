# Pakistan Cricket Analytics Hub

End-to-end analytics for Pakistan men's cricket, 2015 to 2026 (Tests, ODIs, T20Is): ~480 matches, ball-by-ball detail for 479 of them,
25 pages covering team, player, opposition, venue and match views, win-probability models, and an AI assistant that answers questions on the data.

**Live app:** _add your Streamlit Cloud link here_

## What is in it
* **Team:** rise and fall by era, tournaments, opponents and venues, head-to-head, toss and chase, venue profiles.
* **Captains and coaches:** win % by captain and coach, captain-coach pairs, before/after changes, a player's batting and bowling as captain vs not.
* **Players:** batting, bowling, partnerships and fielding, form tracker, player comparison, splits.
* **Match tools:** match explorer, one-page match report (scorecard, run-rate worm, partnerships), innings progress.
* **AI and ML:** Elo and pre-match win probability, live chase probability, first-innings score model, opponent scouting, and **Ask the Data** (Groq LLM writes a read-only pandas query; it is checked, run on the CSVs, and shown so you can verify it).
* **Data transparency:** a Data Quality page and a KPI Guide.

## Do the models work?
They beat a no-model baseline, but only modestly, and the report says so. Models are trained only on earlier matches and tested on later ones.
Full tables and method: [`docs/model_evaluation.md`](docs/model_evaluation.md). Reproduce with `python evaluate_models.py`.

| Test | Baseline (win rate) | Elo only | Logistic reg. | Gradient boosting |
|---|---|---|---|---|
| A. One time split, 115 test matches: log-loss (lower is better) | 0.694 | 0.647 | 0.632 | 0.594 |
| B. Yearly backtest 2021 to 2026, 248 predictions: log-loss | 0.690 | 0.661 | 0.677 | 0.664 |

Split A looks flattering (gradient boosting 70% accuracy) but the larger backtest B shows about 64% at best and little separation between models.
With this much data, the honest takeaway is that results are only partly predictable from pre-match facts.

## Data, and what is inferred
Read [`docs/DATA_NOTES.md`](docs/DATA_NOTES.md). In short:
<!--auto:readme-data-start-->
* **Matches and players:** Cricsheet ball-by-ball (464 matches), plus 15 Pakistan v Afghanistan matches whose scorecards were collected by hand and whose deliveries come from ESPN play-by-play, and 2 recent matches with the result only.
* **Captains are partly inferred.** The source gives tenure years, not dates, so most matches are assigned a captain from the XI and tenure years, then fitted to the played counts. Every match has a `pak_captain_confidence` flag: 184 certain, 15 recorded on a scorecard, 16 set by hand, 266 solved by best fit, 0 year-only. Only 215 of 481 are certain, recorded or hand-checked.
* **Coaches** come from a dated list; 476 matches map to exactly one coach, 5 use an interim fallback (`pak_coach_confidence`).
<!--auto:readme-data-end-->

## Sources and credits
* Ball-by-ball match data: [Cricsheet](https://cricsheet.org) (check their site for the current licence and attribution terms).
* Captain tenures: Wikipedia, *List of Pakistan national cricket captains*, plus a compiled `eras/captains_2015_present.csv`.
* Head coach tenures: compiled by the project author in `eras/pakistan_cricket_coaches_corrected.xlsx`.
* Hand-added matches: `extra/missing_matches.csv` (results) and `extra/afghanistan_scorecards.xlsx` (Pakistan v Afghanistan scorecards, sources in `pak_matches.scorecard_source`).

## Run it
```
pip install -r requirements.txt
streamlit run app.py
```
**Groq key (for Ask the Data):** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, paste your key from console.groq.com/keys, restart. Never commit `secrets.toml`.

Rebuild order after a data refresh: `python scripts/merge_manual_into_data.py`, `python scripts/merge_afghanistan_scorecards.py`, `python scripts/merge_afghanistan_ballbyball.py`, `python scripts/apply_ballbyball_corrections.py`, `python scripts/apply_cricinfo_audit_corrections.py`, `python scripts/merge_afghanistan_ballbyball.py` (again, to refresh the check list), `python build_coaches.py`, `python scripts/build_player_splits.py`, then `python scripts/regenerate_docs.py` (keeps the counts in this README and `docs/DATA_NOTES.md` in step with the CSV). `build_captains.py` re-fits the inferred captains and can re-assign tied matches; run it only on a full rebuild.

## Project layout
```
app.py                     navigation
ask_engine.py              Groq call + read-only pandas runner (Ask the Data)
evaluate_models.py         reproducible model evaluation -> docs/
build_captains.py          fills pak_captain, writes eras/captains.csv (see its note before re-running)
build_coaches.py           fills pak_coach, writes eras/coaches.csv
scripts/                   data build and merge scripts (merge_afghanistan_scorecards.py, regenerate_docs.py, ...)
data/                      cleaned CSVs (matches, batting, bowling, overs, partnerships, ...)
eras/                      captain and coach sources and generated stints
extra/  incoming/          hand-added matches and Afghanistan scorecards, raw sources
docs/                      model evaluation and data notes
pages/                     one file per dashboard page
utils/  views/             shared loaders, theme, ML helpers, overview (see note below)
```
> **Before publishing:** `utils/`, `views/` and pages 1 to 9 must be in the repository; they were not part of the files used to prepare this update.
