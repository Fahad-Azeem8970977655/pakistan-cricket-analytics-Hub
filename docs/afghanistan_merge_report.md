# Pakistan v Afghanistan scorecard merge

Merged from `extra/afghanistan_scorecards.xlsx` (workbook version 4) by `scripts/merge_afghanistan_scorecards.py` (re-runnable; running it twice gives identical files).
A copy of every file that changed is in `backup_pre_afghanistan_merge/`.

## What was loaded
| Table | Rows added |
|---|---|
| `pak_batting` | 143 |
| `pak_bowling` | 86 |
| `pak_partnerships` | 128 (7 to 10 per match; stand totals only, see gaps) |
| `pak_appearances` | 165 (11 Pakistan players x 15 matches) |
| `opp_batting` | 128 |
| `opp_bowling` | 86 |
| `opp_fielding` | 66 |
| `opp_players` | 35 Afghan players (new; Afghanistan had none); 31 have a Cricinfo ID |
| `pak_matches` | 15 rows enriched; 2 new columns `detail_level`, `scorecard_source` |
| `pak_players` | match counts and first/last dates recomputed (46 players changed) |
| `pak_player_splits_*` | rebuilt |
| `eras/captains.csv` | rebuilt (55 stints); `eras/captains_scorecard.csv` added |

Every existing row in every table is unchanged (checked cell by cell against the previous files).

## The 15 matches
| Match | Date | Fmt | Tournament | Pakistan | Afghanistan | Result | Pakistan captain | Player of the match | Bat / bowl rows |
|---|---|---|---|---|---|---|---|---|---|
| manual_1 | 2018-09-21 | ODI | Asia Cup | 258/7 | 257/6 | Won 3 wickets | Sarfraz Ahmed | Shoaib Malik | 17 / 11 |
| manual_2 | 2019-06-29 | ODI | ICC Cricket World Cup | 230/7 | 227/9 | Won 3 wickets | Sarfraz Ahmed | Imad Wasim | 20 / 12 |
| manual_3 | 2021-10-29 | T20I | ICC Men's T20 World Cup | 148/5 | 147/6 | Won 5 wickets | Babar Azam | Asif Ali | 15 / 10 |
| manual_4 | 2022-09-07 | T20I | Asia Cup | 131/9 | 129/6 | Won 1 wicket | Babar Azam | Shadab Khan | 19 / 10 |
| manual_5 | 2023-03-24 | T20I | Afghanistan v Pakistan T20I Series | 92/9 | 98/4 | Lost 6 wickets | Shadab Khan | Mohammad Nabi | 17 / 11 |
| manual_6 | 2023-03-26 | T20I | Afghanistan v Pakistan T20I Series | 130/6 | 133/3 | Lost 7 wickets | Shadab Khan | Fazalhaq Farooqi | 12 / 12 |
| manual_7 | 2023-03-27 | T20I | Afghanistan v Pakistan T20I Series | 182/7 | 116/10 | Won 66 runs | Shadab Khan | Shadab Khan | 21 / 12 |
| manual_8 | 2023-08-22 | ODI | Afghanistan tour of Sri Lanka | 201/10 | 59/10 | Won 142 runs | Babar Azam | Haris Rauf | 22 / 12 |
| manual_9 | 2023-08-24 | ODI | Afghanistan tour of Sri Lanka | 302/9 | 300/5 | Won 1 wicket | Babar Azam | Shadab Khan | 18 / 11 |
| manual_10 | 2023-08-26 | ODI | Afghanistan tour of Sri Lanka | 268/8 | 209/10 | Won 59 runs | Babar Azam | Mohammad Rizwan | 21 / 12 |
| manual_11 | 2023-10-06 | T20I | Asian Games Men's Cricket Competit | 115/10 | 116/6 | Lost 4 wickets | Qasim Akram | - | 19 / 11 |
| manual_12 | 2023-10-23 | ODI | ICC Cricket World Cup | 282/7 | 286/2 | Lost 8 wickets | Babar Azam | Ibrahim Zadran | 12 / 12 |
| manual_13 | 2025-08-29 | T20I | UAE T20I Tri-Series | 182/7 | 143/10 | Won 39 runs | Salman Ali Agha | Salman Ali Agha | 19 / 13 |
| manual_14 | 2025-09-02 | T20I | UAE T20I Tri-Series | 151/9 | 169/5 | Lost 18 runs | Salman Ali Agha | Ibrahim Zadran | 18 / 12 |
| manual_15 | 2025-09-07 | T20I | UAE T20I Tri-Series | 141/8 | 66/10 | Won 75 runs | Salman Ali Agha | Mohammad Nawaz | 21 / 11 |

