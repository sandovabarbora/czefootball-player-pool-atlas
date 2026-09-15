# Task 18 report: goalkeepers — the counter-example

## Status: DONE

Commit: `5c23a68` — "Task 18: goalkeepers -- the counter-example where the pathway works"
(on top of `a82e91a`, itself on top of `3ab44e4`, branch `v1.2`)

## What was built

- `src/fetch_keepers.py`: fetches FBref keeper-stat pages (`stat_type="keeper"`) via
  `src.fetch_fbref.fetch_player_page`, normalises to `fbref_keepers.parquet`
  (`league, season, team, player, player_key, nation, born, age, mp, min, ga, saves,
  sota, save_pct, cs`). Nation-independent, previous/metrics/current seasons, every
  league in `config.leagues()`.
- `src/goalkeepers.py`: the analysis module — per-million presence, age at first
  top-9 appearance (GK vs. outfield, via `pathways._age`/`_dedupe_player_season`
  reused directly, not `pathways.json`), club tier (same goals-scored-percentile
  proxy as `pathways.fare`), a shrunk/quality-adjusted production table, and two
  card picks. Writes `goalkeepers.json` + `outputs/<nation>/gk_export_age.svg`.
- Slide 8b in `templates/report.html.j2`, a `gk-card` roster variant, a Chapter IV
  paragraph on GK shrinkage, full EN/CS i18n, Makefile targets (`keepers`,
  `goalkeepers`), `site/build.sh` + `site/svg_labels.py` + `site/enrich_index.py`
  wiring for the new figure (see "Design decisions" below).

## Design decisions worth flagging

1. **Shrinkage of save %.** The brief says "save % shrunk with exposure `sota`"
   using "the same K". `_shrink_series` (in `src/goalkeepers.py`) generalises
   `features.bayesian_shrink`'s formula so K=900 is compared against the *raw*
   exposure column either way — `min` for GA/90 and saves/90 (a phantom-minutes
   prior, same as the rest of the report), `sota` for save %. A single
   keeper-season's shots-on-target-against is typically well under 900, so the
   "well-observed" cohort is almost always empty and `save_pct_shrunk` compresses
   hard toward the league median for nearly everyone — an intentional
   consequence of a thin single-season sample relative to K, documented in the
   module docstring and in the new `ch4.gk.p` paragraph, not a bug.
2. **GK cards intentionally sit outside the outfield-card site machinery.**
   `site/enrich_index.py`'s `CARD_RE`/`TILE_ARTICLE_RE` (the collapsed-tile
   system) key off the literal `class="cycle-card"` and label a card's first
   `<dd>` as the outfield quality metric ("G+A / 90 adj.") — wiring GK cards
   into it would either mislabel GA/90 or (with `docs/modern.css`'s
   `.cycle-card > :not(.cycle-tile) { display: none }`) render them collapsed
   with nothing to open them. The `gk_card_article` macro uses `class="gk-card"`
   instead (own box styling in `templates/style.css`, same visual treatment,
   oxblood top border) — verified by screenshot on the built site, cards render
   fully and correctly, just not tile-collapsed like the outfield cards.
3. **One necessary site-file edit beyond additive list entries.**
   `site/enrich_index.py` has a five-figure regex that rewrites `../X.svg` to
   `X.svg` on the Czech page so it picks up the Czech-labelled SVG
   `svg_labels.py` writes to `docs/cs/`. Without adding `gk_export_age.svg` to
   it, the Czech page would silently show the English-labelled chart on a
   headline slide (verified this was happening, then fixed). Two other
   Chapter-IV figures — `model_comparison.svg`, `league_strength.svg` — have
   the same pre-existing gap (Czech SVG built by `svg_labels.py` but never
   linked); left alone as out of scope for this task.
