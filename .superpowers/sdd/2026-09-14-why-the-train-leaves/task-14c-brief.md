# Task 14c: The England run — data, pipeline, site at /eng/

Everything nation-specific is now config (14a) and copy (14b). This task fetches
England's inputs, runs the pipeline with `NATION=eng`, builds `docs/eng/`, and reads
the result critically before it ships.

## Data (all headless; no browser window)
1. `NATION=eng make share-tables` — copies the two league tables from cze (no refetch).
2. `NATION=eng uv run python -m src.pool` — FBref country page
   `https://fbref.com/en/country/players/ENG/England-Football-Players` (thousands of
   entries; the parser is the same). Expect the "active players sharing a normalised
   name" warning to be long — record the count; `pick_born` disambiguation by club must
   still apply. Report the pool size and how many have metrics.
3. `NATION=eng uv run python -m src.fetch_squads` — Euro 2024, WC 2026, U21 2025 sections
   "England"; peer squads FRA GER ESP ITA NED POR BEL from the WC page (skip any not at
   the tournament with a warning, as the code does).
4. `NATION=eng uv run python -m src.fetch_photos` — Wikidata P27 = Q145 + P106 footballer,
   then the Wikipedia pass; England's pool is large — cap the Wikipedia second pass at
   players who appear on cards or in the player index (those with metrics), not the
   whole country page (add a `--only-with-metrics` flag or make it the default when the
   pool exceeds 1 000; say which).
5. `NATION=eng make features reduce benchmark analogs sensitivity pathways`
   (`reduce` runs reduce+cluster+trajectory; check the Makefile), then
   `NATION=eng uv run python -m src.squad_lens && … src.big5_series && … src.data_quality && … src.render`.
6. `NATION=eng ./site/build.sh` → `docs/eng/index.html`.

## Read it before it ships (write this into the report)
- Per-capita: English players with ≥ 450 min in the top-9 leagues per million vs
  FRA GER ESP ITA NED POR BEL — and say what the number means when the home league is
  one of the nine (most English players never leave).
- Exhibits A–F for England: which ones carry meaning, which degenerate (e.g. export
  route when "abroad" ≈ 8 leagues), and whether the copy (14b) says so.
- Cards: 17-ish by the same six rules — do the rules produce sensible English names
  (e.g. rule (c)/(d) NT core by top-9 vs *domestic* minutes coincide when domestic = PL:
  if the two rules pick the same player the fall-through will show the next one — is
  that acceptable or should rule (d) be skipped when the domestic league is in the
  headline set? **Ruling to apply: skip rule (d) when `domestic_league` ∈ headline
  leagues** — implement in `historical_analogs.showcase_ids`, keep cze unchanged).
- Big-5 series for England: obviously dominated by the Premier League — the series
  panel should still read (contrast lines FRA, GER).
- Cluster reads: computed examples name English players; check three.
- Data-quality log and the credibility line: England's own counts.
- Any English "Czech" leakage or CS toggle on the eng page.

## Snapshot & site
- `NATION=eng make snapshot` → `data/snapshot/eng/` committed (parquet + json).
- `docs/eng/` committed; `site/players.eng.json` committed; photos in `docs/img/players/`.
- The cze page's top bar switch (14b) links to `/eng/`; verify both directions.

## Verify
`uv run pytest -q -p no:warnings` green (add a test that `showcase_ids` skips rule (d)
when the domestic league is headline); both `docs/index.html` and `docs/eng/index.html`
build; screenshots (one tab, close it) of the eng hero, slide 1, slide 6 and slide 8.
Commit plain message, no AI trailer.
