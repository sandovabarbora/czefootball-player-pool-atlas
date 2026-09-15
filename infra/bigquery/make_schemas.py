"""Generate BigQuery JSON schemas from the processed parquet tables (Task 21b).

Reads `data/processed/<nation>/<table>.parquet` for the eleven tables this
report's `infra/bigquery/` contract documents, maps each column's pandas
dtype to a BigQuery column type, and writes one schema file per table to
`infra/bigquery/schema/<table>.json` -- the flat `[{name, type, mode}, ...]`
shape `bq load --schema=<file>` / `bq mk --table --schema=<file>` accept
directly. The generated files are committed (`infra/bigquery/README.md`
explains why: so a downstream consumer can create or validate a table
without a working pandas/parquet toolchain).

Column shapes are stable across nations (same pipeline, same dtypes), so
this only needs to run once, for `NATION=cze`; a schema drift for another
nation would show up as a difference in the *data*, not the column types.

usage: uv run python infra/bigquery/make_schemas.py [--nation cze]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"

# The processed tables this contract covers (Task 21 brief): the player pool,
# the three position groups' feature and trajectory tables, the two
# country-level benchmark tables, the 26-season Big-5 history table and the
# goalkeeper table.
TABLES = [
    "fbref_players",
    "features_FW", "features_MF", "features_DF",
    "per_capita",
    "cohorts",
    "trajectory_FW", "trajectory_MF", "trajectory_DF",
    "big5_history",
    "fbref_keepers",
]


def bq_type(dtype: object) -> str:
    """One pandas column dtype -> one BigQuery standard-SQL column type.

    Covers the dtypes these tables actually carry (plain and pandas-nullable
    ints, floats, bools, and both plain-`object` and `string[python]` text
    columns); anything else falls back to STRING, BigQuery's safest type for
    an unrecognised column rather than a load-time guess.
    """
    if pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(dtype):
        return "INTEGER"
    if pd.api.types.is_float_dtype(dtype):
        return "FLOAT"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    return "STRING"


def schema_for(df: pd.DataFrame) -> list[dict[str, str]]:
    """`df`'s columns, in frame order, as a BigQuery JSON schema.

    Every field is NULLABLE: pandas' own nullable dtypes (`Int64`, the
    pool's optional columns) already say which columns *can* be null, but a
    NOT NULL column here would be a schema promise this pipeline's dtypes
    don't actually back up on every nation's data.
    """
    return [{"name": col, "type": bq_type(df[col].dtype), "mode": "NULLABLE"} for col in df.columns]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nation", default="cze", help="NATION the tables were built for (default: cze)")
    args = ap.parse_args()

    processed = ROOT_DIR / "data" / "processed" / args.nation
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for table in TABLES:
        path = processed / f"{table}.parquet"
        if not path.exists():
            print(f"skip {table}: {path} not found", file=sys.stderr)
            continue
        df = pd.read_parquet(path)
        schema = schema_for(df)
        out_path = SCHEMA_DIR / f"{table}.json"
        out_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path.relative_to(ROOT_DIR)} ({len(schema)} columns, {len(df)} rows)")
        written += 1

    if written == 0:
        raise SystemExit(f"no tables found under data/processed/{args.nation}/ -- nothing written")


if __name__ == "__main__":
    main()
