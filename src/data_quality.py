"""Data-quality log: recomputed wrangling checks + the recorded incident log.

Chapter IV carries two things side by side:

- Seven checks recomputed from the processed data on every run, so "how many
  rows did this drop" always matches whatever is on disk right now, not a
  number typed once and left to rot.
- A small dated list of pipeline incidents, recorded by hand in
  `config/data_quality_events.yaml` when they happened. Those dates and
  counts are historical facts a fresh run cannot reproduce (the bug that
  caused them is fixed); the template labels them "recorded" rather than
  presenting them as computed.

Run standalone: `python -m src.data_quality` reads the processed pool,
tables, features and nt_flags, plus the cached FBref country page when
present, and writes `data/processed/data_quality.json`
(`{"checks": [...], "events": [...]}`), which `render.py` reads (tolerating
its absence -- the section is then skipped, see `render.load_data`).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from src import config
from src.goalkeepers import join_keeper_pool
from src.logging_setup import setup as logging_setup
from src.pool import is_feminine_surname
from src.utils import collapse_player_seasons, normalize_name, read_parquet

LOG = logging.getLogger(__name__)

# soccerdata's own cache location for the FBref country page (see
# `src.pool.fetch_country_page`: `fb.data_dir / nation()["fbref_country_cache"]`,
# where `fb.data_dir` resolves to `~/soccerdata/data/FBref/`). Read directly
# rather than instantiating `soccerdata.FBref` -- this module never touches
# the network.
COUNTRY_PAGE_CACHE = Path.home() / "soccerdata" / "data" / "FBref" / config.nation()["fbref_country_cache"]

GROUPS = ("FW", "MF", "DF")
_PLAYER_LINK = re.compile(r"^/en/players/[0-9a-f]{8}/")


def _women_filtered_count(html: str) -> int:
    """Country-page entries dropped by the -ová feminine-surname heuristic.

    Mirrors the drop condition inside `pool.parse_country_page` exactly (a
    player anchor found, then `is_feminine_surname` on its link text) rather
    than diffing total-anchors against the parsed frame's length -- the
    latter also swallows entries `parse_country_page` drops for other
    reasons (an unparsable span, a duplicate fbref_id) and would overcount.
    """
    soup = BeautifulSoup(html, "lxml")
    count = 0
    for p in soup.find_all("p"):
        a = p.find("a", href=_PLAYER_LINK)
        if a is not None and is_feminine_surname(a.get_text(strip=True)):
            count += 1
    return count


def _split_seasons_count(features_by_group: dict[str, pd.DataFrame]) -> int:
    """Player-season-group rows collapsed by `collapse_player_seasons`, summed
    across the feature frames given (a mid-season transfer leaves two rows for
    one player_key/season/pos_group; see `utils.collapse_player_seasons`).

    `rate_cols=[]` is deliberate: the resulting row *count* depends only on
    `key_cols` group sizes, not on which columns get a weighted mean versus
    taken from the highest-minutes row, so an empty list is a safe, schema-
    agnostic way to get that count without needing this module to know the
    feature frame's rate-column names.
    """
    total = 0
    for df in features_by_group.values():
        if df.empty:
            continue
        collapsed = collapse_player_seasons(df, rate_cols=[])
        total += len(df) - len(collapsed)
    return total


def _nt_unmatched_count(nt_flags: pd.DataFrame, features_by_group: dict[str, pd.DataFrame]) -> int:
    """`nt_flags` rows (squad-table call-ups) that match no Czech-eligible row
    in any features frame.

    Mirrors `features._attach_flags`'s own join (normalised name, requiring
    birth year to match when both sides carry one) so the count reflects
    exactly the join that decides `nt_flag` -- just inverted, counting the
    nt_flags rows nothing on the features side matched instead of the
    features rows nt_flags matched.
    """
    frames = []
    for df in features_by_group.values():
        if df.empty:
            continue
        f = df.copy()
        if "player_norm" not in f.columns:
            f["player_norm"] = f["player"].map(normalize_name)
        if "home_eligible" in f.columns:
            f = f[f["home_eligible"]]
        if "born" not in f.columns:
            f["born"] = pd.NA
        frames.append(f[["player_norm", "born"]].rename(columns={"born": "born_feat"}))
    if not frames:
        return len(nt_flags)
    combined = pd.concat(frames, ignore_index=True)

    nt = nt_flags.reset_index(drop=True).reset_index()
    candidates = nt.merge(combined, on="player_norm", how="inner")
    # same rule as features._attach_flags: a missing birth year is forgiven on
    # the squad-table side only
    born_ok = candidates["born"].isna() | (candidates["born_feat"] == candidates["born"])
    matched = set(candidates.loc[born_ok, "index"])
    return len(nt) - len(matched)


def compute_checks(
    pool: pd.DataFrame,
    tables: pd.DataFrame,
    features_by_group: dict[str, pd.DataFrame],
    nt_flags: pd.DataFrame,
    country_page_html: str | None = None,
    keepers: pd.DataFrame | None = None,
) -> list[dict]:
    """Seven recomputed wrangling-check rows: `{"id", "count", "unit"}` each.

    See the module docstring for what each check recomputes and why.
    `country_page_html` is the cached FBref country page's text, or `None`
    when the cache file isn't present (`women_filtered`'s count is then
    `None` rather than a guess). `keepers` is `fbref_keepers.parquet`, or
    `None` when it hasn't been fetched yet (`gk_unjoined`'s count is then
    `None` too, same tolerance) -- `gk_unjoined` reruns Task 18's own
    `src.goalkeepers.join_keeper_pool` (league, season, team, player_key)
    against the GK rows of `tables`, so it always reflects the exact join
    `src.goalkeepers` performs, not a separate approximation of it.
    """
    pool_norm = pool["player"].map(normalize_name)
    women_filtered = _women_filtered_count(country_page_html) if country_page_html else None
    gk_unjoined = None if keepers is None or keepers.empty else join_keeper_pool(keepers, tables)[1]

    return [
        {"id": "women_filtered", "count": women_filtered, "unit": "entries"},
        {"id": "namesakes", "count": int(pool_norm.duplicated(keep=False).sum()), "unit": "players"},
        {"id": "no_tables", "count": int((~pool["in_fbref_tables"]).sum()), "unit": "players"},
        {"id": "split_seasons", "count": _split_seasons_count(features_by_group), "unit": "rows"},
        {"id": "nt_unmatched", "count": _nt_unmatched_count(nt_flags, features_by_group), "unit": "names"},
        {"id": "missing_born",
         "count": int(tables.loc[tables["nation"] == config.HOME, "born"].isna().sum()), "unit": "rows"},
        {"id": "gk_unjoined", "count": gk_unjoined, "unit": "rows"},
    ]


def main() -> None:
    logging_setup()
    p = config.PROCESSED_DIR
    pool = read_parquet(p / "pool.parquet")
    tables = read_parquet(p / "fbref_players.parquet")
    features_by_group = {g: read_parquet(p / f"features_{g}.parquet") for g in GROUPS}
    nt_flags = read_parquet(p / "nt_flags.parquet")

    html = COUNTRY_PAGE_CACHE.read_text(encoding="utf-8") if COUNTRY_PAGE_CACHE.exists() else None
    if html is None:
        LOG.warning("cached country page not found at %s; women_filtered count will be null", COUNTRY_PAGE_CACHE)

    keepers_path = p / "fbref_keepers.parquet"
    keepers = read_parquet(keepers_path) if keepers_path.exists() else None
    if keepers is None:
        LOG.warning("%s not found; gk_unjoined count will be null", keepers_path)

    checks = compute_checks(pool, tables, features_by_group, nt_flags, country_page_html=html, keepers=keepers)
    events = config.load_yaml("data_quality_events.yaml")["events"]

    out_path = config.PROCESSED_DIR / "data_quality.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"checks": checks, "events": events}, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    LOG.info("wrote %s (%d checks, %d events)", out_path, len(checks), len(events))


if __name__ == "__main__":
    main()
