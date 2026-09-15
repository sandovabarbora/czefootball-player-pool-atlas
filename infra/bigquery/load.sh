#!/usr/bin/env bash
# infra/bigquery/load.sh -- load the processed parquet tables into BigQuery.
#
# usage: infra/bigquery/load.sh [-n] <dataset> <nation>
#   -n         dry run: print the bq load commands, don't run them
#   <dataset>  BigQuery dataset name to load into (must already exist)
#   <nation>   NATION the tables were built for (cze | eng); picks
#              data/processed/<nation>/*.parquet as the source
#
# One `bq load --source_format=PARQUET --replace <dataset>.<table>
# data/processed/<nation>/<table>.parquet` per table (parquet is
# self-describing, so no --schema flag is needed to load it; the committed
# infra/bigquery/schema/<table>.json files are there for a `bq mk --table
# --schema=...` create-without-load, or for a caller who wants an explicit
# schema instead of BigQuery's auto-detection).
#
# The eight tables below are the ones infra/bigquery/README.md and this
# report describe as the delivered dataset. trajectory_FW/MF/DF also have
# committed schemas (infra/bigquery/schema/trajectory_*.json, from
# make_schemas.py) for a caller who wants them, but are season-to-season
# deltas derived from features_* -- pipeline-internal, not loaded here by
# default; pass them as extra <table> names to `bq load` yourself if needed.
#
# example: infra/bigquery/load.sh -n demo cze     (prints eight commands)
#          infra/bigquery/load.sh football_atlas cze
set -euo pipefail

usage() { echo "usage: $(basename "$0") [-n] <dataset> <nation>" >&2; }

DRY_RUN=0
while getopts "n" opt; do
  case "$opt" in
    n) DRY_RUN=1 ;;
    *) usage; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

if [ $# -ne 2 ]; then
  usage
  exit 2
fi
DATASET="$1"
NATION="$2"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA_DIR="$ROOT/data/processed/$NATION"

TABLES=(fbref_players features_FW features_MF features_DF per_capita cohorts big5_history fbref_keepers)

for t in "${TABLES[@]}"; do
  SRC="$DATA_DIR/$t.parquet"
  CMD=(bq load --source_format=PARQUET --replace "${DATASET}.${t}" "$SRC")
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '%q ' "${CMD[@]}"; printf '\n'
    continue
  fi
  [ -f "$SRC" ] || { echo "missing $SRC -- run \`make render\` (or restore-snapshot) first" >&2; exit 1; }
  printf '%q ' "${CMD[@]}"; printf '\n'
  "${CMD[@]}"
done
