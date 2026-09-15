# `infra/bigquery/` — the processed tables as a BigQuery contract

This report's `data/processed/<nation>/` tables are flat parquet, one row
per entity — nothing here is specific to the pandas/Jinja2 pipeline that
produces them. This directory is that contract, for anyone who wants the
tables in a warehouse instead: generated JSON schemas, a load script, and a
key/type/unit contract for the model-output JSONs the tables don't cover.
See the root [`README.md`](../../README.md#portability) for how this fits
the rest of the pipeline.

## The tables

| Table | Grain | Key |
|---|---|---|
| `fbref_players` | one row per (player, club, season, league) | `player_key`, `league`, `season` |
| `features_FW` / `features_MF` / `features_DF` | one row per (player, season) within that position group, after the minutes floor | `player_key`, `season` |
| `per_capita` | one row per country | `country` |
| `cohorts` | one row per (country, position group, age cohort) | `country`, `pos_group`, `cohort` |
| `trajectory_FW` / `trajectory_MF` / `trajectory_DF` | one row per player with a metrics-vs-previous-season delta, within that position group | `player_key` |
| `big5_history` | one row per (player, club, season, league), Big-5 leagues, full season history | `player_key`, `league`, `season` |
| `fbref_keepers` | one row per (goalkeeper, club, season, league) | `player_key`, `league`, `season` |

`fbref_players` and `big5_history` share a schema (the same raw FBref
season-table columns); `features_*` adds the derived per-90/shrunk/quality
columns (see chapter IV, "From raw tables to a feature vector" and
"Bayesian shrinkage" in the report itself) on top of that. A player who
transferred mid-season has one row per club in `fbref_players`/
`big5_history` and in `features_*` before the render step's own
`collapse_player_seasons` step — this contract ships the pre-collapse
table, so a consumer doing player-season aggregation should dedupe the same
way (`src/utils.py::collapse_player_seasons`).

## Schemas

`infra/bigquery/schema/<table>.json` is a generated BigQuery JSON schema
(`[{name, type, mode}, ...]`) for each table above, built by
`make_schemas.py` from the parquet files' own pandas dtypes:

```bash
uv run python infra/bigquery/make_schemas.py --nation cze
```

Committed, so a downstream consumer can `bq mk --table --schema=...` or
validate a load without running this pipeline. Every field is `NULLABLE` —
pandas' own nullable dtypes (`Int64`, optional feature columns) already say
which columns can be null; a `REQUIRED` field here would be a promise this
pipeline's dtypes don't back up on every nation's data.

## Loading

```bash
infra/bigquery/load.sh [-n] <dataset> <nation>
```

One `bq load --source_format=PARQUET --replace <dataset>.<table>
data/processed/<nation>/<table>.parquet` per table (parquet is
self-describing, so no `--schema` flag is needed to load it — the schema
files above are for table creation or an explicit override instead).
`-n` prints the commands without running them:

```bash
infra/bigquery/load.sh -n demo cze
```

The default table list is the eight tables above minus the three
`trajectory_*` ones (season-to-season deltas, derived from `features_*`,
pipeline-internal rather than part of the delivered dataset); their schemas
are still generated and committed for a consumer who wants them.

## Model-output contract

The eight model JSONs (`league_strength`, `model_comparison`,
`series_model`, `youth_panel`, `gap_decomposition`, `goalkeepers`,
`squad_lens`, `pathways`) are nested model summaries, not flat tables —
`load.sh` does not load them. `infra/bigquery/model_outputs.md`, generated
by `make_contract.py`, documents their top-level keys, types, units and the
season/nation each file describes:

```bash
uv run python infra/bigquery/make_contract.py --nation cze
```

Re-run both generators after a pipeline change touches a table's columns or
a model's output shape; both are committed rather than built at
report-render time, so the contract itself is versioned in git history.