4. **Export-age numbers are computed directly, not read from `pathways.json`.**
   The brief allows either; the figure needs the raw per-player ages (not just
   `export_route`'s median), so `goalkeepers.py` re-walks history with the same
   `pathways._age`/`_dedupe_player_season` helpers rather than depending on
   `pathways.main()` having already run.
5. Concurrent Task-17 review-fix work landed on `feature_eda.py`/`i18n.py`/
   `cs.yaml` while this task ran (as the brief warned) and later committed
   itself as `a82e91a`; an unrelated in-progress CSS change to `.fed-grid`/
   `.fed-tile` (federation tiles) was still sitting uncommitted in
   `templates/style.css` at commit time — staged only my `.gk-card` hunk via
   `git add -p`, left that hunk for its own owner.

## Tests

`tests/test_fetch_keepers.py` (4 tests: keeper-table parse off a trimmed real
cached page, normaliser shape/types, Performance-block mapping, missing-nation
handling) + `tests/test_goalkeepers.py` (14 tests: per-million ranking and
tie-break, minutes floor, export-age walk, club-tier join, the generalised
shrink — both the minutes-exposure case matching `bayesian_shrink`'s formula
and the sota-exposure fallback-to-cohort-median case, production table,
peer medians with a zero-count peer, home-top9 filter, NT-flag namesake-safe
match, card-rule picks, full `build_goalkeepers` JSON shape) + 2 new
`tests/test_render.py` tests (slide 8b present/absent, GK card row, Chapter IV
paragraph). Full suite: **221 passed** (`uv run pytest -q -p no:warnings`,
default `NATION=cze`), including the golden-fixture test (untouched — no key
`goalkeepers.py` touches is in its compared subset) and the real-context
render test (skipped until `goalkeepers.json` existed, green afterward).
`ruff` was not installed in this environment (`No module named ruff`) — lint
not run.

## Headline numbers

### Czechia (`NATION=cze`)

- **Per million:** 4 Czech goalkeepers ≥ 450 min in the top-9 leagues, 2025/26
  → 0.37 per million, **rank 5 of 9** (Denmark leads at 0.67; Poland/Norway/
  Austria/Hungary trail).
- **Export age:** GK median age at first top-9 season = **22** (n=3 current
  top-9 keepers with a birth year), vs. **23** for outfield exports (n=12) —
  Czech goalkeepers leave *earlier* than outfield players, the opposite of
  the train-leaves-without-them pattern chapter I-III describe.
- **Cards:**
  - *Most top-9 minutes*: **Lukáš Horníček** (Braga, POR-Primeira Liga, 2959
    min) — GA/90 1.00 (quality-adj. 0.67), saves/90 2.19, save % 66.6,
    club at 83rd percentile of league goals scored.
  - *Youngest ≥ 450 top-9 min*: **Antonín Kinský** (Tottenham, ENG-Premier
    League, 630 min) — GA/90 1.00 (quality-adj. 1.21, Premier League
    multiplier = 1.0), saves/90 1.43, save % 65.9.
- **GK production table (home, 22 rows)**: full list in
  `data/processed/cze/goalkeepers.json` → `production.home`; spans Braga/PSV/
  Ajax/Tottenham (top-9) down to the domestic CZE-First League and two in
  AUT-Bundesliga. `save_pct_shrunk` clusters tightly (65.0–68.3%), exactly the
  heavy-shrinkage effect described above.
- **Club tier (4 top-9 CZE keepers):** Horníček 83%, Kovar (PSV) 100%,
  Jaroš (Ajax) 83%, Kinský (Tottenham) 42%.

### England (`NATION=eng`)

- **Per million:** 5 English goalkeepers ≥ 450 min in the top-9 leagues →
  0.09 per million, **rank 8 of 8** (lowest of its peer set — a large
  population denominator, not a talent claim).
- **Export age:** GK median age = **26** (n=4) vs. **21** for outfield
  exports (n=150) — the *reverse* contrast of Czechia's: English goalkeepers
  arrive in the top-9 later than outfield players. The slide sentence reads
  correctly either way (no directional wording baked in).
- **Cards:**
  - *Most top-9 minutes*: **Jordan Pickford** (Everton, 3420 min) — GA/90
    1.32 (quality-adj. 1.33), saves/90 2.61, save % 66.1.
  - *Youngest ≥ 450 top-9 min*: **Aaron Ramsdale** (Newcastle, 1004 min) —
    GA/90 1.52 (quality-adj. 1.45), saves/90 2.15, save % 65.7.
- **Club tier (8 top-9 ENG keepers):** Pickford (Everton) 35%, Henderson
  (Crystal Palace) 20%, Pope (Newcastle) 65%, Johnstone (Wolves) 5%, Ramsdale
  (Newcastle) 65%, Trafford (Man City) 100%, Bentley (Wolves) 5%, Woodman
  (Liverpool) 85%.

## Verification performed

- `uv run pytest -q -p no:warnings`: 221 passed (both before and after the
  fetch/render/build steps).
- `NATION=cze uv run python -m src.fetch_keepers`: ran detached
  (~11 min, headless, 1695 rows across 18 leagues; `SVK-Super Liga` failed as
  expected — no comp_id on file, same as every other module). No leftover
  `undetected_chromedriver` processes afterward.
- `NATION=eng make share-tables`: copied `fbref_keepers.parquet` from cze (no
  refetch); `fbref_players.parquet`/`big5_history.parquet` already present.
- `src.goalkeepers` run for both nations; `src.render` + `site/build.sh` run
  for both; rebuilt `docs/index.html`, `docs/cs/index.html`, `docs/eng/index.html`
  and their atlas SVGs (all three nations' outfield-only figures also rebuilt
  as a side effect of the same render/build pass) plus `gk_export_age.svg` in
  all three locations.
- Screenshots taken via a local `python3 -m http.server` over `docs/` (Chrome
  extension refused `file://`): slide 8b + club-tier table + GK card row on
  cze/en, cze/cs (figure and cards fully translated, decimal commas correct,
  club-tier headers translated), and eng/en (reversed export-age contrast
  renders correctly). Confirmed via `enrich_index.py`'s own pass/fail output
  ("ok (en): 17 cards, 10 with portraits" / "ok (cs): 17 cards, 10 with
  portraits" for cze; "ok (en): 14 cards, 13 with portraits" for eng) that the
  outfield card count is unaffected by the new GK cards.

## Concerns / follow-ups (not blocking)

- `ruff` unavailable in this environment; only `pytest` was run as the quality
  gate.
- The pre-existing Czech-SVG-not-linked gap for `model_comparison.svg` and
  `league_strength.svg` (same root cause I fixed for `gk_export_age.svg`) is
  still there — out of scope for this task, flagged for whoever owns that area
  next.
- GK cards do not get the collapsed-tile/portrait treatment the outfield
  roster does (design decision #2 above); if a future task wants visual
  parity, it will need either a GK-aware branch in `enrich_index.py`'s tile
  logic (to avoid the metric-label bug) or a fetched keeper photo set.
