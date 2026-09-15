# Task 14a: The home nation becomes configuration (backend only)

Goal: the pipeline runs for any home nation selected by `NATION=<code>` (default
`cze`), with all nation-specific inputs in `config/nations/<code>.yaml`, all processed
outputs under `data/processed/<code>/` and `outputs/<code>/`, and **the Czech run
byte-identical to today** (same JSON/parquet content for `NATION=cze`).

## config/nations/cze.yaml (create; values = what the code hardcodes today)
```yaml
code: CZE                      # FBref nation code
name: Czechia                  # country name (English), matches countries.yaml
adjective: Czech
population_m: 10.90
fbref_country_page: https://fbref.com/en/country/players/CZE/Czechia-Football-Players
fbref_country_cache: country_cze.html
wikidata_citizenship: Q213     # P27 value for the photo query
domestic_league: CZE-First League
peers: [SVK, AUT, HUN, POL, CRO, DEN, SUI, NOR]    # countries.yaml codes, home nation excluded
cohort_countries: [CZE, SVK, AUT, HUN, POL, CRO, DEN, SUI, NOR]   # today's COHORT_COUNTRIES order
series_contrast: [DEN, CRO]    # thin contrast lines in the Big-5 series
squads:                        # moved verbatim from config/squads.yaml
  nt_core_event: "2026 FIFA World Cup"
  events: [...]
  peer_squads: [...]
```
and `config/nations/eng.yaml`:
```yaml
code: ENG
name: England
adjective: English
population_m: 57.7             # ONS mid-2023 estimate, England only — cite in a comment
fbref_country_page: https://fbref.com/en/country/players/ENG/England-Football-Players
fbref_country_cache: country_eng.html
wikidata_citizenship: Q145     # United Kingdom (English footballers carry P27 = Q145)
domestic_league: ENG-Premier League
peers: [FRA, GER, ESP, ITA, NED, POR, BEL]
cohort_countries: [ENG, FRA, GER, ESP, ITA, NED, POR, BEL]
series_contrast: [FRA, GER]
squads:
  nt_core_event: "2026 FIFA World Cup"
  events:
    - {team: A, event: "UEFA Euro 2024", year: 2024, url: "https://en.wikipedia.org/wiki/UEFA_Euro_2024_squads", section: "England"}
    - {team: A, event: "2026 FIFA World Cup", year: 2026, url: "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads", section: "England"}
    - {team: U21, event: "UEFA European Under-21 Championship 2025", year: 2025, url: "https://en.wikipedia.org/wiki/2025_UEFA_European_Under-21_Championship_squads", section: "England"}
  peer_squads:
    - {country: FRA, section: "France"}
    - {country: GER, section: "Germany"}
    - {country: ESP, section: "Spain"}
    - {country: ITA, section: "Italy"}
    - {country: NED, section: "Netherlands"}
    - {country: POR, section: "Portugal"}
    - {country: BEL, section: "Belgium"}
```
`config/countries.yaml` gains the seven England peers (name, population_m — Eurostat
2024, same source as the existing rows; cite the values in the file comment).
`config/squads.yaml` is deleted (contents moved into `nations/cze.yaml`).

## src/config.py
- `NATION = os.environ.get("NATION", "cze").lower()`; `nation() -> dict` loads
  `config/nations/<NATION>.yaml` (fail loudly if missing); `HOME = nation()["code"]`.
- `PROCESSED_DIR = DATA_DIR / "processed" / NATION`; `OUTPUTS_DIR = ROOT / "outputs" / NATION`;
  `SNAPSHOT_DIR = DATA_DIR / "snapshot" / NATION`. **Migration:** `git mv data/snapshot/*`
  → `data/snapshot/cze/`; `Makefile` `restore-snapshot`/`snapshot` use the nation dirs;
  `make` targets accept `NATION` from the environment (document in Makefile header).
- `PEER_COUNTRIES` / `COHORT_COUNTRIES` come from `nation()`; `DOMESTIC_LEAGUE` from
  `nation()["domestic_league"]`; `config.squads()` returns `nation()["squads"]`.
- Raw FBref tables (`fbref_players.parquet`, `big5_history.parquet`) are nation-independent
  but live under the nation dir for simplicity — `make fetch` for `eng` may symlink or copy
  `data/processed/cze/fbref_players.parquet` (add a Makefile target `share-tables` that
  copies the two parquet files from `cze` to the current nation when absent — no refetch).

## Modules (replace every literal)
- `pool.py`: `COUNTRY_URL`/cache name from `nation()`; `tables.nation == HOME`;
  `club_current` skips the nation's own name (`nation()["name"]`).
- `features.py`: column stays named `czech_eligible`? **No — rename to `home_eligible`**
  everywhere (features, pathways, sensitivity, historical_analogs, data_quality, render,
  tests); the CS/EN copy is unaffected (the column name is internal).
- `fetch_squads.py`: `.assign(country=HOME)`; events from `config.squads()`.
- `fetch_photos.py`: `wdt:P27 wd:{citizenship}`; cache dir per nation.
- `squad_lens.py`, `pathways.py`: `{cfg["domestic"]: HOME}` → `{DOMESTIC_LEAGUE: HOME}`.
- `international_benchmark.py`: `"CZE"` → `HOME`; heatmap highlight row = HOME.
- `data_quality.py`: country page cache name and nation from config.
- `big5_series.py`: `"CZE"` → `HOME`; contrast lines from `series_contrast`; labels
  use `nation()["name"]`.
- `render.py`: every `"CZE"` → `config.HOME` (39 places); `_current_club`, hero, findings,
  peer-compare (`countries=[HOME] + nation().get("compare", peers[:2])` — add
  `compare: [NOR, DEN]` to cze.yaml and `compare: [FRA, ESP]` to eng.yaml); `repo_url`
  unchanged. Keep i18n strings untouched in this task (Task 14b does copy).
- `historical_analogs.py`, `sensitivity.py`: `home_eligible`.
- `site/build.sh`, `site/enrich_index.py`, `site/svg_labels.py`, `site/atlas_meta.py`:
  accept `NATION`; site output dir = `docs/` for `cze`, `docs/<nation>/` otherwise;
  `outputs/<nation>/…` as source; `site/players.json` → `site/players.<nation>.json`;
  `docs/img/players/` shared (fbref ids are global).

## Tests
- `tests/test_config.py`: `NATION` env selects the file; `nation()["code"]` for cze/eng;
  dirs contain the nation segment.
- Golden test: with `NATION=cze` and the snapshot restored, `python -m src.render`
  produces `outputs/cze/index.html` whose tag-stripped text equals the text of the
  current `docs/index.html` **minus** site-layer additions — simpler and sufficient:
  assert `build_context(load_data())` for cze yields the same `hero`, `per_capita`,
  `cards` (player keys + reasons), `squad_lens.rows`, `peer_compare` as a JSON fixture
  you capture from the current main **before** refactoring (write the fixture first,
  commit it as `tests/fixtures/context_cze_golden.json`, then refactor until it passes).
- Existing tests updated for `home_eligible` and nation dirs; `uv run pytest -q -p no:warnings` green.

## Verify
`NATION=cze make restore-snapshot && NATION=cze uv run python -m src.render` → identical
context (golden test). `NATION=eng uv run python -c "from src import config; print(config.nation()['name'], config.PROCESSED_DIR)"` → England, `data/processed/eng`.
No fetch for England in this task. Commit plain message, no AI trailer.
