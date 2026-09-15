# Task 18: Goalkeepers — the counter-example (spec §3)

**Football question:** "The one position where Czech players leave young and sit at big
clubs is the one where the pool holds up — what is different there?" Analytical: GK
presence per million in the top-9 leagues, age at export of GK vs outfield exports,
club tier, and a GK production table — all descriptive.

**Nation-aware:** everything through config; England's version reads about English
keepers (Pickford, Henderson, …) with its own peers.

## A. Data: keeper tables
- `src/fetch_fbref.fetch_player_page(league, season, "keeper")` exists (page segment
  `keepers`). New module `src/fetch_keepers.py` → `data/processed/<nation>/fbref_keepers.parquet`
  with columns `league, season, team, player, player_key, nation, born, age, mp, min,
  ga, saves, sota, save_pct, cs` (map from soccerdata's `Performance` block: GA, SoTA,
  Saves, Save%, CS; check the actual column tuples on one cached page and record them).
  Seasons: previous, metrics, current for every league in `config.leagues()` (as
  `fetch_fbref.main` does, minus history). Headless; cached pages under soccerdata's
  dir; nation-independent → Makefile `share-tables` copies it for the second nation.
- GK rows in `fbref_players.parquet` (`pos == "GK"`) already carry minutes/born/nation;
  join on `(league, season, team, player_key)`.

## B. Module `src/goalkeepers.py` → `data/processed/<nation>/goalkeepers.json` + figure
1. **Per million**: distinct GKs with ≥ 450 min in headline leagues per peer country,
   metrics season (same rule as outfield per-capita), with the home nation's rank.
2. **Age at export**: for the home nation, every GK with a top-9 season since the
   earliest fetched season — age at *first* top-9 season, vs the same for outfield
   exports (`export_route` data: reuse `pathways.export_route` logic or its JSON for
   the home country's `median_export_age`); report medians and n; also the age at
   which each current top-9 home GK first appeared in a top-9 table.
3. **Club tier**: for the home nation's top-9 GKs in the metrics season: club, league,
   minutes, and the club's goals-scored percentile (the same club-strength proxy the
   pathways use) — a small table.
4. **GK production table**: per GK (home nation, metrics season, ≥ 450 min): GA/90,
   saves/90, save %, clean-sheet share, shrunk toward the league median with the same
   K (`bayesian_shrink` on rates with exposure `min/90`; save % shrunk with exposure
   `sota`), quality-adjusted with the league multiplier for GA/90 only (a goal against in
   a stronger league counts less: `ga90_q = ga90_shrunk × m_L`); peer medians per
   country for the same columns.
5. **Two GK cards by rule**: (a) most top-9 minutes among home GKs; (b) youngest home
   GK with ≥ 450 top-9 minutes. Card body = the GK table row + club tier + the NT flag
   (nt_flags covers GKs). Reuse the card markup minus the outfield-only blocks
   (cluster/trajectory/analogs) — a `gk-card` variant.
6. Figure `outputs/<nation>/gk_export_age.svg`: strip plot of age at first top-9
   season, GK vs outfield, home nation, with medians marked.

## C. Report
New **slide 8b** — the counter-example — between "How do {a} and {b} do it?" and "Who
are the players?": question "Where does it work: goalkeepers?" (CS "Kde to funguje:
brankáři?"), answer sentence: "{n_gk} {adj} goalkeepers play ≥ {min} minutes in the
top-{topn} leagues ({pm} per million, rank {rank} of {n}); they first appeared there at
a median age of {gk_age}, against {out_age} for outfield exports." Proof: the strip
plot + the club-tier table (folded). How-line: data + rule + "a comparison of two
pathways inside one nation, not a causal claim". Cards in the roster under a kicker
"Goalkeepers — most top-9 minutes · youngest in the top-{topn}". Chapter IV: one
paragraph on GK metrics and their shrinkage. All EN + CS, numbers via placeholders.
For England the same slide reads about English keepers; if the GK export-age contrast
is absent (both near the same age), the sentence still reads correctly.

## D. Tests
`tests/test_goalkeepers.py`: keeper-table normaliser on a fixture built from one cached
keepers page (trim to ≤ 100 KB, commit under `tests/fixtures/`); per-million + rank on a
toy; export-age extraction; shrinkage with exposure `sota`; JSON shape; card rules.

## Verify
`uv run pytest -q -p no:warnings`; `NATION=cze uv run python -m src.fetch_keepers`
(headless; detached with a bounded until-loop if > 10 min); `NATION=eng make share-tables`
then `src.goalkeepers` for both; render + build both; screenshots (one tab, close it).
Commit plain message, no AI trailer; add src/config/templates/tests/fixtures + rebuilt
docs + snapshots (+ `fbref_keepers.parquet` in both snapshots); never data/processed,
outputs, data/raw.
