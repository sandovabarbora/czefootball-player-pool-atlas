# Task 18 fix round 1 report: goalkeepers — the counter-example

## Status: DONE

Commit: `a9051a1` — "Task 18 fix round 1: goalkeepers chapter review findings" (branch `v1.2`,
on top of `5393890`)

## What was fixed (all six review findings)

1. **GA/90 direction.** `ga90_q = ga90_shrunk / league_multiplier` (was `*`); `m_ENG = 1` is
   the baseline, weaker leagues' GA now scales up. Copy in `ch4.gk.p` already matched the
   intended (division) direction, so it was left as-is; `slide.8b.how` didn't mention the
   multiplier at all and needed no change on this point.
2. **Age at first top-9 season — censoring and depth.** The export-age walk now reads
   `fbref_players.parquet`'s `pos == "GK"` rows (back to 2020/21) instead of
   `fbref_keepers.parquet` (previous/metrics/current only). A first top-9 appearance already
   in the earliest fetched season is `censored`, using the exact same `first_hist` reference
   `pathways.export_route` uses for outfield exports, so a goalkeeper and an outfield export
   censored on the same season count the same way. `slide.8b.how` now states both censored
   shares.
3. **One season for everything.** `per_million`, `club_tier`, `production_table`,
   `home_top9_gks`, and now `gk_first_top9_ages` all key off `metrics_season`; every exhibit
   is built from one shared `home_top9_gks` roster so the sentence's `n_gk`, the club-tier
   table's row count and the export-age median's `n` are the same number by construction.
   `build_goalkeepers` dropped the separate `current_season` parameter (unused once every
   exhibit uses `metrics_season`).
4. **Join keepers to the pool table.** New `join_keeper_pool(keepers, players_all)` joins
   `fbref_keepers.parquet` to the GK rows of `fbref_players.parquet` on
   `(league, season, team, player_key)`; the players table's `born`/`nation`/`min` are
   canonical. Unjoined rows are dropped and the count is logged; `src/data_quality.py` gained
   a new recomputed check, `gk_unjoined` (reruns `join_keeper_pool` itself, not a separate
   approximation of it).
5. **CS grammar.** `slide.8b.a`: "brankářů hraje" (genitive plural + singular verb) → "brankáři
   hrají" (nominative plural + plural verb). Re-read every other new GK Czech string
   (`gk.tier.summary`, `ch3.gk.kicker`, `ch4.gk.p`, card/table labels) — none of the others pair
   a numeral with a noun+verb, so none had the same defect.
6. **England semantics.** `slide.8b.how` gained the same `{home_note}` mechanism slides 4/5
   use, new key `slide.8b.home_note`, shown only when `domestic_league_code in headline_leagues`.

## Tests

`uv run pytest -q -p no:warnings` (default `NATION=cze`): **229 passed**. New/changed tests:
- `tests/test_goalkeepers.py`: `join_keeper_pool` canonical-fields + unjoined count (item 4);
  a sub-1-multiplier row asserting `ga90_q > ga90_shrunk` (item 1); the GK age walk finding a
  2020/21 first season and flagging it censored from `fbref_players.parquet`-shaped input,
  which the old keeper-page-only walk could never see (item 2); `build_goalkeepers`'s
  `n_gk == len(club_tier) == export_age.gk_n` invariant on toy data (item 3); updated
  `club_tier`/`gk_first_top9_ages`/`build_goalkeepers` call sites for the new signatures.
- `tests/test_data_quality.py`: `gk_unjoined` present-but-null with no keepers table, and a
  toy join with one deliberately unjoined row.
- `tests/test_render.py`: `slide.8b.how` states both censored shares and drops `home_note`
  when the home league isn't a headline league, gains it (`"needs no move"`) when it is; the
  Czech `slide.8b.a` render contains "brankáři hrají" and never "brankářů hraje".

## Corrected headline numbers

### Czechia (`NATION=cze`)

- **Per million:** 4 Czech goalkeepers ≥ 450 min in the top-9 leagues, 2025/26 → 0.37 per
  million, **rank 5 of 9**. `n_gk` (4) == club-tier table rows (4) == export-age median `n`
  (4) — the round-1 desync is gone.
- **Export age:** GK median age at first top-9 season = **22.5** (n=4, **0 % censored** —
  none of the four's first top-9 season is 2020/21), vs **23** for outfield exports (n=19,
  21 % censored). Earliest first seasons: Horníček 2021/22, Kinský 2025/26, Jaroš 2024/25,
  Kovář 2023/24 — all inside the fetched window, so none needed the censoring flag (the bug
  this round fixed mainly hit England, see below).
- **GA/90 quality adjustment (division, item 1):** Horníček (Braga, POR-Primeira Liga,
  multiplier 0.63) ga90 1.00 → **ga90_q 1.70** (inflated, weaker league); Kinský (Tottenham,
  ENG-Premier League, multiplier 1.0, the baseline) ga90 1.00 → ga90_q 1.21 (unchanged by the
  fix, since dividing/multiplying by 1.0 is the same).
- **Data quality:** `gk_unjoined` = 12 of 1695 keeper rows (fbref_keepers.parquet is
  nation-independent, so this count is shared with England's run).

### England (`NATION=eng`)

- **Per million:** 5 English goalkeepers ≥ 450 min in the top-9 leagues → 0.09 per million,
  **rank 8 of 8**. `n_gk` (5) == club-tier rows (5) == export-age median `n` (5).
- **Export age:** GK median age = **26** (n=5, **100 % censored** — all five: Ramsdale,
  Henderson, Pickford, Johnstone, Pope — already appear in 2020/21, the earliest fetched
  season, so their true first top-9 season is unknown and the number is now honestly flagged
  rather than presented as measured) vs **21** for outfield exports (n=200, 40.5 % censored).
  This is exactly the case item 2 targeted: the old keeper-page-only walk could never see past
  2023/24 and silently reported some more-recent, wrong "first" season for established
  internationals like Pickford; the fix surfaces the true situation (unknown, censored)
  instead.
- **GA/90 quality adjustment:** all English top-9 keepers play in the ENG-Premier League
  itself (multiplier 1.0, the baseline), so `ga90_q` is numerically unchanged by the
  multiply→divide fix for this nation's cards (Pickford ga90 1.32 → ga90_q 1.33; Ramsdale
  ga90 1.52 → ga90_q 1.45).
- **`slide.8b.how` home_note (item 6):** now reads "…a comparison of two pathways inside one
  nation, not a causal claim. First top-9 season needs no move for a Premier League keeper."
  — present for England (Premier League is a headline league), absent for Czechia.
- **Data quality:** `gk_unjoined` = 12 of 1695 keeper rows (same shared table as Czechia).

## Concerns / follow-ups (not blocking)

- `ruff` is still not installed in this environment; only `pytest` was run as the quality gate
  (same limitation noted in the original task-18-report).
- `gk_unjoined` = 12 rows is nonzero but small relative to 1695; not investigated further here
  since the brief only asked for the count to be logged, not root-caused. A future pass could
  check whether those 12 are a specific team-naming mismatch pattern.
- The pre-existing gap where `model_comparison.svg`/`league_strength.svg` have no linked
  Czech-labelled SVG (flagged in the original task-18-report) is still there — out of scope
  for this fix round.
