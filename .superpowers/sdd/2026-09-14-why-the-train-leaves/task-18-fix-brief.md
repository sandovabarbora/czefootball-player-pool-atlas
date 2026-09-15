# Task 18 fix round 1 — goalkeepers (review findings, all must be addressed)

Review verdict: spec ❌ / Needs changes. Fix these in `src/goalkeepers.py`, `src/fetch_keepers.py`
(if needed), i18n, tests; rerun for cze and eng; rebuild; commit.

1. **GA/90 adjustment direction (High).** `ga90_q = ga90_shrunk * league_multiplier` discounts
   goals conceded in weak leagues — the opposite of the copy ("a goal conceded in a stronger
   league counts less"). Fix: `ga90_q = ga90_shrunk / league_multiplier` (m_ENG = 1 is the
   baseline; weaker leagues' GA scale up). Add a test with a sub-1 multiplier row asserting
   `ga90_q > ga90_shrunk`. Check the copy in `ch4.gk.p`/`slide.8b.how` still matches the
   formula; adjust if not.

2. **Age at first top-9 season — censoring and depth (High).** Keeper pages are fetched
   only for previous/metrics/current, so no GK "first season" can predate 2024/25 (Pickford
   shows first_age 30 in 2024/25 — wrong). Fix: compute GK first-top-9 ages from
   `fbref_players.parquet` GK rows (`pos == "GK"`, ≥ 450 min), which reach back to 2020/21
   for the headline leagues, exactly as `pathways.export_route` does for outfield players —
   reuse its logic (or its JSON) so GK and outfield are censored identically; report a
   `censored_share` for GKs like `export_route` does, and state it in `slide.8b.how`
   ("first season in a fetched top-{topn} table; players already there in {history_start}
   are censored — {censored_pct} % of the goalkeepers, {censored_out_pct} % of the outfield
   exports"). Keeper tables stay only for GA/saves/CS (production table).

3. **One season for everything (High).** `per_million`, `club_tier`, `production_table`,
   `home_top9_gks` use the metrics season; `gk_first_top9_ages` was called with the current
   season, so the sentence's "4 goalkeepers" sat above a median computed over 3. Use the
   metrics season everywhere; the count in the sentence must equal the rows in the club-tier
   table and the n behind the median.

4. **Join keepers to the pool table (Medium).** Join `fbref_keepers.parquet` to the GK rows of
   `fbref_players.parquet` on `(league, season, team, player_key)`; log how many keeper rows
   fail to join and add the count to `data_quality.json` checks (`gk_unjoined`, unit rows)
   via `src/data_quality.py`; use the players-table `born/nation/min` as canonical.

5. **CS grammar (Medium).** `slide.8b.a`: "{n_gk} {cs_adj_pl} brankáři hrají aspoň {min}
   minut …" (nominative plural + plural verb). Re-read the other new CS strings for the same
   agreement pattern.

6. **England semantics (Low).** `slide.8b.how` gets the same `{home_note}` mechanism as slides
   4/5 when the home league is a headline league ("first top-{topn} season needs no move for
   a {home_league} keeper").

Verify: `uv run pytest -q -p no:warnings`; `NATION=cze uv run python -m src.goalkeepers &&
… src.data_quality && … src.render`; same for eng; `./site/build.sh` both; the cze sentence
count == table rows == median n; Pickford's first season now 2020/21 (censored) with the
censoring disclosed. Report the corrected numbers (cze and eng: n_gk, per million, GK vs
outfield median first-top-9 age with censored shares). Commit plain message, no AI trailer.
