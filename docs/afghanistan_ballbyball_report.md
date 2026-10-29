# Pakistan v Afghanistan ball-by-ball merge

Merged from `extra/afghanistan_ball_by_ball.xlsx` (ESPN structured play-by-play, sheets `Ball-by-Ball` and `Innings Coverage`) by `scripts/merge_afghanistan_ballbyball.py`.
Re-runnable: running it twice gives identical files. Run order: `merge_afghanistan_scorecards.py`, `merge_afghanistan_ballbyball.py`, `apply_ballbyball_corrections.py`, `apply_cricinfo_audit_corrections.py`, then `merge_afghanistan_ballbyball.py` once more to refresh the check list. A copy of every file that changed is in `backup_pre_ball_by_ball/`.
The scorecard sheets in the new workbook are identical, cell for cell, to `extra/afghanistan_scorecards.xlsx`, so no scorecard data changed.

## What was loaded
| Table | Change |
|---|---|
| `pak_deliveries.csv.gz` | +5,623 deliveries (15 matches, 30 innings), same columns and rules as the Cricsheet rows |
| `pak_overs.csv` | +914 over rows |
| `pak_batting` | `dot_balls`, `dot_ball_pct` filled for all 143 rows |
| `pak_bowling`, `opp_bowling` | `dot_balls` filled for all 86 + 86 rows; blank fours / sixes conceded filled from the deliveries |
| `pak_partnerships` | `balls`, `batter1_runs`, `batter2_runs` filled for all 128 stands |
| `pak_matches` | dot-ball % (both sides), powerplay / middle / death runs and wickets (both sides) filled for the 15 matches; new column `bbb_source`; `detail_level` = `ball-by-ball` |
| `pak_player_splits_*` | rebuilt (batter and bowler dot-ball % now include these matches) |

Phases: ODI overs 1-10 / 11-40 / 41-50, T20I overs 1-6 / 7-15 / 16-20. No match was rain-reduced. Dot ball rules follow the existing build (batter: faced, not a wide, nothing off the bat; bowler: legal ball, nothing off the bat; team: legal ball, no runs). Dismissed batter on a run-out is taken from the scorecard.

## Checks
* Every one of the 30 innings agrees with the source's coverage sheet: delivery count, total runs, legal balls and wickets.
* Dismissed batters in the deliveries are the same set as the batters marked out on the scorecards, in all 30 innings.
* Pakistan partnership runs from the deliveries equal the scorecard stand totals for all 128 stands.
* Powerplay + middle + death runs equal the innings total for both sides in all 15 matches.
* After the corrections, all 270 batter lines and all 174 bowler lines match (2 of them, in `manual_2`, only after a Cricinfo check showed the scorecard is right) the hand-collected scorecards on runs, balls, boundaries, wickets and extras. The rest are listed below and in `docs/afghanistan_ballbyball_checks.csv`.