## Checks (all 15 matches pass)
* Pakistan batting runs + extras = innings total, and partnership runs add up to it.
* Afghan batting runs + extras implied by the dataset score; bowlers' balls = length of the innings; bowler runs are consistent with the total.
* Fall-of-wicket rows = wickets lost; unbroken last stand = the two not-out batters.
* 11 distinct named players per side. A full rebuild from your original files reproduces the data exactly.
* All 27 dashboard pages load without errors; the Afghanistan views now show content (Head-to-Head no longer says "no scorecard data").

These are arithmetic checks. The scorecards have not been compared line by line with Cricinfo.

## Corrections and decisions
1. 24 Mar 2023 T20I: Pakistan 92/9 (scorecard), previously 92/10. `extra/missing_matches.csv` updated so a re-run keeps it.
2. 26 Aug 2023 ODI: won by 59 runs (previously flagged "6 runs?").
3. `manual_11`: one Afghan batter had innings number 7; set to 2.
4. `manual_3` and `manual_9`: bowling sheets carried the wrong innings number; set to the batting innings they bowled in.
5. Partner names in partnerships come from the batting order. The workbook's "partner" column disagreed with it for 18 wickets (10 matches), and the batting order stayed consistent for every wicket.
6. Names follow the dashboard spelling: Sarfraz Ahmed, Salman Ali Agha, Sufiyan Muqeem, Mirza Baig, Mohammad Wasim; "(c)" and "(wk)" removed. Afghan players use full names (Fareed Ahmad, Shahidullah Kamal).
7. `manual_7`: Karim Janat batted and bowled but is not in the 11 listed Afghan names (a replacement); he is kept.
8. Captains: the 15 are now `scorecard` (recorded, not inferred). Changes against the old guess: 24 Mar and 26 Mar 2023 were Shadab Khan (not Babar Azam / Mohammad Rizwan); the 2025 tri-series is Salman Ali Agha.
9. The other 466 captains are exactly as before. Re-running `build_captains.py` re-assigned 19 tied matches (for example the 2020 England T20I), so it was not re-run. The `scorecard` captains are applied as an overlay and are protected if it is run.
10. Cricinfo IDs: the workbook is not consistent. It claims every row has an ID, but the same player has different IDs in different matches (17 players). The `manual_10` and `manual_15` rows still carry the older IDs (for example Rashid Khan 79159 against 793463 in the other matches), and a few single matches differ slightly. An ID is used only when most of the player's matches agree; ties are left blank. See `extra/cricinfo_id_conflicts.csv` for each player, the IDs found and the matches they came from. Update: the 4 tied players were later checked against Cricinfo and filled (see `docs/cricinfo_audit.xlsx`); the other 13 use the majority ID.
11. Dot-ball % and boundary % are now computed only from rows that record them (`utils/splits.py`, `utils/ml.py`, `pages/5_Bowling.py`), so the new rows cannot lower players' averages. Every player's Dot % is unchanged.

## Confidence counts (from the CSV)
certain 184, scorecard 15, manual 16, solved 266, year-only 0. README and `docs/DATA_NOTES.md` are now generated from the CSV (`python scripts/regenerate_docs.py`), which also fixed the earlier disagreement.

## Still missing for these 15 matches (left empty, not estimated)
* Dot balls, over-by-over runs, deliveries and powerplay / middle / death splits. The Phase Analysis page still cannot use them.
* Runs and balls per batter inside each partnership.
* Pakistan fielding rows (the Afghan batting card names no fielder for many dismissals). Pakistan fielding totals exclude these 15 matches.
* Cricinfo IDs for 4 Afghan players (Abdul Rahman, AM Ghazanfar, Darwish Rasooli, Noor Ahmad); coaches (kept from the existing coach list).
* `manual_11` player of the match.

## Model evaluation
`python evaluate_models.py` reproduced your published numbers exactly on the old data. With the 15 matches added the numbers move by 0.001 to 0.003 (gradient boosting, yearly backtest log-loss 0.661 to 0.664); the README table was updated and the conclusion is unchanged: the predictor is only modestly better than the baseline.

## Not changed by this merge
The 2 Oct 2026 ODIs (result only), tournament-stage checks, the 2015 to 2025 spot-check, small-sample flags, weather source note, abandoned matches, and pitch / day-night / ranking / squad data are still open.
