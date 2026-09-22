"""UEFA men's association (country) coefficient ranking, from Wikipedia.

Used as a fallback source for league quality multipliers when ClubElo's API
is unavailable (see src/fetch_elo.py: it tries ClubElo first and falls back
here on an HTTP failure). The coefficient is UEFA's rolling current 5-year
points total per national association, taken from the "Current ranking"
table under the "Men's association coefficient" section of
https://en.wikipedia.org/wiki/UEFA_coefficient -- NOT the women's or
amateur-competition tables on the same page, which share a near-identical
column layout but rank different (and much lower/differently-scoped) totals.

src.utils.http_get has no built-in cache, so a small file cache is kept here
via src.utils.cached_text (shared with src/fetch_squads.py and
src/fetch_elo.py) to avoid re-hitting Wikipedia on every run.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup
from bs4.element import Tag

from src import config
from src.utils import cached_text

LOG = logging.getLogger(__name__)

USER_AGENT = "czefootball-player-pool-atlas/1.0 (hello@bsandova.com)"
UEFA_COEFFICIENT_URL = "https://en.wikipedia.org/wiki/UEFA_coefficient"

# Association name, as it appears on the Wikipedia table before any trailing
# "(L, C)" competition-format annotation, -> the country code used in
# config/leagues.yaml. A couple of associations carry two accepted English
# names on Wikipedia over time (Turkey/Türkiye, Czech Republic/Czechia); both
# are mapped to the same code.
ASSOCIATION_TO_CODE: dict[str, str] = {
    "England": "ENG",
    "Italy": "ITA",
    "Spain": "ESP",
    "Germany": "GER",
    "France": "FRA",
    "Netherlands": "NED",
    "Portugal": "POR",
    "Belgium": "BEL",
    "Turkey": "TUR",
    "Türkiye": "TUR",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Austria": "AUT",
    "Hungary": "HUN",
    "Poland": "POL",
    "Croatia": "CRO",
    "Denmark": "DEN",
    "Switzerland": "SUI",
    "Norway": "NOR",
    "Slovakia": "SVK",
}

_ASSOCIATION_HEADING_RE = re.compile(r"men.?s\s+association\s+coefficient", re.I)
_SEASON_RE = re.compile(r"^(19|20)\d{2}[–-](\d{2}|(19|20)\d{2})$")
_NUM_RE = re.compile(r"\d+\.\d+|\d+")

__all__ = ["country_coefficients", "fetch_country_coefficients", "ranking_seasons"]


def _table_columns(table: Tag) -> tuple[int, int, list[str], int] | None:
    """Return (association_col, total_coefficient_col, season_labels, n_header_rows).

    The target table has a 2-row header: row0 carries top-level headers
    ("Ranking", "Member association", "Coefficient", "Teams", "Places..."),
    some spanning multiple columns (colspan) or both header rows
    (rowspan=2); row1 carries the leaf sub-headers for the multi-column
    groups (season labels + "Total" under "Coefficient", etc). "Total"
    appears twice in row1 (once for the 5-year coefficient total, once for
    the "Places" summary at the very end) -- only the one nested under the
    "Coefficient" top header is what we want, hence tracking `coef_range`.
    Returns None if the table doesn't look like this shape.
    """
    rows = table.find_all("tr")
    header_rows: list[list[Tag]] = []
    for r in rows:
        cells = r.find_all(["th", "td"])
        if cells and all(c.name == "th" for c in cells):
            header_rows.append(cells)
        else:
            break
    if len(header_rows) < 2:
        return None
    row0, row1 = header_rows[0], header_rows[1]

    col = 0
    assoc_col: int | None = None
    coef_range: tuple[int, int] | None = None
    rowspan_cols: set[int] = set()
    for c in row0:
        colspan = int(c.get("colspan", 1))
        rowspan = int(c.get("rowspan", 1))
        text = c.get_text(" ", strip=True)
        if rowspan >= 2:
            if re.search(r"association", text, re.I):
                assoc_col = col
            rowspan_cols.add(col)
        elif re.search(r"coefficient", text, re.I):
            coef_range = (col, col + colspan)
        col += colspan
    if assoc_col is None or coef_range is None:
        return None

    row1_map: dict[int, str] = {}
    c_idx = 0
    for c in row1:
        while c_idx in rowspan_cols:
            c_idx += 1
        row1_map[c_idx] = c.get_text(" ", strip=True)
        c_idx += 1

    season_labels = [row1_map[ci] for ci in range(*coef_range) if _SEASON_RE.match(row1_map.get(ci, ""))]
    total_col = next(
        (ci for ci in range(*coef_range) if row1_map.get(ci, "").strip().lower() == "total"),
        None,
    )
    if total_col is None or not season_labels:
        return None
    return assoc_col, total_col, season_labels, len(header_rows)


def _find_table(soup: BeautifulSoup) -> tuple[Tag, int, int, list[str], int]:
    heading = next((h for h in soup.find_all("h2") if _ASSOCIATION_HEADING_RE.search(h.get_text())), None)
    candidates: list[Tag] = []
    if heading is not None:
        first = heading.find_next("table", class_=re.compile("wikitable"))
        if first is not None:
            candidates.append(first)
    candidates += soup.find_all("table", class_=re.compile("wikitable"))
    for table in candidates:
        info = _table_columns(table)
        if info is not None:
            assoc_col, total_col, season_labels, n_header = info
            return table, assoc_col, total_col, season_labels, n_header
    raise ValueError("no men's-association-coefficient wikitable found")


def country_coefficients(html: str) -> dict[str, float]:
    """Parse the men's association 5-year UEFA coefficient ranking.

    Returns {country_code: total_5yr_coefficient} for the associations
    mapped in ASSOCIATION_TO_CODE (others present on the page, e.g. Serbia,
    Ukraine, are dropped -- we only need the countries referenced in
    config/leagues.yaml).
    """
    soup = BeautifulSoup(html, "lxml")
    table, assoc_col, total_col, _season_labels, n_header = _find_table(soup)

    out: dict[str, float] = {}
    for r in table.find_all("tr")[n_header:]:
        cells = r.find_all(["td", "th"])
        if len(cells) <= max(assoc_col, total_col):
            continue
        name = cells[assoc_col].get_text(" ", strip=True).split("(")[0].strip()
        code = ASSOCIATION_TO_CODE.get(name)
        if code is None:
            continue
        m = _NUM_RE.search(cells[total_col].get_text(" ", strip=True))
        if m is None:
            LOG.warning("no numeric coefficient for %s (%s), skipping", name, code)
            continue
        out[code] = float(m.group(0))
    return out


def ranking_seasons(html: str) -> list[str]:
    """Return the season labels (e.g. ["2022-23", ..., "2026-27"]) making up the ranking."""
    soup = BeautifulSoup(html, "lxml")
    _table, _assoc_col, _total_col, season_labels, _n_header = _find_table(soup)
    return season_labels


def _fetch_html(url: str, cache_key: str) -> str:
    """Fetch `url`, cached under data/raw/wiki/<cache_key>.html."""
    cache_path = config.RAW_DIR / "wiki" / f"{cache_key}.html"
    return cached_text(url, cache_path, headers={"User-Agent": USER_AGENT})


def fetch_country_coefficients() -> tuple[dict[str, float], list[str]]:
    """Fetch the live page and return (coefficients, season_labels)."""
    html = _fetch_html(UEFA_COEFFICIENT_URL, "uefa_coefficient")
    return country_coefficients(html), ranking_seasons(html)