## Disagreements between the deliveries and the hand-collected scorecards
27 batter / bowler lines first differed. For each case I asked which source breaks an independent check (a batter's boundaries cannot exceed his runs; the bowling card must agree with the batting card on fours and sixes; bowler runs must add up to the innings total). In 7 cases the card fails and was **corrected from the deliveries** by `scripts/apply_ballbyball_corrections.py` (44 changed values, listed in `docs/afghanistan_ballbyball_corrections.csv`):
| Match | Correction | Why |
|---|---|---|
| `manual_9` (24 Aug 2023), Pakistan batters | fours / sixes 27 / 3 to 23 / 1 | Naseem Shah's line (1 four, 2 sixes in 10 runs) is impossible; the bowling card says 23 / 1 |
| `manual_3` (29 Oct 2021), Afghan batters | 18 / 4 to 15 / 5 | the bowling card says 15 / 5 |
| `manual_12` (23 Oct 2023), Pakistan batters | sixes 6 to 9 | the bowling card says 9 |
| `manual_4` (7 Sep 2022), Afghan batters | fours 6 to 10 | the bowling card says 10 |
| `manual_14` (2 Sep 2025), Afghan bowlers | Karim Janat row replaced by Noor Ahmad (4-0-20-2) | card runs summed to 150 against 145 needed, bowler wickets to 7 against 9 needed; the card's own "dismissed by" already names Noor Ahmad for 2 wickets |
| `manual_4` (7 Sep 2022), Afghan bowlers | innings rebuilt; Azmatullah Omarzai (1 over) added | card omitted him and its runs summed to 126 against 127 needed |
Match-level totals that depend on these rows (`pak_fours`, `pak_sixes`, `pak_boundary_pct`, `opp_best_bowler`) were recomputed.

### Corrected to the Cricinfo scorecards (20 values and 1 missing row)
The 12 lines that the deliveries could not settle were then checked against the opened Cricinfo scorecard pages (audit: `docs/cricinfo_audit.xlsx`; per-cell list with URLs: `docs/cricinfo_audit_corrections.csv`; applied by `scripts/apply_cricinfo_audit_corrections.py`, before / after in `docs/cricinfo_audit_applied.csv`). Cricinfo agrees with the deliveries wherever the hand-collected card differed on balls, so the card was wrong.
| Match | What changed | Cricinfo shows |
|---|---|---|
| `manual_4` (7 Sep 2022), Pakistan innings | Fakhar Zaman balls 3 to 9, Khushdil Shah balls 6 to 3 (strike rates recomputed) | 5 (9) and 1 (3) |
| `manual_4`, Afghan innings | Azmatullah Omarzai balls 11 to 10 | 10 (10) |
| `manual_4`, Pakistan bowling | Haris Rauf wides 1 to 0, sixes conceded 0 to 1 | WD 0; the six comes from the deliveries |
| `manual_11` (6 Oct 2023), Afghan bowlers | Fareed Ahmad 3-0-15-3, Qais Ahmad 3-0-11-2 (2 wides), Zahir Khan 3-0-20-2 (1 wide), Gulbadin Naib 4-0-29-1 (3 wides); **Sharafuddin Ashraf 3-0-17-0 row added** | same figures |
| `manual_11`, Pakistan bowling | Sufiyan Muqeem wides 0 to 1, Usman Qadir wides 0 to 2 | WD 1 and WD 2 |
| `manual_14` (2 Sep 2025), Afghan bowlers | no change: Noor Ahmad 4-0-20-2 is kept | Cricinfo lists Noor Ahmad and does not list Karim Janat as a bowler |
Boundaries for the added Ashraf row (1 four, 1 six) and Haris Rauf's six are taken from the deliveries because the Cricinfo bowling card does not publish them. Match-level `pak_wides_bowled`, `pak_sixes_conceded` and `opp_best_bowling` (`manual_11`: 3/29 to 3/15) were recomputed, and the player-split tables rebuilt.

### Settled by Cricinfo: scorecard kept (2 lines)
| Match | What differs | Cricinfo shows |
|---|---|---|
| `manual_2` (29 Jun 2019) | Haris Sohail 57 balls on the card vs 56 in the deliveries; Imad Wasim 54 vs 55 | 27 (57) and 49 (54): the card is right, the deliveries are one ball off. Listed in `docs/cricinfo_verified_exceptions.csv`; the checks file marks them `Cricinfo-verified`. |
Their dot-ball % comes from the deliveries (56 and 55 balls), so it is a fraction of a point off for these two players.

Nothing is left unresolved: 504 checks, 0 failing.

### Cricinfo player IDs (21 rows)
Abdul Rahman 819507, Darwish Rasooli 819441, Noor Ahmad 1182529 and AM Ghazanfar 1326798 were a tie between two IDs in the workbook and had been left blank. They were checked against Cricinfo profile pages and filled in `opp_batting`, `opp_bowling`, `opp_fielding` and `opp_players` (`extra/cricinfo_id_conflicts.csv` updated).

## Corrections made while merging
* `manual_11` (6 Oct 2023): the card showed 0 fours and 0 sixes conceded for every bowler on both sides (placeholder zeros, the deliveries have 9 fours / 5 sixes and 7 fours / 3 sixes). Replaced from the deliveries. `pak_fours_conceded` and `pak_sixes_conceded` for that match changed from 0 to 9 and 5.
* Source players have the long ESPN names ("Mohammad Babar Azam"); 18 names were mapped to the dashboard spelling (for example Sarfraz Ahmed, Sufiyan Muqeem, Imad Wasim, Usman Shinwari).
* Two "retired not out (hurt)" events (`manual_7`, `manual_8`) are not counted as wickets, same as the Cricsheet rows.
* `scripts/build_deliveries.py` now keeps these `manual_*` delivery rows when it rebuilds the Cricsheet ones. `scripts/regenerate_docs.py`, the Data Quality page and the AI-assistant data notes (`utils/llm.py`) were updated to say these matches now have delivery-level data.

## Still missing
* Pakistan fielding rows: the feed names no fielder.
* Everything listed in the earlier report that is not about deliveries (`manual_11` player of the match, the 2 Oct 2026 ODIs, the 2015-2025 spot check).

## Not changed
`evaluate_models.py` was not re-run, so the model table in the README is as before.
