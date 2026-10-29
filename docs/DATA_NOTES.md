# Data notes: what is exact and what is inferred

## Match data
<!--auto:notes-match-start-->
* **464 of 481 matches** (Tests, ODIs, T20Is, Jan 2015 to 20 Oct 2026) come from Cricsheet ball-by-ball files.
* **15 Pakistan v Afghanistan matches** (2018 to 2025) are not in Cricsheet. Their scorecards were collected by hand (`scripts/merge_afghanistan_scorecards.py`) and their deliveries come from ESPN play-by-play (`scripts/merge_afghanistan_ballbyball.py`); see the next section. `detail_level = ball-by-ball`, `bbb_source = ESPN play-by-play`.
* **2 matches** (the 18 and 20 Oct 2026 ODIs) were added by hand from `extra/missing_matches.csv` with the result only: no XI, scorecards or umpires. `detail_level = result-only`.
<!--auto:notes-match-end-->

## Pakistan v Afghanistan scorecards (hand-collected)
Cricsheet has none of these 15 matches (Sep 2018 to Sep 2025). The scorecards were collected from Cricinfo, Cricbuzz and Wikipedia into `extra/afghanistan_scorecards.xlsx` and merged by `scripts/merge_afghanistan_scorecards.py`. The source URLs for each match are in `pak_matches.scorecard_source`.

**What they add:** batting and bowling for both sides, partnerships (from the fall of wickets), the playing XI for both sides, umpires, match referee, player of the match, Pakistan's batting order and the captain marked on the scorecard (`pak_captain_confidence = scorecard`). Afghan players are added to the opposition tables.

**What is still empty (never estimated):**
* (filled by the ball-by-ball merge, see the next section: dot balls, over-by-over runs, deliveries, phase splits, balls and runs per batter in each partnership);
* Pakistan fielding rows (`pak_fielding`): the Afghan batting card does not name the fielder for many dismissals. Afghan fielding (`opp_fielding`) is built from Pakistan's dismissals, so Pakistan fielding totals exclude these 15 matches;
* Cricinfo IDs for 4 Afghan players. The workbook gives the same player different IDs in different matches (the `manual_10` and `manual_15` rows carry older IDs). An ID is used only when most of that player's matches agree; disputed ones are listed in `extra/cricinfo_id_conflicts.csv` (17 players). The 4 that were a tie (Abdul Rahman, Darwish Rasooli, Noor Ahmad, AM Ghazanfar) were checked against their Cricinfo profile pages and filled by `scripts/apply_cricinfo_audit_corrections.py` (21 rows across batting, bowling, fielding and player tables).

**Checks run:** batting runs + extras = innings total for both sides; bowlers' balls = innings length; fall-of-wicket count = wickets lost; partnership runs add up to the Pakistan total; 11 named players per side. All 15 matches pass. This is arithmetic only: the scorecards have **not** been checked line by line against Cricinfo.

## Pakistan v Afghanistan ball-by-ball (ESPN play-by-play)
The same 15 matches have 5,623 deliveries from the ESPN play-by-play feed (`extra/afghanistan_ball_by_ball.xlsx`, merged by `scripts/merge_afghanistan_ballbyball.py`). `detail_level = ball-by-ball`, `bbb_source = ESPN play-by-play`.

**What it adds:** rows in `pak_deliveries` and `pak_overs` (so these matches now appear on Phase Analysis, Innings Progress and the Match One Pager); `dot_balls` and `dot_ball_pct` for every batter and bowler; balls and runs per batter in each Pakistan partnership; powerplay / middle / death runs and wickets for both sides; dot-ball % for both sides. Phases are fixed by format: ODI overs 1-10, 11-40, 41-50; T20I overs 1-6, 7-15, 16-20 (no match was rain-reduced).

**Checks:** every innings agrees with the source's own coverage sheet (delivery count, runs, legal balls); 27 batter / bowler lines first differed from the hand-collected scorecards. In 7 cases an independent check showed the card was wrong (boundary counts that contradict the bowling card or the batter's runs, bowler figures that do not add up to the innings) and `scripts/apply_ballbyball_corrections.py` fixed them from the deliveries (before / after in `docs/afghanistan_ballbyball_corrections.csv`). A further 20 values and one missing bowling row (7 Sep 2022 and 6 Oct 2023) were checked against the Cricinfo scorecard pages and corrected by `scripts/apply_cricinfo_audit_corrections.py` (list with source URLs: `docs/cricinfo_audit_corrections.csv`, full audit: `docs/cricinfo_audit.xlsx`). The last 2 lines (29 Jun 2019, Haris Sohail 57 vs 56 balls and Imad Wasim 54 vs 55) were also checked: Cricinfo shows 27 (57) and 49 (54), so the scorecard is right and the deliveries are one ball off. Nothing is unresolved. Listed in `docs/afghanistan_ballbyball_checks.csv`, explained in `docs/afghanistan_ballbyball_report.md`.

