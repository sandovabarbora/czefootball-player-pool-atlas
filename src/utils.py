"""Small utilities shared across fetchers and features.

Keep this thin. If something grows beyond ~30 lines and is used in only one
caller, move it into the caller.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import pandas as pd
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from unidecode import unidecode

from src import config

LOG = logging.getLogger(__name__)


def season_label(season: str) -> str:
    """'2024-2025' -> '2024/25'."""
    start, end = season.split("-")
    return f"{start}/{end[-2:]}"


def normalize_name(name: str) -> str:
    """Canonicalize a player name for cross-source matching.

    unidecode (strip diacritics) -> lowercase -> collapse whitespace.
    """
    ascii_name = unidecode(str(name))
    return re.sub(r"\s+", " ", ascii_name.strip().lower())


def player_key(name: str, born: object) -> str:
    """Build the canonical player key: normalized name + birth year.

    FBref's player-season tables carry no player id, so `normalize_name(name)
    + "|" + str(born)` is the join key across leagues/seasons (see Task 0
    spike). `born` becomes "x" when missing or not a finite number.
    """
    born_part = "x" if born is None or pd.isna(born) else str(int(born))
    return f"{normalize_name(name)}|{born_part}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((requests.RequestException,)),
    reraise=True,
)
def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    sleep_after: float = 0.0,
) -> requests.Response:
    """Polite HTTP GET with retry/backoff.

    Args:
        url: full URL to request.
        headers: optional HTTP headers (User-Agent set if not provided).
        timeout: per-request timeout in seconds.
        sleep_after: seconds to sleep after a successful response. Use to be
            polite to servers without backoff math.

    Returns:
        The successful Response object.

    Raises:
        requests.HTTPError: on non-2xx after retries.
    """
    headers = headers or {}
    headers.setdefault("User-Agent", "czefootball-player-pool-atlas/0.1 (research)")
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    if sleep_after:
        time.sleep(sleep_after)
    return resp


def cached_text(
    url: str,
    cache_path: Path,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> str:
    """Return `cache_path`'s text if it exists, else fetch `url` and cache it.

    http_get has no built-in cache, so fetchers that hit slow/rate-limited
    sources (Wikipedia, ClubElo, ...) keep a small local file cache instead
    of re-hitting the source on every run. Each caller picks its own
    `cache_path` (directory + filename convention) and headers (e.g.
    User-Agent); this helper only handles the read-through-cache logic.

    Args:
        url: full URL to request on a cache miss.
        cache_path: file to read from / write to. Parent directory is
            created if missing.
        headers: passed through to http_get.
        timeout: passed through to http_get.

    Returns:
        The cached or freshly-fetched text.
    """
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    resp = http_get(url, headers=headers, timeout=timeout)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(resp.text, encoding="utf-8")
    return resp.text


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to parquet, ensuring parent directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    LOG.info("wrote %s rows to %s", len(df), path)


def resolve_processed(path: Path) -> Path:
    """Return `path`, or its `config.SNAPSHOT_DIR` twin when `path` is missing.

    `data/processed/` is gitignored while `data/snapshot/` (the same
    parquet/json files) is committed, so a clean clone can render without
    refetching: any reader of a processed file goes through this helper and
    picks the snapshot copy when the processed one is absent, with a WARNING
    so a missing upstream stage in a full `make all` run stays visible. Only files that live directly in `config.PROCESSED_DIR` are
    redirected; anything else is returned unchanged.
    """
    if path.exists():
        return path
    if path.parent != config.PROCESSED_DIR:
        return path
    fallback = config.SNAPSHOT_DIR / path.name
    if fallback.exists():
        LOG.warning("%s missing; using snapshot copy %s", path, fallback)
        return fallback
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    """Read a parquet file, falling back to the snapshot copy (see
    `resolve_processed`); clear error if neither exists."""
    path = resolve_processed(path)
    if not path.exists():
        raise FileNotFoundError(f"Expected parquet not found: {path}. Run upstream fetcher first.")
    return pd.read_parquet(path)


def collapse_player_seasons(
    df: pd.DataFrame,
    rate_cols: list[str],
    key_cols: tuple[str, ...] = ("player_key", "season", "pos_group"),
) -> pd.DataFrame:
    """Collapse duplicate (player_key, season, pos_group) rows into one.

    `features_*.parquet` is built from `fbref_players.parquet`, which has
    one row per player-TEAM-season -- a player transferred mid-season (rare,
    but real) therefore has two rows for the same player_key/season/pos_group,
    one per club. Left uncollapsed, that duplication lets one transferred
    player occupy two analog-candidate slots in `find_analogs`, or inflate
    `sensitivity.churn()`'s rank comparison via a cartesian merge.

    This is NOT a re-run of Bayesian shrinkage from raw counts (that would
    require redoing the (league, season) shrinkage cohort math in
    `features.bayesian_shrink`, which a couple of split-season rows don't
    justify). Instead, for each duplicate group:
      - `min` is summed (that player's total minutes that season)
      - every column in `rate_cols` (per-90 rate/quality columns, already on
        the features frame) is replaced by its minutes-weighted mean across
        the group's rows (weights = each row's `min`) -- a reasonable
        second-order approximation of a season aggregate. Rows where that
        rate is NaN are excluded from both the weighted sum and the weight
        total, so a NaN stint never dilutes the result toward zero -- if
        only one row has a value, the collapsed result is exactly that
        row's value.
      - every other column (`league`, `team`, `nation`, `born`, `age`,
        `nt_flag`, `nt_events`, `home_eligible`, `league_multiplier`, ...)
        is taken from the row with the most minutes (that club/league is
        where most of the player's season was spent)

    Groups of size 1 pass through unchanged (weighted mean of one row is
    itself; sum of one row's `min` is itself), so it is always safe to call
    this on a full features frame, not just on rows known to be duplicated.
    """
    key_cols = list(key_cols)
    df = df.reset_index(drop=True)
    sizes = df.groupby(key_cols)["min"].transform("size")
    singles, dup_rows = df[sizes == 1], df[sizes > 1]
    if dup_rows.empty:
        return df

    other_cols = [c for c in df.columns if c not in {*key_cols, *rate_cols, "min"}]
    collapsed = []
    for _, g in dup_rows.groupby(key_cols):
        total_min = float(g["min"].sum())
        lead = g.loc[g["min"].idxmax()]
        row = {c: lead[c] for c in key_cols}
        row["min"] = int(total_min)
        for c in rate_cols:
            row[c] = _weighted_mean_skip_nan(g[c], g["min"])
        row.update({c: lead[c] for c in other_cols})
        collapsed.append(row)

    out = pd.concat([singles, pd.DataFrame(collapsed)], ignore_index=True)
    return out[df.columns.tolist()]


def _weighted_mean_skip_nan(values: pd.Series, weights: pd.Series) -> float:
    """Minutes-weighted mean of `values`, excluding rows where `values` is NaN.

    The weight denominator only sums the minutes of the *valid* rows, so a
    NaN stint's minutes don't dilute the result: with one NaN row and one
    valid row, the answer is exactly the valid row's own value, not that
    value scaled down by its share of total minutes. Returns NaN if every
    row is NaN.
    """
    valid = values.notna()
    if not valid.any():
        return float("nan")
    v, w = values[valid].astype(float), weights[valid].astype(float)
    w_total = w.sum()
    return float(v.mean()) if w_total <= 0 else float((v * w).sum() / w_total)
