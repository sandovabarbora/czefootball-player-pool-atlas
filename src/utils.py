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

LOG = logging.getLogger(__name__)


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
    headers.setdefault("User-Agent", "czehockey-player-pool-atlas/0.1 (research)")
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


def read_parquet(path: Path) -> pd.DataFrame:
    """Read a parquet file; clear error if it does not exist."""
    if not path.exists():
        raise FileNotFoundError(f"Expected parquet not found: {path}. Run upstream fetcher first.")
    return pd.read_parquet(path)