**Still empty:** Pakistan fielding rows (the feed names no fielder).

**Corrections made while merging:** Pakistan's first T20I score on 24 Mar 2023 is 92/9, not 92/10; the 26 Aug 2023 ODI is a 59-run win; one Afghan row had a wrong innings number; the bowling innings numbers of two matches were aligned to the batting innings; partner names come from the batting order, because the workbook's partner column disagreed with it for 18 wickets. Names follow the dashboard's spelling (for example Sarfraz Ahmed, Salman Ali Agha, Sufiyan Muqeem, Mirza Baig). Afghan players use full names, because Afghanistan is not in Cricsheet (other opponents use Cricsheet's initials style). One Afghan player (Karim Janat, 27 Mar 2023) appears on the scorecard but not in the 11 listed names, so he is a replacement.

## Captains: partly inferred
The only source available gives each captain's tenure by **year**, not by date, and several captains overlap in a year (for example ODI 2015, T20I 2023). So `build_captains.py` assigns a captain to each match like this:

1. A captain is a candidate only if the tenure years cover the match **and** the captain is in the playing XI.
2. Where more than one candidate remains, an integer optimisation picks the assignment whose per-captain match counts best fit the played counts in the source table.
3. A few matches were fixed by hand from PCB / Cricinfo reports and series-level Wikipedia tables (New Zealand Tests 2020/21, the three Asian Games T20Is in 2023, England and South Africa Tests).

Every match carries a `pak_captain_confidence` value:

<!--auto:notes-captain-start-->
| Value | Meaning | Matches |
|---|---|---|
| `certain` | exactly one possible captain was in the XI | 184 |
| `scorecard` | the captain is marked (c) on a scorecard we collected | 15 |
| `manual` | set by hand from match reports | 16 |
| `solved` | several candidates; chosen by the count-fit step | 266 |
| `year-only` | no XI data; only the tenure year was used | 0 |
<!--auto:notes-captain-end-->

<!--auto:notes-captain-text-start-->
**What this means.** 215 of 481 matches (45%) are certain, recorded or hand-checked; the other 266 are the best fit, not a record. Pre-2017 ODIs are the weakest (Azhar Ali, Sarfraz Ahmed and Shoaib Malik overlap), so a single match there may be swapped between them. Win % by captain is reliable at the level of a long tenure, not of a single match.
<!--auto:notes-captain-text-end-->

## Coaches: mostly clean
The coach source (`eras/pakistan_cricket_coaches_corrected.xlsx`) has exact start and end dates, split by red-ball and white-ball roles. `build_coaches.py` applies specialist roles first, then all-format coaches.

<!--auto:notes-coach-start-->
| `pak_coach_confidence` | Meaning | Matches |
|---|---|---|
| `clean` | exactly one coach role covers the match | 476 |
| `interim-fallback` | Australia white-ball series, Nov 2024, assigned to the interim coach | 5 |
<!--auto:notes-coach-end-->

## Other limits
* Pakistan fielding totals exclude the 15 Afghanistan matches (see above).
* The sample is small: about 480 matches over 11 years, split across three formats. Treat per-opponent and per-venue percentages with care.
* Win % uses completed matches only. Draws in Tests count as completed, not as wins.
* The models use only pre-match facts and are tested on later matches than they train on. See `docs/model_evaluation.md`.

## Verification log (2026-10-21)
All 2026 results were checked against Cricinfo/ESPN, Wikipedia and news reports: Bangladesh ODIs and Tests, Australia T20Is and ODIs, Sri Lanka T20Is (Jan and Oct), T20 World Cup, West Indies and England Tests, Asian Games, and the Oct 2026 tri-series. All results and margins matched. Fixed: five 2026 Test captains (16 May Masood; 25 Jul Babar; 19 Aug Salman Ali Agha; 27 Aug and 9 Sep Babar, confirmed by Wikipedia series page), T20 World Cup 2026 stage (Super 8, eliminated), Lord's Test 2026 score (110/10 & 194/10; Cricsheet had 9 wickets because of an absent-hurt batter; batting rows still list 9 dismissals). Added by hand, no scorecard: 18 Oct ODI v Sri Lanka (won by 37 runs) and 20 Oct ODI v England (won by 87 runs, 302/9 v 215, Arafat Minhas player of the match). Not in the data: the 9 Jan 2026 T20I v Sri Lanka (rain, abandoned), the abandoned T20 World Cup v New Zealand and Asian Games QF v Hong Kong, and tri-series matches after 20 Oct. The 15 Afghanistan scorecards (added later) passed arithmetic checks only. Not verified: 2015-2025 matches, player-level stats, weather, models.
